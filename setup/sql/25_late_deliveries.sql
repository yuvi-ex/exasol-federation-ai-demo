-- Question 4 · Which big customers keep getting late deliveries?
-- Asked twice: live across Snowflake + S3 (no copy), then on the table 20_accelerate.sql built inside Exasol.
-- Same answer; the second one is a fraction of a second. setup step "accelerate" runs both and records the live timing.

-- Q4 live
SELECT v.C_NAME AS CUSTOMER, v.NATION, ROUND(v.OPEN_ORDER_VALUE / 1e3, 0) AS OPEN_ORDERS_K,
       ROUND(100 * d.LATE_LINES / d.LINES, 1) AS PCT_LATE, d.LINES
FROM   DEMO_FEDERATED.SF_CUSTOMER_VALUE v                                   -- Snowflake orders
JOIN   DEMO_FEDERATED.CUSTOMER_DELIVERY d ON d.C_CUSTKEY = v.C_CUSTKEY      -- S3 shipments x Snowflake orders
WHERE  ROUND(100 * d.LATE_LINES / d.LINES, 1) >= 75
ORDER  BY v.OPEN_ORDER_VALUE DESC LIMIT 5;

-- Q4 accelerated
SELECT C_NAME AS CUSTOMER, NATION, ROUND(OPEN_ORDER_VALUE / 1e3, 0) AS OPEN_ORDERS_K, PCT_LATE, LINES
FROM   DEMO_ACCEL.CUSTOMER_360
WHERE  PCT_LATE >= 75                       -- 3 in 4 deliveries arrived after the promised date
ORDER  BY OPEN_ORDER_VALUE DESC LIMIT 5;

-- Q4 total
SELECT COUNT(*) AS CUSTOMERS, ROUND(SUM(OPEN_ORDER_VALUE) / 1e9, 2) AS OPEN_B
FROM   DEMO_ACCEL.CUSTOMER_360 WHERE PCT_LATE >= 75;
