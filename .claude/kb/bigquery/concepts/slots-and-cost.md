# BigQuery Slots and Cost

> **Purpose**: On-demand vs capacity slots, bytes processed, cost controls, dry_run
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

BigQuery pricing for query execution is based on bytes processed (on-demand) or
reserved slot-hours (capacity editions). Understanding the billing model and using
cost controls — partition filters, column selection, dry runs, and approximate
aggregations — is essential for managing DW operating cost at scale.

## On-Demand vs Capacity Editions

```
ON-DEMAND                           CAPACITY (EDITIONS)
─────────────────────────────────   ──────────────────────────────────
Pay per TB scanned                  Pay per slot-hour reserved
~$6.25 / TB (pricing varies)        Standard / Enterprise / Enterprise+
Auto-scales to available slots      Fixed slot pool (100 slots minimum)
Good for: irregular workloads       Good for: consistent high-volume jobs
No commitment                       Annual/monthly commitment for discount
```

## Slots Explained

A slot is a unit of BigQuery computation (virtual CPU + memory). One query may use
hundreds of slots temporarily. On-demand automatically borrows capacity; capacity
editions reserve a fixed pool shared across all queries in the project/reservation.

```sql
-- View slot usage for recent jobs (requires INFORMATION_SCHEMA access)
SELECT
    job_id,
    query,
    total_slot_ms,
    total_bytes_processed,
    ROUND(total_bytes_processed / POW(1024,4), 4) AS tb_processed,
    ROUND(total_bytes_processed / POW(1024,4) * 6.25, 4) AS est_cost_usd
FROM `region-us`.INFORMATION_SCHEMA.JOBS
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
  AND job_type = 'QUERY'
ORDER BY total_bytes_processed DESC
LIMIT 20;
```

## Cost Estimation Before Execution (Dry Run)

```bash
# Estimate bytes processed WITHOUT running the query
bq query \
  --dry_run \
  --use_legacy_sql=false \
  'SELECT customer_id, SUM(amount) FROM `project.dw.fct_orders`
   WHERE order_date >= "2024-01-01"
   GROUP BY 1'

# Output: "Query successfully validated. Assuming the tables are not modified,
#          running this query will process 1234567890 bytes."
# Cost estimate: bytes / 1TB * $6.25
```

```python
# Dry run via Python client
from google.cloud import bigquery

client = bigquery.Client()
job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)

query = """
    SELECT customer_id, SUM(amount)
    FROM `project.dw.fct_orders`
    WHERE order_date >= '2024-01-01'
    GROUP BY 1
"""

job = client.query(query, job_config=job_config)
print(f"Bytes to process: {job.total_bytes_processed:,}")
print(f"Est. cost: ${job.total_bytes_processed / 1e12 * 6.25:.4f} USD")
```

## Cost Controls

```sql
-- 1. Column selection: only read columns you need (columnar storage skips the rest)
-- BAD:
SELECT * FROM `project.dw.fct_order_lines`;          -- reads all columns

-- GOOD:
SELECT order_id, customer_id, net_amount
FROM `project.dw.fct_order_lines`;                   -- reads 3 columns only

-- 2. Partition filter: prune entire partitions before scanning
SELECT SUM(net_amount)
FROM `project.dw.fct_order_lines`
WHERE order_date = '2024-06-15';                     -- only 1 partition scanned

-- 3. Maximum bytes billed (fail-safe against runaway queries)
-- Set in BigQuery UI: Project Settings → Maximum bytes billed
-- Or via API:
job_config = bigquery.QueryJobConfig(maximum_bytes_billed=10 * 1024**3)  # 10 GB cap

-- 4. Query labels for cost attribution
SELECT /*+ LABEL('team=analytics,job=daily_revenue') */
    ...
```

## Approximate Aggregations

```sql
-- APPROX_COUNT_DISTINCT: 1% accuracy, 100x faster + cheaper than COUNT(DISTINCT)
SELECT APPROX_COUNT_DISTINCT(user_id) AS approx_users
FROM `project.dw.fct_events`
WHERE event_date = '2024-06-15';
```

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| Unknown query cost | `bq query --dry_run` | Zero cost, instant estimate |
| High-cost SELECT * | Explicit column list | Columnar skip reduces bytes |
| COUNT(DISTINCT x) on billions | `APPROX_COUNT_DISTINCT(x)` | 1% error, 100x cheaper |
| Protect against runaway query | `maximum_bytes_billed` | Hard cap in job config |

## Common Mistakes

### Wrong

```sql
-- SELECT * reads all columns from columnar storage — unnecessary cost
SELECT * FROM `project.dw.fct_order_lines`
WHERE order_date = '2024-06-15'
```

### Correct

```sql
-- Only project required columns
SELECT order_id, customer_id, net_amount
FROM `project.dw.fct_order_lines`
WHERE order_date = '2024-06-15'
```

## Related

- [partitioning.md](partitioning.md)
- [patterns/cost-optimized-query.md](../patterns/cost-optimized-query.md)
