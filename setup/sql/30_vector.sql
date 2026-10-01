-- Vector search: Exasol SaaS -> Qdrant Cloud. No embedding server of your own:
-- Qdrant Cloud Inference turns text into vectors, both when loading and when searching.
-- Python adapter because Qdrant Cloud needs https (the Labs Lua adapter only speaks http).
--
-- Run on: Exasol SaaS. The connection is created by setup/setup.py from .env:
--   CREATE CONNECTION DEMO_QDRANT_CONN TO '<cluster https url>' USER '' IDENTIFIED BY '<qdrant api key>';
CREATE SCHEMA IF NOT EXISTS DEMO_VEC_ADAPTER;

-- Load: a SET UDF receives ticket rows and upserts them to Qdrant Cloud in batches; Qdrant embeds the text.
CREATE OR REPLACE PYTHON3 SET SCRIPT DEMO_VEC_ADAPTER.PUSH_TO_QDRANT(
  conn VARCHAR(200), collection VARCHAR(200), model VARCHAR(200), id DECIMAL(18,0), text VARCHAR(2000))
EMITS (pushed INT) AS
import json, urllib.request

def _call(url, key, method, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method=method,
                                 headers={"api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)

def run(ctx):
    c = exa.get_connection(ctx.conn)
    url, key, col, model = c.address.rstrip("/"), c.password, ctx.collection, ctx.model
    batch, total = [], 0
    while True:
        batch.append({"id": int(ctx.id), "payload": {"_original_id": str(int(ctx.id)), "text": ctx.text},
                      "vector": {"text": {"text": ctx.text, "model": model}}})
        more = ctx.next()
        if len(batch) == 64 or not more:
            _call(f"{url}/collections/{col}/points?wait=true", key, "PUT", {"points": batch})
            total += len(batch)
            batch = []
        if not more:
            break
    ctx.emit(total)
/

-- Search: the virtual-schema adapter. Each Qdrant collection becomes a table (ID, TEXT, SCORE, QUERY);
-- WHERE "QUERY" = '...' is sent to Qdrant as text, Qdrant Cloud embeds it and returns the nearest points.
CREATE OR REPLACE PYTHON3 ADAPTER SCRIPT DEMO_VEC_ADAPTER.QDRANT_CLOUD_ADAPTER AS
import json, urllib.request

def _props(req):
    return ((req.get("schemaMetadataInfo") or {}).get("properties") or {})

def _conn(p):
    c = exa.get_connection(p["CONNECTION_NAME"])
    return c.address.rstrip("/"), c.password or ""

def _http(url, key, body=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 method="GET" if body is None else "POST",
                                 headers={"api-key": key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)

def _tables(p):
    url, key = _conn(p)
    cols = [{"name": "ID", "dataType": {"type": "VARCHAR", "size": 2000000, "characterSet": "UTF8"}},
            {"name": "TEXT", "dataType": {"type": "VARCHAR", "size": 2000000, "characterSet": "UTF8"}},
            {"name": "SCORE", "dataType": {"type": "DOUBLE"}},
            {"name": "QUERY", "dataType": {"type": "VARCHAR", "size": 2000000, "characterSet": "UTF8"}}]
    names = [c["name"] for c in _http(f"{url}/collections", key)["result"]["collections"]]
    return [{"name": n.upper(), "columns": cols} for n in sorted(names)]

def _lit(s):
    return "'" + str(s).replace("'", "''") + "'"

def _empty():
    return ("SELECT CAST('' AS VARCHAR(2000000) UTF8) AS ID, CAST('' AS VARCHAR(2000000) UTF8) AS TEXT, "
            "CAST(0 AS DOUBLE) AS SCORE, CAST('' AS VARCHAR(2000000) UTF8) AS QUERY FROM DUAL WHERE FALSE")

def _pushdown(req, p):
    pdr = req.get("pushdownRequest") or {}
    f = pdr.get("filter") or {}
    q = ""
    if f.get("type") == "predicate_equal":
        l, r = f.get("left") or {}, f.get("right") or {}
        if l.get("type") == "column" and l.get("name", "").upper() == "QUERY" and r.get("type") == "literal_string":
            q = r["value"]
        elif r.get("type") == "column" and r.get("name", "").upper() == "QUERY" and l.get("type") == "literal_string":
            q = l["value"]
    if not q:
        return ("SELECT * FROM VALUES (CAST('HINT' AS VARCHAR(2000000) UTF8), CAST("
                + _lit('Search with WHERE "QUERY" = \'your text\'') + " AS VARCHAR(2000000) UTF8), CAST(0 AS DOUBLE), "
                "CAST('' AS VARCHAR(2000000) UTF8)) AS t(ID, TEXT, SCORE, QUERY)")
    limit = int(((pdr.get("limit") or {}).get("numElements")) or 10)
    col = req["involvedTables"][0]["name"].lower()
    url, key = _conn(p)
    res = _http(f"{url}/collections/{col}/points/query", key,
                {"query": {"text": q, "model": p["QDRANT_MODEL"]}, "using": "text", "limit": limit, "with_payload": True})
    pts = (res.get("result") or {}).get("points") or []
    if not pts:
        return _empty()
    rows = ",".join(f"(CAST({_lit(pt['payload'].get('_original_id', pt['id']))} AS VARCHAR(2000000) UTF8),"
                    f"CAST({_lit(pt['payload'].get('text', ''))} AS VARCHAR(2000000) UTF8),"
                    f"CAST({float(pt.get('score', 0))} AS DOUBLE),CAST({_lit(q)} AS VARCHAR(2000000) UTF8))" for pt in pts)
    return f"SELECT * FROM VALUES {rows} AS t(ID, TEXT, SCORE, QUERY)"

def adapter_call(request_json):
    req = json.loads(request_json)
    t = req.get("type", "").lower()
    if t == "getcapabilities":
        return json.dumps({"type": "getCapabilities",
                           "capabilities": ["SELECTLIST_EXPRESSIONS", "FILTER_EXPRESSIONS", "LIMIT", "LIMIT_WITH_OFFSET",
                                            "FN_PRED_EQUAL", "LITERAL_STRING"]})
    if t in ("createvirtualschema", "refresh"):
        name = "createVirtualSchema" if t == "createvirtualschema" else "refresh"
        return json.dumps({"type": name, "schemaMetadata": {"tables": _tables(_props(req))}})
    if t == "setproperties":
        p = dict(_props(req))
        for k, v in (req.get("properties") or {}).items():
            if v in ("", None):
                p.pop(k, None)
            else:
                p[k] = v
        return json.dumps({"type": "setProperties", "schemaMetadata": {"tables": _tables(p)}})
    if t == "dropvirtualschema":
        return json.dumps({"type": "dropVirtualSchema"})
    if t == "pushdown":
        return json.dumps({"type": "pushdown", "sql": _pushdown(req, _props(req))})
    raise ValueError("unsupported request type " + t)
/
