"""Exasol SaaS connection for the page, timed queries, and a cached fallback.

Every successful result is written to cache/<key>.json. If a source fails during a demo, the page shows the
last good result and labels it as cached, never silently. A failed connect backs off for 30 s so the page
never hangs (an auto-stopped database or an IP that is not on the allow-list both look like a timeout).
"""
import json
import re
import sys
import time
from pathlib import Path

import pyexasol
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from demo.config import get  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
_NUM = re.compile(r"^-?\d+(\.\d+)?$")
_DOWN = {}
_BACKOFF = 30


def _num(v):
    """pyexasol returns DECIMAL as str; turn numeric strings into numbers for display."""
    if isinstance(v, str) and _NUM.match(v):
        return float(v) if "." in v else int(v)
    return v


def _check_down(which):
    if time.time() - _DOWN.get(which, 0) < _BACKOFF:
        raise ConnectionError("Exasol is not reachable (retrying in a few seconds)")


@st.cache_resource(show_spinner=False)
def _conn(which: str):
    _check_down(which)
    try:
        con = pyexasol.connect(dsn=f"{get('EXASOL_HOST')}:{get('EXASOL_PORT', '8563')}", user=get("EXASOL_USER"),
                               password=get("EXASOL_PAT"), encryption=True, fetch_dict=True, connection_timeout=5)
    except Exception:
        _DOWN[which] = time.time()
        raise
    con.execute("ALTER SESSION SET QUERY_TIMEOUT = 120")
    return con


def run(which: str, sql: str, key: str | None = None) -> dict:
    """Run sql on Exasol. Returns {rows, cols, secs, live, error, at}."""
    t = time.time()
    try:
        try:
            stmt = _conn(which).execute(sql)
        except (pyexasol.ExaCommunicationError, pyexasol.ExaConnectionError):
            _conn.clear()                      # dropped socket: reconnect once
            _check_down(which)
            stmt = _conn(which).execute(sql)
        if stmt.result_type == "resultSet":
            rows, cols = [{k: _num(v) for k, v in r.items()} for r in stmt.fetchall()], list(stmt.column_names())
        else:  # DDL / CTAS: report the affected row count as a one-row result
            rows, cols = [{"ROWS_WRITTEN": stmt.rowcount()}], ["ROWS_WRITTEN"]
        res = {"rows": rows, "cols": cols, "secs": time.time() - t, "live": True, "error": None,
               "at": time.strftime("%H:%M:%S")}
        if key:
            CACHE.mkdir(exist_ok=True)
            (CACHE / f"{key}.json").write_text(json.dumps(res, default=str))
        return res
    except Exception as e:  # noqa: BLE001 - any failure falls back to the cached result
        msg = getattr(e, "message", str(e))
        f = CACHE / f"{key}.json" if key else None
        if f and f.exists():
            res = json.loads(f.read_text())
            res.update(live=False, error=msg[:300])
            return res
        return {"rows": [], "cols": [], "secs": time.time() - t, "live": False, "error": msg[:300], "at": None}


def ping(which: str) -> bool:
    try:
        _conn(which).execute("SELECT 1")
        return True
    except Exception:  # noqa: BLE001
        _conn.clear()
        return False
