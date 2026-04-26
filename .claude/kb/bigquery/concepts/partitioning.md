# BigQuery Partitioning

> **Purpose**: Partition types, strategies, expiration, and require_partition_filter
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

Partitioning divides a BigQuery table into segments based on a column value. When a
query filters on the partition column, BigQuery skips entire partitions that don't
match — called partition pruning. This reduces bytes scanned and therefore cost and
latency. Partitioning is the highest-impact optimization for large tables.

## Partition by DATE or TIMESTAMP

The most common pattern for event-driven fact tables.

```sql
-- TIMESTAMP partition with DAY granularity (default and most common)
CREATE TABLE `project.dw.fct_events` (
    event_id     STRING    NOT NULL,
    user_id      INT64     NOT NULL,
    event_at     TIMESTAMP NOT NULL,
    event_type   STRING,
    payload      JSON
)
PARTITION BY TIMESTAMP_TRUNC(event_at, DAY)
OPTIONS (
    description                = 'Events fact table. Partitioned by event day.',
    partition_expiration_days  = 365,    -- auto-delete partitions older than 1 year
    require_partition_filter   = true    -- queries MUST include a partition predicate
);

-- DATE partition (simpler; no TIMESTAMP_TRUNC needed)
CREATE TABLE `project.dw.fct_orders` (
    order_id    STRING  NOT NULL,
    order_date  DATE    NOT NULL,
    amount      NUMERIC
)
PARTITION BY order_date;

-- MONTH granularity (for lower-frequency snapshots)
CREATE TABLE `project.dw.fct_account_monthly` (
    account_id      INT64  NOT NULL,
    snapshot_month  DATE   NOT NULL,
    balance         NUMERIC
)
PARTITION BY DATE_TRUNC(snapshot_month, MONTH);
```

## Ingestion-Time Partitioning

When no suitable time column exists, BigQuery uses the load timestamp automatically.
Reference with `_PARTITIONDATE` or `_PARTITIONTIME` pseudo-columns.

```sql
CREATE TABLE `project.raw.events_raw` (
    raw_payload STRING
)
PARTITION BY _PARTITIONDATE;   -- partitioned by load date automatically

-- Query using pseudo-column
SELECT * FROM `project.raw.events_raw`
WHERE _PARTITIONDATE = '2024-06-15';
```

## INTEGER RANGE Partitioning

For non-time sharding on integer columns (account IDs, shard keys).

```sql
CREATE TABLE `project.dw.fct_transactions` (
    transaction_id INT64   NOT NULL,
    account_id     INT64   NOT NULL,
    amount         NUMERIC
)
PARTITION BY RANGE_BUCKET(
    account_id,
    GENERATE_ARRAY(0, 1000000, 10000)   -- 100 buckets of 10,000 IDs each
);
```

## Partition Expiration

```sql
-- Partitions older than 90 days are automatically deleted
OPTIONS (partition_expiration_days = 90)

-- Remove expiration (set to NULL to keep forever)
ALTER TABLE `project.dw.fct_events`
SET OPTIONS (partition_expiration_days = NULL);
```

## require_partition_filter

Prevents accidental full-table scans by requiring a WHERE clause on the partition column.

```sql
OPTIONS (require_partition_filter = true)

-- Query WITHOUT filter → error:
-- "Cannot query over table without a filter on partitioned column event_at"

-- Query WITH filter → OK:
SELECT * FROM `project.dw.fct_events`
WHERE event_at BETWEEN '2024-01-01' AND '2024-01-31';
```

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| Event table with timestamps | `PARTITION BY TIMESTAMP_TRUNC(event_at, DAY)` | Most common |
| Daily batch loaded table | `PARTITION BY _PARTITIONDATE` | Ingestion-time |
| Integer-sharded table | `PARTITION BY RANGE_BUCKET(id, ...)` | Non-time use case |
| Auto-expire old data | `partition_expiration_days = N` | Reduces storage cost |

## Common Mistakes

### Wrong

```sql
-- Partitioning on a STRING column — not supported!
PARTITION BY event_type  -- ERROR: STRING column not supported
```

### Correct

```sql
-- Always partition on DATE, TIMESTAMP, or INT64 column
PARTITION BY TIMESTAMP_TRUNC(event_at, DAY)
```

## Related

- [clustering.md](clustering.md)
- [patterns/partitioned-clustered-table.md](../patterns/partitioned-clustered-table.md)
- [slots-and-cost.md](slots-and-cost.md)
