-- Questions 3, 5 and 6 (run on Exasol SaaS). {VEC_TABLE} is filled from .env (QDRANT_COLLECTION).

-- Q3 · Find complaints about damaged goods (Qdrant Cloud embeds the search text)
SELECT v."SCORE" AS SIMILARITY, t.TICKET_ID, t.CATEGORY, t.CHURN_INTENT, t.TICKET_TEXT
FROM  (SELECT "ID", "SCORE" FROM {VEC_TABLE}
       WHERE "QUERY" = 'goods smashed during shipping' LIMIT 4) v
JOIN   DEMO_DATA.SUPPORT_TICKETS t ON t.TICKET_ID = CAST(v."ID" AS DECIMAL(9,0))
ORDER  BY v."SCORE" DESC;

-- Q5 · Which customers does our ML model flag as likely to leave?
WITH scored AS (
  SELECT C_CUSTKEY, TICKET_TEXT, DEMO_AI.CHURN_RISK(TICKET_TEXT) AS RISK
  FROM   DEMO_DATA.SUPPORT_TICKETS),
per_customer AS (
  SELECT C_CUSTKEY, SUM(CASE WHEN RISK >= 0.5 THEN 1 ELSE 0 END) AS RISKY_TICKETS,
         MAX(RISK) AS MAX_RISK, MAX(CASE WHEN RISK >= 0.5 THEN TICKET_TEXT END) AS EXAMPLE
  FROM scored GROUP BY C_CUSTKEY)
SELECT c.C_NAME AS CUSTOMER, c.NATION, p.RISKY_TICKETS, ROUND(100 * p.MAX_RISK) AS RISK_PCT,
       ROUND(c.OPEN_ORDER_VALUE / 1e3, 0) AS OPEN_ORDERS_K, p.EXAMPLE
FROM   per_customer p
JOIN   DEMO_ACCEL.CUSTOMER_360 c ON c.C_CUSTKEY = p.C_CUSTKEY
WHERE  p.RISKY_TICKETS > 0
ORDER  BY p.RISKY_TICKETS DESC, c.OPEN_ORDER_VALUE DESC
LIMIT  5;

-- Q6 · Which unhappy customers put the most revenue at risk?
--   vector search (Qdrant Cloud) finds candidates -> the ML model (Python UDF) confirms churn -> revenue (Snowflake + S3, accelerated)
WITH candidates AS (
  SELECT CAST("ID" AS DECIMAL(9,0)) AS TICKET_ID
  FROM   {VEC_TABLE}
  WHERE  "QUERY" = 'customer is unhappy and threatening to move to another supplier'
  LIMIT  300),
confirmed AS (
  SELECT t.C_CUSTKEY, t.TICKET_TEXT, DEMO_AI.CHURN_RISK(t.TICKET_TEXT) AS RISK
  FROM   candidates a JOIN DEMO_DATA.SUPPORT_TICKETS t ON t.TICKET_ID = a.TICKET_ID)
SELECT c.C_NAME AS CUSTOMER, c.NATION, c.SEGMENT,
       ROUND(c.OPEN_ORDER_VALUE / 1e3, 0) AS OPEN_ORDERS_K,
       c.PCT_LATE AS PCT_LINES_LATE,
       COUNT(*) AS ANGRY_TICKETS,
       MAX(f.TICKET_TEXT) AS SAMPLE_TICKET
FROM   confirmed f
JOIN   DEMO_ACCEL.CUSTOMER_360 c ON c.C_CUSTKEY = f.C_CUSTKEY
WHERE  f.RISK >= 0.5
GROUP  BY c.C_NAME, c.NATION, c.SEGMENT, c.OPEN_ORDER_VALUE, c.PCT_LATE
ORDER  BY c.OPEN_ORDER_VALUE DESC
LIMIT  10;
