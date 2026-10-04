# One engine, every source: Exasol federation + in-database AI demo

A live, click-through demo of Exasol as **one governed SQL endpoint** over a warehouse (**Snowflake**), a data lake
(**Parquet on Amazon S3**) and a vector store (**Qdrant Cloud**), with an **ML model trained and run inside the database**.
Everything runs live on cloud services; the laptop only runs the browser.

```
User  (analyst · notebook · BI tool · AI agent)
  │
Exasol SaaS
  ├── Semantic Views       the certified business contract (shown as concept; Exasol Labs project)
  ├── Native tables        accelerated working set (CUSTOMER_360)
  └── Python UDF           scikit-learn model, loaded from BucketFS, scores rows in parallel
  │
Virtual schemas & connectors
  ├── C  Snowflake      JDBC virtual schema, full pushdown        (TPC-H sample: customers + orders)
  ├── D  Amazon S3      IMPORT FROM PARQUET, read in place        (TPC-H line items, 6 M rows)
  └── A  Qdrant Cloud   Python virtual-schema adapter over https  (5,000 synthetic support tickets)
```

The page has two tabs:

- **Overview**: the challenge, the architecture, a live "wrong but plausible" fan-out example, the adoption path,
  how MLflow fits, a measured token comparison for LLM agents, and an illustrative Langfuse trace.
- **Live demo**: six questions, each answered live. The diagram lights the path a question takes; every answer shows
  three measured numbers and what Exasol did. The SQL is behind "For engineers".

| # | Question | What it proves |
|---|---|---|
| 1 | Which countries bring the most revenue? | Snowflake read live; the whole join and GROUP BY run in Snowflake, 25 rows come back |
| 2 | Which shipping modes run late? | 6 M rows read straight from Parquet on S3, no load job |
| 3 | Find complaints about damaged goods | Semantic search in a WHERE clause; Qdrant Cloud embeds the text itself |
| 4 | Which big customers keep getting late deliveries? | Snowflake orders + S3 shipments copied once into Exasol: the same answer as asking both live, in about 0.2 s instead of about 47 s |
| 5 | Which customers does our ML model flag as likely to leave? | Model trained and run inside Exasol, nothing exported |
| 6 | Which unhappy customers put the most revenue at risk? | Vector search + ML model + accelerated data in one SQL statement |

## What you need

| Service | Notes |
|---|---|
| **Exasol SaaS** | A trial works. Add your laptop's public IP under Security. Create a personal access token. |
| **Snowflake** | A trial works. Uses the built-in `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1`. |
| **Amazon S3** | One private bucket (same region as Exasol, ideally), plus an IAM user with **read-only** access to it. |
| **Qdrant Cloud** | The free tier works. Its Cloud Inference creates the embeddings, so no embedding server is needed. |
| **Laptop** | Python 3.11+, the AWS CLI logged in (only to upload the Parquet files once). |

Costs on trials are small: an XSmall Exasol cluster (auto-stops when idle), an X-Small Snowflake warehouse
(auto-suspends after 60 s), about 125 MB in S3, and Qdrant's free tier.

## Setup

1. **Snowflake.** In Snowsight, open a new SQL file, paste [`setup/snowflake_setup.sql`](setup/snowflake_setup.sql) and
   choose **Run all** (as ACCOUNTADMIN). Copy the `TOKEN_SECRET` it shows; it is shown only once.
2. **S3 read-only user.** In IAM, create a user with this policy, and an access key for it:
   ```json
   {"Version": "2012-10-17", "Statement": [{"Effect": "Allow",
     "Action": ["s3:GetObject", "s3:ListBucket", "s3:GetBucketLocation"],
     "Resource": ["arn:aws:s3:::YOUR-BUCKET", "arn:aws:s3:::YOUR-BUCKET/*"]}]}
   ```
3. **Settings.** `cp .env.example .env` and fill it in. `.env` is git-ignored.
4. **Install and run the setup** (about 5 minutes; every step is safe to re-run):
   ```bash
   python -m venv .venv && . .venv/bin/activate
   pip install -r requirements.txt
   python -m setup.setup            # or one step at a time: check, jars, snowflake, lake, s3, accelerate, tickets, vector, ml, smoke
   ```
   It downloads and checksum-verifies the Snowflake virtual schema adapter and JDBC driver, uploads them to BucketFS,
   creates the virtual schemas and connections, uploads the Parquet files from `datasets/` to your S3 bucket, builds the
   accelerated table, loads the synthetic tickets from `datasets/`, pushes them to Qdrant Cloud from inside Exasol,
   trains the model inside Exasol, and finishes with a smoke test of all six questions.
5. **Start the page:** `./app/run.sh`, then open http://localhost:8510 (another port: `PORT=8511 ./app/run.sh`).

Before a demo: start the Exasol database (it auto-stops when idle), check the IP allow-list if you are on a new
network, and click through the six questions once. Every successful run is cached, so if a source is slow during the
demo the page shows the last good result, clearly labelled as cached.

## Telling the story

Lead with the audience's challenges, then show each one solved live:

1. **Data is spread across systems; every project starts with a pipeline** → virtual schemas query it in place (questions 1, 2).
2. **Federation is too slow for what everyone uses** → federate first, copy only the hot data into Exasol, and prove the answer is identical (question 4).
3. **Vector search lives in a silo** → Qdrant becomes a SQL table you can join (question 3).
4. **Models have to leave the data to be scored** → Python UDFs score in the database; MLflow models can live in BucketFS via [`exasol/mlflow-plugin`](https://github.com/exasol/mlflow-plugin) (question 5).
5. **SQL that runs but is wrong** → the fan-out example on the Overview tab; [Semantic Views](https://github.com/exasol-labs/exasol-semantic-views) refuses ill-posed questions.
6. **Agents are expensive and opaque** → small exact answers instead of raw data (the token chart); Langfuse plus Exasol's query log for observability.

Finish on question 6 and its banner: **"No pipeline was built for this question."**

Be precise about two things: Semantic Views is an **Exasol Labs** project (confirm support status before committing to
it), and the Langfuse trace is **illustrative** (only the SQL step is measured live).

## What is in the repo

| Path | What |
|---|---|
| `app/` | The Streamlit page (`app.py`), its Exasol connection and cache (`db.py`), styling (`theme.py`) |
| `setup/setup.py` | The step-by-step setup described above |
| `setup/snowflake_setup.sql` | Role, warehouse, typed views and token for Snowflake |
| `setup/sql/10_federated_views.sql` | S3 Parquet view and the Snowflake/S3 federated views |
| `setup/sql/20_accelerate.sql` | The one statement that builds `CUSTOMER_360` inside Exasol |
| `setup/sql/25_late_deliveries.sql` | Question 4, asked live across Snowflake + S3 and on the Exasol copy |
| `setup/sql/30_vector.sql` | The Qdrant Cloud virtual-schema adapter (Python) and the loader UDF |
| `setup/sql/40_ml_udfs.sql` | The model registry, the training UDF and the scoring UDF |
| `setup/sql/50_questions.sql` | Questions 3, 5 and 6 |
| `datasets/` | The data the demo loads: synthetic tickets (CSV) and the S3 lake (7 Parquet files); see [datasets/README.md](datasets/README.md) |
| `setup/data/gen_tickets.py` | Regenerates the tickets exactly (fixed seed) |
| `demo/` | Settings loader and Exasol helpers |

## Where the data lives (and how to show it)

Every source keeps its own data; Exasol reads it where it is. If the audience asks to see the data in the source system:

| Source | What is there | Where to look | Background |
|---|---|---|---|
| **Snowflake** | TPC-H customers (150 k) and orders (1.5 M), exposed as typed views `EXASOL_DEMO_ADMIN.TPCH.*` | Snowsight: run `SELECT * FROM EXASOL_DEMO_ADMIN.TPCH.ORDERS LIMIT 10;`. To show the pushdown, open **Monitoring → Query History** and filter on user `EXASOL_SVC`: each demo question appears as one query that Exasol sent | [Snowflake's TPC-H sample data](https://docs.snowflake.com/en/user-guide/sample-data-tpch) · [Query History](https://docs.snowflake.com/en/user-guide/ui-snowsight-activity) · [TPC-H](https://www.tpc.org/tpch/) |
| **Amazon S3** | 7 Parquet files, 6,001,215 shipment lines, under `lake/lineitem/` | S3 console → your bucket → `lake/` → `lineitem/` (the bucket is private, so the object URL returns Access Denied; that is the point), or `aws s3 ls s3://YOUR-BUCKET/lake/lineitem/ --human-readable --summarize`. The same files are in this repo: [`datasets/lake/lineitem/`](datasets/lake/lineitem/) | [Exasol `IMPORT ... FROM PARQUET`](https://docs.exasol.com/db/latest/sql/import.htm) · [Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html) |
| **Qdrant Cloud** | 5,000 support tickets as 384-dimension vectors (collection set by `QDRANT_COLLECTION`) | [cloud.qdrant.io](https://cloud.qdrant.io) → your cluster → **Dashboard** → the collection: points, vectors and payload text. The source CSV is in this repo: [`datasets/support_tickets.csv`](datasets/support_tickets.csv) | [Qdrant Cloud Inference](https://qdrant.tech/documentation/cloud/inference/) · [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) · [Exasol Labs Qdrant adapter](https://github.com/exasol-labs/exasol-qdrant-adapter) |
| **Exasol** | `DEMO_ACCEL.CUSTOMER_360` (one row per customer, built once from Snowflake + S3), `DEMO_DATA.SUPPORT_TICKETS`, the model registry `DEMO_AI.MODEL_REGISTRY` and the model file in BucketFS (`/buckets/uploads/default/demo/models/churn_model.pkl`) | Any SQL client: `SELECT * FROM DEMO_ACCEL.CUSTOMER_360 LIMIT 10;` and `SELECT MODEL_NAME, VERSION, TRAINED_AT, N_TRAIN, ALGORITHM FROM DEMO_AI.MODEL_REGISTRY;` | [Exasol SaaS](https://docs.exasol.com/saas/home.htm) · [Snowflake virtual schema](https://github.com/exasol/snowflake-virtual-schema) |

`CUSTOMER_360` is an ordinary Exasol table, not a cache: it has no expiry and stays as of its last build. Rebuild it with
the button under question 4 ("For engineers"), or on a schedule, by re-running `setup/sql/20_accelerate.sql`.

## Things worth knowing

- **Snowflake keys are `NUMBER(38,0)`.** Exasol's DECIMAL stops at 36 digits, so the virtual schema would map them to
  `VARCHAR(2000000)`: wrong joins and slow transfers. The typed views in `snowflake_setup.sql` expose them as `NUMBER(18,0)`.
- **GROUP BY pushdown.** Keep `ROUND()` outside the aggregating subquery, or Snowflake receives the join without the
  GROUP BY and ships every row back. Check with `EXPLAIN VIRTUAL`.
- **Snowflake string literals.** The current Snowflake dialect renders string literals in a form Snowflake rejects in
  some pushdowns; the views push down literal-free aggregations and filter in Exasol.
- **Snowflake login.** The connection uses a programmatic access token in the password field. A key-file path doesn't
  work for the loader, and a key embedded in the URL would appear in error messages.
- **Qdrant Cloud needs https**, so the adapter is written in Python (the Exasol Labs Lua adapter speaks http only).
- **BucketFS uploads** on SaaS go through the API and take a few seconds to appear under `/buckets/uploads/default/`.
- **Pure vector search with a small free model** is weak at "churn intent"; question 6 therefore pairs it with the ML
  model (vector candidates, then the model confirms).
- **Data residency.** Qdrant's free inference models run in the US; for real data use its EU models or your own Qdrant.

## Data

Customers and orders are the **TPC-H** sample that every Snowflake account has; shipments are TPC-H line items, included
as Parquet in [`datasets/`](datasets/README.md). The support tickets are **synthetic** (also in `datasets/`, generated by
`setup/data/gen_tickets.py`) and linked to real TPC-H customer keys; their churn phrasing is easy to learn, which is why the model scores near 100%. TPC-H dates are uniform
by design, so late-shipment rates look similar everywhere: they prove the joins, not a business finding.

## License

MIT, see [LICENSE](LICENSE).
