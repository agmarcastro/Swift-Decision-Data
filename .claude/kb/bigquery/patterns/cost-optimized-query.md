# Cost-Optimized Query Pattern

> **Purpose**: Query optimization techniques — column selection, partition filters, CTEs, approximations
> **MCP Validated**: 2026-04-24

## When to Use

- Reviewing or refactoring queries that process unexpectedly large byte volumes
- Designing new analytical queries on large fact tables
- Establishing query standards for a team (code review checklist)

## Implementation

```sql
-- ============================================================
-- BEFORE: Expensive query pattern (anti-patterns annotated)
-- ============================================================
SELECT *                                            -- [BAD] reads ALL columns
FROM `project.dw.fct_order_lines` ol
JOIN `project.dw.dim_customer` c
    ON ol.customer_id = c.customer_id              -- [BAD] no is_current filter on SCD2
WHERE EXTRACT(YEAR FROM ol.order_date) = 2024      -- [BAD] function on partition column
                                                    --       prevents partition pruning!
GROUP BY ol.customer_id, c.loyalty_tier
ORDER BY COUNT(DISTINCT ol.order_id) DESC;          -- [BAD] COUNT DISTINCT is expensive
-- Estimated cost: 50 TB scanned (full table scan)

-- ============================================================
-- AFTER: Optimized version with all fixes applied
-- ============================================================

-- Step 1: Pre-filter large table BEFORE joining (partition + cluster pruning)
WITH filtered_orders AS (
    SELECT
        customer_id,
        order_id,
        net_amount,
        quantity_ordered
    FROM `project.dw.fct_order_lines`
    -- GOOD: literal date range on partition column → partition pruning
    WHERE order_date BETWEEN '2024-01-01' AND '2024-12-31'
    -- Additional cluster column filter
      AND order_status IN ('shipped', 'delivered')
),

-- Step 2: Aggregate before joining to dimension (reduce rows for JOIN)
order_summary AS (
    SELECT
        customer_id,
        APPROX_COUNT_DISTINCT(order_id)     AS approx_order_count,  -- cheaper than COUNT DISTINCT
        COUNT(*)                             AS line_count,
        SUM(net_amount)                      AS total_revenue,
        SUM(quantity_ordered)                AS total_quantity
    FROM filtered_orders
    GROUP BY customer_id
),

-- Step 3: Join to small dimension table AFTER aggregating fact (smaller JOIN)
customer_revenue AS (
    SELECT
        c.loyalty_tier,
        c.customer_id,
        c.full_name,
        o.approx_order_count,
        o.line_count,
        o.total_revenue,
        o.total_quantity
    FROM order_summary o
    -- GOOD: only join to current dimension records
    JOIN `project.dw.dim_customer` c
        ON o.customer_id = c.customer_id
       AND c.is_current = TRUE           -- SCD2 filter: only current version
)

SELECT
    loyalty_tier,
    COUNT(*)                                AS customer_count,
    SUM(approx_order_count)                 AS est_total_orders,
    SUM(total_revenue)                      AS total_revenue,
    AVG(total_revenue)                      AS avg_revenue_per_customer
FROM customer_revenue
GROUP BY loyalty_tier
ORDER BY total_revenue DESC;
-- Estimated cost: 0.5 TB scanned (100x reduction)
```

## Subquery vs CTE Performance

```sql
-- CTEs in BigQuery are NOT materialized by default (they act like views/macros)
-- BigQuery optimizer may inline or materialize CTEs automatically
-- For readability AND optimizer hints, CTEs are preferred over nested subqueries

-- AVOID: deeply nested subqueries (hard to read, harder to optimize)
SELECT * FROM (
    SELECT * FROM (
        SELECT customer_id, SUM(amount) FROM (
            SELECT * FROM raw_orders WHERE year = 2024
        ) GROUP BY 1
    ) WHERE total > 100
);

-- PREFER: flat CTE structure
WITH base     AS (SELECT customer_id, amount FROM raw_orders WHERE order_date >= '2024-01-01'),
     totals   AS (SELECT customer_id, SUM(amount) AS total FROM base GROUP BY 1),
     filtered AS (SELECT * FROM totals WHERE total > 100)
SELECT * FROM filtered;
```

## Optimization Checklist

| Check | Anti-Pattern | Fix |
|-------|-------------|-----|
| Column selection | `SELECT *` | Explicit column list |
| Partition filter | `WHERE YEAR(date) = 2024` (function wrapping) | `WHERE date BETWEEN '2024-01-01' AND '2024-12-31'` |
| SCD2 join | `JOIN dim_customer ON id = id` (no is_current) | Add `AND c.is_current = TRUE` |
| Distinct count | `COUNT(DISTINCT user_id)` | `APPROX_COUNT_DISTINCT(user_id)` for estimates |
| Join order | Small table drives large table | Aggregate large table first; join small dim last |
| Cost preview | Run without checking cost | Always `bq query --dry_run` first |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Partition filter | Literal date range | Avoid function wrapping on partition column |
| Approximate error | ~1% | `APPROX_COUNT_DISTINCT` accuracy vs `COUNT(DISTINCT)` |
| CTE strategy | Flat, named CTEs | One transformation step per CTE |

## Example Usage

```bash
# Always dry-run a new query before running on production data
bq query --dry_run --use_legacy_sql=false "
  SELECT loyalty_tier, SUM(net_amount)
  FROM \`project.dw.fct_order_lines\` ol
  JOIN \`project.dw.dim_customer\` c ON ol.customer_id = c.customer_id AND c.is_current = TRUE
  WHERE order_date BETWEEN '2024-01-01' AND '2024-12-31'
  GROUP BY 1
"
```

## See Also

- [concepts/slots-and-cost.md](../concepts/slots-and-cost.md)
- [concepts/partitioning.md](../concepts/partitioning.md)
- [concepts/clustering.md](../concepts/clustering.md)
