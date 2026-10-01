#!/usr/bin/env python3
"""Set up the demo on Exasol SaaS from the settings in .env.

    python -m setup.setup            # every step, in order
    python -m setup.setup check      # one step (or several: jars snowflake lake ...)

Steps: check, jars, snowflake, lake, s3, accelerate, tickets, vector, ml, smoke.
Each step is safe to re-run. Run setup/snowflake_setup.sql in Snowflake first.
"""
import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from demo import exa
from demo.config import BUCKET_DIR, NAMES, ROOT, SQL, UDF_BUCKET, get, vec_table

JARS = ROOT / "jars"
VS_JAR = "virtual-schema-dist-14.0.4-snowflake-1.0.1.jar"
VS_URL = f"https://github.com/exasol/snowflake-virtual-schema/releases/download/1.0.1/{VS_JAR}"
JDBC_VER = "4.3.4"
JDBC_JAR = f"snowflake-jdbc-{JDBC_VER}.jar"
JDBC_URL = f"https://repo1.maven.org/maven2/net/snowflake/snowflake-jdbc/{JDBC_VER}/{JDBC_JAR}"
LAKE_PREFIX = "lake/lineitem"
DATASETS = ROOT / "datasets"
YEARS = range(1992, 1999)


def say(msg):
    print(f"  {msg}", flush=True)


def fetch(url, dest, checksum_url, algo):
    if not dest.exists():
        say(f"downloading {dest.name}")
        urllib.request.urlretrieve(url, dest)
    want = urllib.request.urlopen(checksum_url, timeout=60).read().decode().split()[0]
    got = hashlib.new(algo, dest.read_bytes()).hexdigest()
    if got != want:
        dest.unlink()
        raise SystemExit(f"checksum mismatch for {dest.name}: delete it and re-run")
    say(f"{dest.name}: {algo} verified")


def snowflake():
    import snowflake.connector
    return snowflake.connector.connect(account=get("SNOWFLAKE_ACCOUNT"), user=get("SNOWFLAKE_USER"),
                                       password=get("SNOWFLAKE_PAT"), role=get("SNOWFLAKE_ROLE"),
                                       warehouse=get("SNOWFLAKE_WAREHOUSE"), login_timeout=30)


def qdrant(method, path, body=None):
    req = urllib.request.Request(get("QDRANT_URL").rstrip("/") + path, method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"api-key": get("QDRANT_API_KEY"), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def until_visible(fn, what, tries=18, wait=10):
    """A file uploaded to SaaS BucketFS takes a little while to appear under /buckets; retry until it does."""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            msg = getattr(e, "message", str(e))
            if i == tries - 1 or not any(k in msg for k in ("cannot find", "No such file", "FileNotFound", "not found")):
                raise
            say(f"waiting for {what} to appear in BucketFS ({(i + 1) * wait}s)")
            time.sleep(wait)


def lit(s):
    return "'" + s.replace("'", "''") + "'"


# ------------------------------------------------------------------ steps
def step_check(con):
    ver = con.execute("SELECT PARAM_VALUE FROM EXA_METADATA WHERE PARAM_NAME = 'databaseProductVersion'").fetchval()
    say(f"Exasol: {ver}")
    py = con.execute("SELECT SESSION_VALUE FROM EXA_PARAMETERS WHERE PARAMETER_NAME = 'SCRIPT_LANGUAGES'").fetchval()
    say("Python UDFs available" if "PYTHON3" in py else "WARNING: no PYTHON3 script language")
    s = snowflake().cursor().execute("SELECT COUNT(*) FROM EXASOL_DEMO_ADMIN.TPCH.ORDERS").fetchone()[0]
    say(f"Snowflake: {s:,} orders visible to {get('SNOWFLAKE_USER')}")
    say(f"Qdrant Cloud: version {qdrant('GET', '/')['version']}")
    aws = subprocess.run(["aws", "sts", "get-caller-identity", "--query", "Arn", "--output", "text"], capture_output=True, text=True)
    say(f"AWS CLI: {aws.stdout.strip() or 'not logged in (needed only for the lake step)'}")


def step_jars(con):
    JARS.mkdir(exist_ok=True)
    fetch(VS_URL, JARS / VS_JAR, VS_URL + ".sha256", "sha256")
    fetch(JDBC_URL, JARS / JDBC_JAR, JDBC_URL + ".sha1", "sha1")
    cfg = JARS / "settings.cfg"
    cfg.write_text(f"DRIVERNAME=SNOWFLAKE_JDBC_DRIVER\nJAR={JDBC_JAR}\nDRIVERMAIN=net.snowflake.client.api.driver.SnowflakeDriver\n"
                   "PREFIX=jdbc:snowflake:\nFETCHSIZE=100000\nINSERTSIZE=-1\nNOSECURITY=YES\n\n")
    for local, remote in [(cfg, "drivers/jdbc/snowflake/settings.cfg"), (JARS / JDBC_JAR, f"drivers/jdbc/snowflake/{JDBC_JAR}"),
                          (JARS / VS_JAR, f"{BUCKET_DIR}/{VS_JAR}")]:
        exa.bucketfs_upload(local, remote)
        say(f"uploaded {remote}")


def step_snowflake(con):
    n = NAMES
    url = (f"jdbc:snowflake://{get('SNOWFLAKE_ACCOUNT').lower()}.snowflakecomputing.com/?JDBC_QUERY_RESULT_FORMAT=JSON"
           f"&warehouse={get('SNOWFLAKE_WAREHOUSE')}&role={get('SNOWFLAKE_ROLE')}&db=SNOWFLAKE_SAMPLE_DATA")
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {n['SF_ADAPTER']}")
    # the token goes in the password field: Exasol never prints it in errors
    con.execute(f"CREATE OR REPLACE CONNECTION {n['SF_CONN']} TO {lit(url)} USER {lit(get('SNOWFLAKE_USER'))} "
                f"IDENTIFIED BY {lit(get('SNOWFLAKE_PAT'))}")
    con.execute(f"""CREATE OR REPLACE JAVA ADAPTER SCRIPT {n['SF_ADAPTER']}.SNOWFLAKE_JDBC_ADAPTER AS
  %scriptclass com.exasol.adapter.RequestDispatcher;
  %jar {UDF_BUCKET}/{BUCKET_DIR}/{VS_JAR};
  %jar {UDF_BUCKET}/drivers/jdbc/snowflake/{JDBC_JAR};
  // keeps the final ';' above from being taken as the statement terminator
""")
    exists = con.execute(f"SELECT COUNT(*) FROM EXA_ALL_VIRTUAL_SCHEMAS WHERE SCHEMA_NAME = {lit(n['SNOWFLAKE_VS'])}").fetchval()
    if exists:
        con.execute(f"ALTER VIRTUAL SCHEMA {n['SNOWFLAKE_VS']} REFRESH")
    else:
        until_visible(lambda: con.execute(
            f"CREATE VIRTUAL SCHEMA {n['SNOWFLAKE_VS']} USING {n['SF_ADAPTER']}.SNOWFLAKE_JDBC_ADAPTER WITH "
            f"CATALOG_NAME = 'EXASOL_DEMO_ADMIN' SCHEMA_NAME = 'TPCH' CONNECTION_NAME = {lit(n['SF_CONN'])}"), "the adapter jar")
    vs = n["SNOWFLAKE_VS"]
    nations = con.execute(f"SELECT COUNT(*) FROM {vs}.NATION").fetchval()
    say(f"virtual schema {vs}: {nations} nations read live from Snowflake")


def step_lake(con):
    bucket = get("S3_BUCKET")
    have = subprocess.run(["aws", "s3", "ls", f"s3://{bucket}/{LAKE_PREFIX}/"], capture_output=True, text=True).stdout
    if all(f"ship_year={y}.parquet" in have for y in YEARS):
        say(f"s3://{bucket}/{LAKE_PREFIX}/ already has the 7 Parquet files, skipping")
        return
    local = DATASETS / "lake" / "lineitem"
    if all((local / f"ship_year={y}.parquet").exists() for y in YEARS):
        subprocess.run(["aws", "s3", "sync", str(local), f"s3://{bucket}/{LAKE_PREFIX}/", "--only-show-errors"], check=True)
        say(f"uploaded the 7 Parquet files from datasets/ to s3://{bucket}/{LAKE_PREFIX}/")
        return
    say("datasets/lake/lineitem is missing, exporting LINEITEM from Snowflake instead")
    import pyarrow as pa
    import pyarrow.parquet as pq
    money = pa.decimal128(15, 2)
    schema = pa.schema([("L_ORDERKEY", pa.int64()), ("L_PARTKEY", pa.int64()), ("L_SUPPKEY", pa.int64()), ("L_LINENUMBER", pa.int64()),
                        ("L_QUANTITY", money), ("L_EXTENDEDPRICE", money), ("L_DISCOUNT", money), ("L_TAX", money),
                        ("L_RETURNFLAG", pa.string()), ("L_LINESTATUS", pa.string()), ("L_SHIPDATE", pa.date32()),
                        ("L_COMMITDATE", pa.date32()), ("L_RECEIPTDATE", pa.date32()), ("L_SHIPINSTRUCT", pa.string()),
                        ("L_SHIPMODE", pa.string()), ("L_DAYS_LATE", pa.int64())])
    out = ROOT / "setup" / "data" / "lake"
    out.mkdir(parents=True, exist_ok=True)
    cur = snowflake().cursor()
    for y in YEARS:
        cur.execute(f"""SELECT L_ORDERKEY, L_PARTKEY, L_SUPPKEY, L_LINENUMBER,
               L_QUANTITY::NUMBER(15,2) L_QUANTITY, L_EXTENDEDPRICE::NUMBER(15,2) L_EXTENDEDPRICE,
               L_DISCOUNT::NUMBER(15,2) L_DISCOUNT, L_TAX::NUMBER(15,2) L_TAX, L_RETURNFLAG, L_LINESTATUS,
               L_SHIPDATE, L_COMMITDATE, L_RECEIPTDATE, L_SHIPINSTRUCT, L_SHIPMODE,
               DATEDIFF('day', L_COMMITDATE, L_RECEIPTDATE) AS L_DAYS_LATE
            FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.LINEITEM WHERE YEAR(L_SHIPDATE) = {y}""")
        # Snowflake's Arrow result picks the narrowest type per batch; a lake file needs one stable schema
        t = cur.fetch_arrow_all().select(schema.names).cast(schema)
        pq.write_table(t, out / f"ship_year={y}.parquet", compression="snappy")
        say(f"{y}: {t.num_rows:,} rows")
    subprocess.run(["aws", "s3", "sync", str(out), f"s3://{bucket}/{LAKE_PREFIX}/", "--only-show-errors"], check=True)
    say(f"uploaded to s3://{bucket}/{LAKE_PREFIX}/")


def step_s3(con):
    url = f"https://{get('S3_BUCKET')}.s3.{get('S3_REGION')}.amazonaws.com"
    con.execute(f"CREATE OR REPLACE CONNECTION {NAMES['S3_CONN']} TO {lit(url)} USER {lit(get('S3_READER_ACCESS_KEY_ID'))} "
                f"IDENTIFIED BY {lit(get('S3_READER_SECRET_ACCESS_KEY'))}")
    say(f"{exa.run_file(con, SQL / '10_federated_views.sql')} statements from 10_federated_views.sql")
    rows = con.execute(f"SELECT COUNT(*) FROM {NAMES['FEDERATED']}.S3_LINEITEM").fetchval()
    say(f"S3 view: {rows:,} rows read in place")


def step_accelerate(con):
    t = time.time()
    exa.run_file(con, SQL / "20_accelerate.sql")
    n = con.execute(f"SELECT COUNT(*) FROM {NAMES['ACCEL']}.CUSTOMER_360").fetchval()
    say(f"{NAMES['ACCEL']}.CUSTOMER_360: {n:,} customers built from Snowflake + S3 in {time.time() - t:.0f}s")


def step_tickets(con):
    csv_file = DATASETS / "support_tickets.csv"
    if not csv_file.exists():  # regenerate (deterministic, seed 42): same rows as the committed file
        subprocess.run([sys.executable, "gen_tickets.py"], cwd=ROOT / "setup" / "data", check=True, capture_output=True)
        csv_file = ROOT / "setup" / "data" / "support_tickets.csv"
    d = NAMES["DATA"]
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {d}")
    con.execute(f"""CREATE OR REPLACE TABLE {d}.SUPPORT_TICKETS (
      TICKET_ID DECIMAL(9,0), C_CUSTKEY DECIMAL(9,0), CREATED_DATE DATE, CHANNEL VARCHAR(40),
      CATEGORY VARCHAR(20), CHURN_INTENT DECIMAL(1,0), TICKET_TEXT VARCHAR(2000))""")
    con.import_from_file(str(csv_file), (d, "SUPPORT_TICKETS"), import_params={"skip": 1})
    cnt = con.execute(f"SELECT COUNT(*) FROM {d}.SUPPORT_TICKETS").fetchval()
    say(f"{d}.SUPPORT_TICKETS: {cnt:,} synthetic tickets")


def step_vector(con):
    n, col, model = NAMES, get("QDRANT_COLLECTION", "support_tickets"), get("QDRANT_MODEL")
    con.execute(f"CREATE OR REPLACE CONNECTION {n['QDRANT_CONN']} TO {lit(get('QDRANT_URL'))} USER '' IDENTIFIED BY {lit(get('QDRANT_API_KEY'))}")
    say(f"{exa.run_file(con, SQL / '30_vector.sql')} statements from 30_vector.sql")
    try:
        qdrant("DELETE", f"/collections/{col}")
    except Exception:  # noqa: BLE001 - absent on a first run
        pass
    qdrant("PUT", f"/collections/{col}", {"vectors": {"text": {"size": int(get("QDRANT_DIM", "384")), "distance": "Cosine"}}})
    t = time.time()
    pushed = con.execute(f"""SELECT SUM(PUSHED) FROM (SELECT {n['VEC_ADAPTER']}.PUSH_TO_QDRANT({lit(n['QDRANT_CONN'])}, {lit(col)},
        {lit(model)}, TICKET_ID, TICKET_TEXT) FROM {n['DATA']}.SUPPORT_TICKETS GROUP BY IPROC())""").fetchval()
    say(f"pushed {int(pushed):,} tickets from Exasol to Qdrant Cloud in {time.time() - t:.0f}s (Qdrant embeds them)")
    con.execute(f"DROP FORCE VIRTUAL SCHEMA IF EXISTS {n['VEC']}")
    con.execute(f"CREATE VIRTUAL SCHEMA {n['VEC']} USING {n['VEC_ADAPTER']}.QDRANT_CLOUD_ADAPTER WITH "
                f"CONNECTION_NAME = {lit(n['QDRANT_CONN'])} QDRANT_MODEL = {lit(model)}")
    r = con.execute(f"""SELECT COUNT(*) FROM (SELECT "ID" FROM {vec_table()} WHERE "QUERY" = 'goods smashed during shipping' LIMIT 5)""").fetchval()
    say(f"virtual schema {n['VEC']}: test search returned {r} tickets")


def step_ml(con):
    ai, d = NAMES["AI"], NAMES["DATA"]
    say(f"{exa.run_file(con, SQL / '40_ml_udfs.sql')} statements from 40_ml_udfs.sql")
    t = time.time()
    n, algo, b64 = con.execute(f"SELECT {ai}.TRAIN_CHURN_MODEL(TICKET_TEXT, CHURN_INTENT) FROM {d}.SUPPORT_TICKETS "
                               "WHERE MOD(TICKET_ID, 5) <> 0").fetchone()
    say(f"trained inside Exasol on {n:,} tickets in {time.time() - t:.1f}s")
    ver = int(con.execute(f"SELECT MAX(VERSION) FROM {ai}.MODEL_REGISTRY WHERE MODEL_NAME = 'churn'").fetchval() or 0) + 1
    con.execute(f"INSERT INTO {ai}.MODEL_REGISTRY VALUES ('churn', {{v}}, CURRENT_TIMESTAMP, {{n}}, {{a}}, {{m}})",
                {"v": ver, "n": n, "a": algo, "m": b64})
    with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
        f.write(base64.b64decode(b64))
    exa.bucketfs_upload(f.name, f"{BUCKET_DIR}/models/churn_model.pkl")
    say(f"registered churn v{ver}, uploaded to BucketFS {BUCKET_DIR}/models/churn_model.pkl")
    def holdout():
        return con.execute(f"""SELECT COUNT(*), SUM(CASE WHEN (RISK >= 0.5) = (CHURN_INTENT = 1) THEN 1 ELSE 0 END),
                  SUM(CASE WHEN RISK >= 0.5 AND CHURN_INTENT = 1 THEN 1 ELSE 0 END), SUM(CASE WHEN RISK >= 0.5 THEN 1 ELSE 0 END),
                  SUM(CHURN_INTENT)
                FROM (SELECT CHURN_INTENT, {ai}.CHURN_RISK(TICKET_TEXT) RISK FROM {d}.SUPPORT_TICKETS WHERE MOD(TICKET_ID, 5) = 0)""").fetchone()
    r = until_visible(holdout, "the model")
    tot, ok, tp, pp, ap = (int(x) for x in r)
    con.execute(f"CREATE OR REPLACE TABLE {ai}.MODEL_METRICS AS SELECT 'churn' MODEL_NAME, {{v}} VERSION, {{n}} N_TEST, "
                "{acc} ACCURACY, {prec} PRECISION_, {rec} RECALL",
                {"v": ver, "n": tot, "acc": round(ok / tot, 4), "prec": round(tp / max(pp, 1), 4), "rec": round(tp / max(ap, 1), 4)})
    say(f"hold-out: {tot:,} unseen tickets, accuracy {100 * ok / tot:.1f}% (synthetic tickets make this easy)")


def step_smoke(con):
    q = (SQL / "50_questions.sql").read_text().replace("{VEC_TABLE}", vec_table())
    checks = [("Q1 Snowflake", f"SELECT COUNT(*) FROM (SELECT n.N_NAME, SUM(o.O_TOTALPRICE) FROM {NAMES['SNOWFLAKE_VS']}.ORDERS o "
                               f"JOIN {NAMES['SNOWFLAKE_VS']}.CUSTOMER c ON c.C_CUSTKEY = o.O_CUSTKEY JOIN {NAMES['SNOWFLAKE_VS']}.NATION n "
                               "ON n.N_NATIONKEY = c.C_NATIONKEY GROUP BY n.N_NAME)"),
              ("Q2 S3", f"SELECT COUNT(DISTINCT L_SHIPMODE) FROM {NAMES['FEDERATED']}.S3_LINEITEM"),
              ("Q4 accelerated", f"SELECT COUNT(DISTINCT NATION) FROM {NAMES['ACCEL']}.CUSTOMER_360")]
    parts = [p for p in exa.statements(q)]
    checks += [("Q3 vector", parts[0]), ("Q5 ML", parts[1]), ("Q6 everything", parts[2])]
    for label, sql in checks:
        t = time.time()
        rows = con.execute(sql).fetchall()
        say(f"{label}: ok ({len(rows)} rows, {time.time() - t:.1f}s)")


STEPS = ["check", "jars", "snowflake", "lake", "s3", "accelerate", "tickets", "vector", "ml", "smoke"]

if __name__ == "__main__":
    wanted = sys.argv[1:] or STEPS
    bad = [s for s in wanted if s not in STEPS]
    if bad:
        raise SystemExit(f"unknown step(s) {bad}; choose from {STEPS}")
    con = exa.connect()
    con.execute("ALTER SESSION SET QUERY_TIMEOUT = 900")
    for s in STEPS:
        if s in wanted:
            print(f"[{s}]", flush=True)
            globals()[f"step_{s}"](con)
    print("done.")
