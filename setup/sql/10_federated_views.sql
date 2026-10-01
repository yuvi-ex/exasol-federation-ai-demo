-- Runs on Exasol SaaS. Snowflake (warehouse) and S3 (lake) behind views; one row per customer where aggregated.
CREATE SCHEMA IF NOT EXISTS DEMO_FEDERATED;

-- S3 lakehouse: shipment lines read in place from Parquet (nothing stored in Exasol).
CREATE OR REPLACE VIEW DEMO_FEDERATED.S3_LINEITEM AS
SELECT * FROM (
  IMPORT INTO (L_ORDERKEY DECIMAL(18,0), L_PARTKEY DECIMAL(18,0), L_SUPPKEY DECIMAL(18,0), L_LINENUMBER DECIMAL(18,0),
    L_QUANTITY DECIMAL(15,2), L_EXTENDEDPRICE DECIMAL(15,2), L_DISCOUNT DECIMAL(15,2), L_TAX DECIMAL(15,2),
    L_RETURNFLAG VARCHAR(1), L_LINESTATUS VARCHAR(1), L_SHIPDATE DATE, L_COMMITDATE DATE, L_RECEIPTDATE DATE,
    L_SHIPINSTRUCT VARCHAR(25), L_SHIPMODE VARCHAR(10), L_DAYS_LATE DECIMAL(18,0))
  FROM PARQUET AT DEMO_S3_CONN
  FILE 'lake/lineitem/ship_year=1992.parquet' FILE 'lake/lineitem/ship_year=1993.parquet'
  FILE 'lake/lineitem/ship_year=1994.parquet' FILE 'lake/lineitem/ship_year=1995.parquet'
  FILE 'lake/lineitem/ship_year=1996.parquet' FILE 'lake/lineitem/ship_year=1997.parquet'
  FILE 'lake/lineitem/ship_year=1998.parquet');

-- Snowflake warehouse: customer value, aggregated inside Snowflake by pushdown.
-- The Snowflake dialect renders string literals as E'...' (Postgres syntax) which Snowflake rejects,
-- so only a literal-free GROUP BY is pushed down; the 'O' (open) test runs in Exasol on ~400k rows.
CREATE OR REPLACE VIEW DEMO_FEDERATED.SF_CUSTOMER_VALUE AS
WITH by_status AS (
  SELECT O_CUSTKEY, O_ORDERSTATUS, COUNT(*) AS N, SUM(O_TOTALPRICE) AS REVENUE, MAX(O_ORDERDATE) AS LAST_DATE
  FROM DEMO_SNOWFLAKE.ORDERS GROUP BY O_CUSTKEY, O_ORDERSTATUS)
SELECT c.C_CUSTKEY, c.C_NAME, n.N_NAME AS NATION, c.C_MKTSEGMENT AS SEGMENT,
       SUM(s.N) AS ORDERS, SUM(s.REVENUE) AS LIFETIME_REVENUE,
       SUM(CASE WHEN s.O_ORDERSTATUS = 'O' THEN s.REVENUE ELSE 0 END) AS OPEN_ORDER_VALUE,
       MAX(s.LAST_DATE) AS LAST_ORDER_DATE
FROM by_status s
JOIN DEMO_SNOWFLAKE.CUSTOMER c ON c.C_CUSTKEY = s.O_CUSTKEY
JOIN DEMO_SNOWFLAKE.NATION n ON n.N_NATIONKEY = c.C_NATIONKEY
GROUP BY c.C_CUSTKEY, c.C_NAME, n.N_NAME, c.C_MKTSEGMENT;

-- Lake x warehouse: delivery experience per customer (S3 lines joined to Snowflake orders).
CREATE OR REPLACE VIEW DEMO_FEDERATED.CUSTOMER_DELIVERY AS
SELECT o.O_CUSTKEY AS C_CUSTKEY, COUNT(*) AS LINES,
       SUM(CASE WHEN l.L_DAYS_LATE > 0 THEN 1 ELSE 0 END) AS LATE_LINES,
       ROUND(AVG(l.L_DAYS_LATE), 1) AS AVG_DAYS_LATE
FROM DEMO_FEDERATED.S3_LINEITEM l
JOIN (SELECT O_ORDERKEY, O_CUSTKEY FROM DEMO_SNOWFLAKE.ORDERS) o ON o.O_ORDERKEY = l.L_ORDERKEY
GROUP BY o.O_CUSTKEY;
