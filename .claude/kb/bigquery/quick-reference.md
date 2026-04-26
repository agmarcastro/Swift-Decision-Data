# BigQuery Quick Reference

> Fast lookup tables. For code examples, see linked files.
> **MCP Validated**: 2026-04-24

## Partitioning Strategy Decision Table

| Data Pattern | Partition Type | Column/Field | Notes |
|-------------|---------------|-------------|-------|
| Event time data | `TIMESTAMP` / `DATE` | `event_at`, `created_at` | Most common for facts |
| Daily batch loads | `DATE` | `_loaded_at` | Simple ingestion-time pattern |
| Integer ranges | `INT64 RANGE` | `account_id`, `shard_id` | For non-time sharding |
| No good partition key | Ingestion-time | `_PARTITIONTIME` | Fallback; less optimal |

## Partition Types DDL Options

| Type | DDL Syntax | Granularity Options |
|------|-----------|---------------------|
| Date | `PARTITION BY date_col` | DAY (default) |
| Timestamp | `PARTITION BY TIMESTAMP_TRUNC(ts_col, DAY)` | HOUR, DAY, MONTH, YEAR |
| Integer range | `PARTITION BY RANGE_BUCKET(int_col, GENERATE_ARRAY(0, 10000, 100))` | Custom buckets |

## Cluster Column Ordering Rules

| Rule | Guidance |
|------|---------|
| Max columns | 4 cluster columns |
| Column order | Most selective filter first, then JOIN keys |
| Data type | Low-variance strings, INT64 keys; avoid high-cardinality UUID |
| Partition + cluster | Partition first (date), then cluster (customer_id, product_id) |
| Cardinality sweet spot | 100–100,000 distinct values per cluster column |

## BigQuery DDL OPTIONS Reference

| Option | Type | Description |
|--------|------|-------------|
| `description` | STRING | Table/column description shown in UI |
| `partition_expiration_days` | INT64 | Auto-delete partitions older than N days |
| `require_partition_filter` | BOOL | Force queries to include partition predicate |
| `labels` | MAP | Key-value tags for cost attribution |
| `kms_key_name` | STRING | CMEK encryption key |
| `friendly_name` | STRING | Display name in BigQuery UI |

## Cost Control Quick Picks

| Goal | Method |
|------|--------|
| Preview query cost | `bq query --dry_run --use_legacy_sql=false 'SELECT ...'` |
| Prevent runaway queries | `SET @@query_label = "team:analytics,job:daily_report"` |
| Enforce partition filter | `OPTIONS (require_partition_filter = true)` |
| Avoid SELECT * | Explicitly list columns; columnar storage skips unread cols |
| Approximate distinct count | `APPROX_COUNT_DISTINCT(user_id)` instead of `COUNT(DISTINCT ...)` |

## On-Demand vs Capacity Slots

| Dimension | On-Demand | Capacity (Editions) |
|-----------|-----------|---------------------|
| Pricing | Per TB scanned | Per slot-hour reserved |
| Best for | Unpredictable workloads | Consistent high-volume |
| Burst | Automatic | Up to committed slots |
| Cost control | Limit by bytes billed | Predictable monthly cost |
| Minimum | None | 100 slots (standard) |

## Common Pitfalls

| Don't | Do Instead |
|-------|-----------|
| `SELECT *` on large tables | Select only required columns |
| Query without partition filter | Use `WHERE date_col = ...` on partition col |
| Cluster on UUID/hash column | Use lower-cardinality business keys |
| Run MERGE without dedup CTE | Deduplicate source before MERGE |

## Related Documentation

| Topic | Path |
|-------|------|
| Partitioned Table DDL | `patterns/partitioned-clustered-table.md` |
| Cost Optimization | `patterns/cost-optimized-query.md` |
| Full Index | `index.md` |
