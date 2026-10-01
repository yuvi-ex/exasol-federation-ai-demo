"""Settings from .env (repo root), with environment variables taking precedence. No secrets in code."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL = ROOT / "setup" / "sql"


def _load():
    env = {}
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k in env or k.startswith(("EXASOL_", "SNOWFLAKE_", "S3_", "QDRANT_"))})
    return env


ENV = _load()


def get(key, default=None):
    v = ENV.get(key, default)
    if v is None:
        raise SystemExit(f"Missing setting {key}: copy .env.example to .env and fill it in.")
    return v


# Object names used everywhere (SQL files, setup, app). Change here to run several copies side by side.
NAMES = {
    "SNOWFLAKE_VS": "DEMO_SNOWFLAKE", "SF_ADAPTER": "DEMO_SF_ADAPTER", "SF_CONN": "DEMO_SNOWFLAKE_CONN",
    "S3_CONN": "DEMO_S3_CONN", "FEDERATED": "DEMO_FEDERATED", "ACCEL": "DEMO_ACCEL", "DATA": "DEMO_DATA",
    "VEC_ADAPTER": "DEMO_VEC_ADAPTER", "VEC": "DEMO_VEC", "QDRANT_CONN": "DEMO_QDRANT_CONN", "AI": "DEMO_AI",
}
BUCKET_DIR = "demo"                      # folder in SaaS BucketFS for jars and the model
UDF_BUCKET = "/buckets/uploads/default"  # how SaaS UDFs see uploaded files


def vec_table():
    return f'{NAMES["VEC"]}.{get("QDRANT_COLLECTION", "support_tickets").upper()}'
