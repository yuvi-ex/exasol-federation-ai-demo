"""Exasol SaaS helpers: connect, run a .sql file, upload a file to BucketFS through the SaaS API."""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

import pyexasol

from demo.config import get


def connect(**kw):
    return pyexasol.connect(dsn=f"{get('EXASOL_HOST')}:{get('EXASOL_PORT', '8563')}", user=get("EXASOL_USER"),
                            password=get("EXASOL_PAT"), encryption=True, **kw)


def statements(text):
    """Split SQL: ';' ends a statement, and a CREATE ... SCRIPT body ends with a line holding only '/'."""
    out, buf, in_script = [], [], False
    for line in text.splitlines(True):
        s = line.strip()
        if not in_script and not buf and (s.startswith("--") or not s):
            continue
        if not in_script and re.match(r"CREATE\s+(OR\s+REPLACE\s+)?\w+\s+(\w+\s+)?SCRIPT", s, re.I):
            in_script = True
        if in_script and s == "/":
            out.append("".join(buf)); buf, in_script = [], False
            continue
        buf.append(line)
        if not in_script and s.endswith(";"):
            out.append("".join(buf).rstrip().rstrip(";")); buf = []
    return out


def run_file(con, path, **fmt):
    text = Path(path).read_text()
    for k, v in fmt.items():
        text = text.replace("{" + k + "}", v)
    n = 0
    for st in statements(text):
        con.execute(st); n += 1
    return n


def bucketfs_upload(local_path, bucket_path):
    """POST files/{url-encoded key, slashes too} returns a presigned URL; PUT the bytes there."""
    key = urllib.parse.quote(bucket_path, safe="")
    api = (f"https://cloud.exasol.com/api/v1/accounts/{get('EXASOL_ACCOUNT_ID')}/databases/"
           f"{get('EXASOL_DATABASE_ID')}/files/{key}")
    req = urllib.request.Request(api, method="POST", headers={"Authorization": f"Bearer {get('EXASOL_PAT')}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        url = json.load(r)["url"]
    data = Path(local_path).read_bytes()
    put = urllib.request.Request(url, data=data, method="PUT")
    with urllib.request.urlopen(put, timeout=600) as r:
        if r.status != 200:
            raise RuntimeError(f"upload of {bucket_path} failed: HTTP {r.status}")
