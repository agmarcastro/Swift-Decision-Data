# BigQuery Materialized Views

> **Purpose**: When to use materialized views, incremental refresh, staleness, supported aggregates
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

A BigQuery materialized view (MV) is a pre-computed query result stored physically in
BigQuery and automatically refreshed when the base table changes (incremental delta
refresh). Queries that match the MV's definition are transparently rewritten to use
the MV instead — reducing cost and latency without changing the query SQL. MVs are
best for aggregation-heavy queries on large tables with predictable access patterns.

## When to Use Materialized Views

```
USE MATERIALIZED VIEW WHEN:          USE TABLE (e.g., dbt model) WHEN:
────────────────────────────────     ─────────────────────────────────────
Query is run 10+ times per day       ETL pipeline is batch / scheduled
Base table is large (>1 TB)          Complex transformations (JOINs, UDFs)
Query is aggregation-heavy           Need full control over refresh timing
Transparent rewrite is acceptable    Query shape varies unpredictably
Near-real-time freshness needed      Multiple CTEs, subquery nesting
```

## Creating a Materialized View

```sql
-- Materialized view: daily revenue aggregation
-- BigQuery incrementally refreshes this when fct_order_lines is updated
CREATE MATERIALIZED VIEW `project.dw.mv_daily_revenue`
OPTIONS (
    description         = 'Daily revenue by customer and product. Auto-refreshed.',
    enable_refresh      = true,
    refresh_interval_minutes = 60,   -- refresh at most every 60 minutes
    max_staleness       = INTERVAL '4' HOUR   -- tolerate up to 4h staleness
)
AS
SELECT
    order_date,
    customer_id,
    product_id,
    -- Supported aggregate functions
    COUNT(*)                    AS order_line_count,
    SUM(net_amount)             AS total_net_amount,
    SUM(quantity_ordered)       AS total_quantity,
    MAX(net_amount)             AS max_order_amount,
    MIN(net_amount)             AS min_order_amount,
    AVG(net_amount)             AS avg_order_amount,
    APPROX_COUNT_DISTINCT(customer_id) AS approx_unique_customers
FROM `project.dw.fct_order_lines`
WHERE order_date >= '2020-01-01'
GROUP BY 1, 2, 3;
```

## Supported Aggregate Functions

Only specific aggregate functions are supported in MVs. Unsupported functions cause
the MV creation to fail or fall back to non-incremental refresh.

| Supported | Notes |
|-----------|-------|
| `COUNT(*)` | Always supported |
| `COUNT(DISTINCT col)` | Supported (BigQuery uses HLL sketch internally) |
| `SUM(col)` | Supported |
| `MIN(col)` / `MAX(col)` | Supported |
| `AVG(col)` | Supported |
| `APPROX_COUNT_DISTINCT(col)` | Supported, faster |
| `HLL_COUNT.INIT(col)` | Supported for sketch-based cardinality |
| Complex subqueries | NOT supported — use dbt table instead |
| UDFs | NOT supported |
| Window functions | NOT supported |

## Staleness and Refresh Control

```sql
-- Check staleness of all materialized views
SELECT
    table_schema,
    table_name,
    last_refresh_time,
    TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), last_refresh_time, MINUTE) AS minutes_stale
FROM `project`.INFORMATION_SCHEMA.MATERIALIZED_VIEWS
ORDER BY minutes_stale DESC;

-- Manual refresh (force immediate sync)
CALL BQ.REFRESH_MATERIALIZED_VIEW('project.dw.mv_daily_revenue');

-- Disable auto-refresh (for cost control during off-hours)
ALTER MATERIALIZED VIEW `project.dw.mv_daily_revenue`
SET OPTIONS (enable_refresh = false);
```

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| Aggregation query, high frequency | Materialized view | Transparent rewrite |
| Complex JOIN + transform | dbt table/incremental | MVs don't support complex SQL |
| Near-real-time aggregation | MV with `refresh_interval_minutes = 5` | Trade cost for freshness |
| Tolerate some staleness | `max_staleness = INTERVAL '4' HOUR` | Query uses cached result |

## Common Mistakes

### Wrong

```sql
-- MV with a JOIN — incremental refresh not supported for JOIN-based MVs in most cases
CREATE MATERIALIZED VIEW mv_orders_joined AS
SELECT o.order_id, c.loyalty_tier
FROM fct_order_lines o
JOIN dim_customer c ON o.customer_key = c.customer_key;  -- JOIN: likely falls back to full refresh
```

### Correct

```sql
-- MV on a single table with pure aggregation — fully incremental
CREATE MATERIALIZED VIEW mv_daily_orders AS
SELECT order_date, COUNT(*) AS orders, SUM(net_amount) AS revenue
FROM fct_order_lines
GROUP BY 1;  -- single table, simple aggregation → incremental refresh
```

## Related

- [slots-and-cost.md](slots-and-cost.md)
- [patterns/cost-optimized-query.md](../patterns/cost-optimized-query.md)
- [partitioning.md](partitioning.md)
