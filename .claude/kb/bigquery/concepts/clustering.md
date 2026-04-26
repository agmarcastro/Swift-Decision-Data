# BigQuery Clustering

> **Purpose**: Cluster key selection, cardinality rules, interaction with partitioning
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

Clustering physically sorts data within each partition (or across the table) by the
specified columns. BigQuery uses this ordering to skip data blocks that don't match
query filters — called block pruning. Unlike partitioning (coarse-grained), clustering
provides fine-grained pruning within a partition. Clustering and partitioning are
complementary and should usually be combined on large tables.

## Cluster Key Selection Rules

```
RULE 1: Column order matters — most-filtered column first
RULE 2: Max 4 cluster columns
RULE 3: Choose columns frequently used in WHERE / JOIN ON clauses
RULE 4: Sweet spot cardinality: 100 – 100,000 distinct values
RULE 5: Avoid high-cardinality unique IDs (UUIDs) as first cluster column
RULE 6: Integers cluster faster than long strings
```

## The Pattern

```sql
-- GOOD: partition by date, cluster by the next most common filters
CREATE TABLE `project.dw.fct_order_lines` (
    order_line_key  INT64     NOT NULL,
    order_date      DATE      NOT NULL,
    customer_id     INT64     NOT NULL,   -- ~500k distinct values ← good cardinality
    product_id      INT64     NOT NULL,   -- ~10k distinct values ← good cardinality
    store_id        INT64     NOT NULL,   -- ~200 distinct values ← good cardinality
    order_status    STRING,
    net_amount      NUMERIC
)
PARTITION BY order_date           -- coarse filter: entire day pruned
CLUSTER BY                        -- fine filter: block pruning within day
    customer_id,                  -- most common join key → position 1
    product_id,                   -- second most common filter → position 2
    store_id;                     -- third → position 3
```

## Cardinality Guidelines

```
Too low (< 100 distinct values):    Minimal pruning benefit; all blocks likely hit
                                    Example: is_active (2 values), order_status (6 values)

Sweet spot (100 – 100,000):         Strong pruning; blocks naturally align to distinct values
                                    Example: product_id, store_id, postal_code

Too high (> 1M distinct values):    Each block contains few matching rows; overhead increases
                                    Example: UUID primary keys, exact timestamps
                                    → Use as partition key or join key instead
```

## Interaction with Partitioning

```sql
-- Partition pruning happens first (eliminates whole partitions)
-- Cluster pruning happens next (eliminates blocks within remaining partitions)

-- Efficient: partition filter + cluster filter
SELECT SUM(net_amount)
FROM `project.dw.fct_order_lines`
WHERE order_date BETWEEN '2024-01-01' AND '2024-01-31'  -- partition pruning
  AND customer_id = 12345                                -- cluster pruning
  AND product_id  IN (101, 202, 303);                   -- cluster pruning

-- Less efficient: cluster filter without partition filter (scans all partitions)
SELECT SUM(net_amount)
FROM `project.dw.fct_order_lines`
WHERE customer_id = 12345;   -- cluster pruning only; all partitions scanned
```

## When Clustering Beats Partitioning Alone

```sql
-- Problem: you need to filter by customer_id and product_id frequently,
-- but your table is already partitioned by date.
-- Partitioning by customer_id would require INTEGER RANGE and is awkward.
-- Solution: keep DATE partition + add cluster on customer_id, product_id.

-- Clustering gives you sub-partition pruning without changing the partition key.
-- Result: 90%+ bytes scanned reduction for typical customer/product lookups.
```

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| Most common WHERE column | Cluster position 1 | Always highest impact first |
| Second most common filter | Cluster position 2 | |
| JOIN key (FK to dimension) | Include in cluster | Speeds star schema joins |
| UUID / hash column | Avoid as cluster | Too high cardinality |
| Boolean / low-card col | Avoid as cluster | Too low cardinality |

## Common Mistakes

### Wrong

```sql
-- Clustering on UUID (unique per row) — no pruning benefit
CLUSTER BY order_uuid,  -- 10M distinct values → no block pruning
           created_at   -- timestamp → too high cardinality
```

### Correct

```sql
-- Cluster on dimension FK columns — good cardinality and match query patterns
CLUSTER BY customer_id, product_id, store_id
```

## Related

- [partitioning.md](partitioning.md)
- [patterns/partitioned-clustered-table.md](../patterns/partitioned-clustered-table.md)
- [slots-and-cost.md](slots-and-cost.md)
