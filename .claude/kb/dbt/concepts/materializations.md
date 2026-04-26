# dbt Materializations

> **Purpose**: view/table/incremental/ephemeral mechanics and when to use each
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

A materialization controls how dbt persists a model's query result in the warehouse.
The right choice balances query performance (table vs view), build cost (full refresh
vs incremental), and storage. BigQuery's columnar engine and slot-based pricing make
incremental especially valuable for large fact tables.

## The Four Core Materializations

### view

```sql
-- dbt creates a BigQuery view (no physical data stored)
-- Always reads from upstream tables at query time
{{ config(materialized='view') }}

SELECT ...
FROM {{ ref('stg_crm__customers') }}
```
Use when: staging models, lightweight transformations, data freshness is critical.

### table

```sql
-- dbt runs CREATE OR REPLACE TABLE — full rebuild every run
{{ config(materialized='table') }}

SELECT ...
FROM {{ ref('int_orders_joined') }}
```
Use when: models that are queried frequently, dimensions, small-to-medium datasets.

### incremental

```sql
-- dbt appends or merges only new/changed rows
-- Uses is_incremental() macro to conditionally add a WHERE filter
{{ config(
    materialized = 'incremental',
    unique_key   = 'order_line_key',
    on_schema_change = 'append_new_columns'
) }}

SELECT
    order_line_key,
    order_id,
    ordered_at,
    net_amount
FROM {{ ref('stg_shopify__order_lines') }}

{% if is_incremental() %}
    -- Only load rows newer than the max loaded timestamp
    WHERE ordered_at > (SELECT MAX(ordered_at) FROM {{ this }})
{% endif %}
```
Use when: large fact tables, event logs, any table where full rebuild is costly.

### ephemeral

```sql
-- dbt inlines the model as a CTE — no physical object created
{{ config(materialized='ephemeral') }}

SELECT
    customer_id,
    COUNT(*) AS order_count
FROM {{ ref('stg_crm__orders') }}
GROUP BY 1
```
Use when: reusable subquery logic shared across multiple models; avoid for expensive
queries referenced by many downstream models (re-computed each time).

## Incremental Strategies (BigQuery)

```yaml
# dbt_project.yml or model config
models:
  my_project:
    marts:
      +materialized: incremental
      +incremental_strategy: merge   # append | merge | insert_overwrite | delete+insert
```

| Strategy | SQL Generated | Use Case |
|----------|--------------|---------|
| `append` | INSERT INTO | Immutable events (logs, raw clicks) |
| `merge` | MERGE (upsert) | Facts with corrections, SCD2-like updates |
| `insert_overwrite` | REPLACE PARTITION | Partition-aligned hourly/daily loads |
| `delete+insert` | DELETE + INSERT | When MERGE scan cost is too high |

## on_schema_change Behavior

```yaml
{{ config(
    materialized = 'incremental',
    on_schema_change = 'append_new_columns'  # ignore | fail | append_new_columns | sync_all_columns
) }}
```

| Setting | Behavior |
|---------|---------|
| `ignore` | Default; new columns in model are silently dropped |
| `fail` | Error on any schema difference |
| `append_new_columns` | Add new columns to target; existing columns unchanged |
| `sync_all_columns` | Add new + drop removed columns (destructive!) |

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| Staging model | `view` | No storage cost, always fresh |
| Dimension table | `table` | Full rebuild, fast queries |
| Large fact table | `incremental` + `merge` | Process delta only |
| Shared CTE | `ephemeral` | Inlined; no object created |

## Common Mistakes

### Wrong

```sql
-- incremental model without is_incremental() guard — full scan every run!
{{ config(materialized='incremental', unique_key='id') }}
SELECT * FROM {{ ref('stg_events') }}
-- WHERE clause missing: processes ALL rows every run — same cost as table!
```

### Correct

```sql
{{ config(materialized='incremental', unique_key='id') }}
SELECT * FROM {{ ref('stg_events') }}
{% if is_incremental() %}
WHERE event_at > (SELECT MAX(event_at) FROM {{ this }})
{% endif %}
```

## Related

- [model-layers.md](model-layers.md)
- [patterns/incremental-model.md](../patterns/incremental-model.md)
- [concepts/snapshots.md](snapshots.md)
