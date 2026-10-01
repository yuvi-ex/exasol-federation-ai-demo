-- In-database ML on Exasol SaaS: train with a SET UDF (scikit-learn), store in BucketFS, score with a scalar UDF.
-- Train with a SET UDF (scikit-learn inside Exasol), register the model, score with a scalar UDF.
CREATE SCHEMA IF NOT EXISTS DEMO_AI;

CREATE TABLE IF NOT EXISTS DEMO_AI.MODEL_REGISTRY (
  MODEL_NAME VARCHAR(100), VERSION DECIMAL(9,0), TRAINED_AT TIMESTAMP,
  N_TRAIN DECIMAL(9,0), ALGORITHM VARCHAR(200), MODEL_B64 VARCHAR(2000000));

-- Train: every training row arrives in one call; the fitted pipeline comes back as base64.
CREATE OR REPLACE PYTHON3 SET SCRIPT DEMO_AI.TRAIN_CHURN_MODEL(ticket_text VARCHAR(2000), churn DECIMAL(1,0))
EMITS (n_train INT, algorithm VARCHAR(200), model_b64 VARCHAR(2000000)) AS
import base64, pickle
from sklearn.pipeline import make_pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

def run(ctx):
    texts, labels = [], []
    while True:
        texts.append(ctx.ticket_text)
        labels.append(int(ctx.churn))
        if not ctx.next():
            break
    model = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True),
                          LogisticRegression(max_iter=2000, class_weight="balanced"))
    model.fit(texts, labels)
    ctx.emit(len(texts), "TF-IDF (1-2 grams) + logistic regression, scikit-learn",
             base64.b64encode(pickle.dumps(model)).decode())
/

-- Score: the model is loaded from BucketFS once per UDF instance, then every row is scored in parallel.
CREATE OR REPLACE PYTHON3 SCALAR SCRIPT DEMO_AI.CHURN_RISK(ticket_text VARCHAR(2000)) RETURNS DOUBLE AS
import pickle
MODEL = pickle.load(open("/buckets/uploads/default/demo/models/churn_model.pkl", "rb"))

def run(ctx):
    if ctx.ticket_text is None:
        return None
    return float(MODEL.predict_proba([ctx.ticket_text])[0][1])
/
