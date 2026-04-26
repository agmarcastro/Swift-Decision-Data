# dbt Snapshots

> **Purpose**: dbt snapshot mechanics, strategies, invalidate_hard_deletes, downstream consumption
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

dbt snapshots are a built-in SCD Type 2 mechanism. They read a source model or table,
detect changes by comparing row hashes or timestamps, and maintain a history table with
`dbt_valid_from`, `dbt_valid_to`, `dbt_scd_id`, and `dbt_updated_at` columns. The
snapshot table then feeds downstream `dim_` models via `ref()`.

## Snapshot Strategies

Two strategies control how dbt detects changes:

### timestamp strategy

```sql
-- snapshots/snp_customers.sql
{% snapshot snp_customers %}

{{
    config(
        target_schema = 'snapshots',
        strategy       = 'timestamp',
        unique_key     = 'customer_id',
        updated_at     = 'updated_at',     -- source column tracking last change
        invalidate_hard_deletes = true     -- close rows for deleted source records
    )
}}

SELECT
    customer_id,
    full_name,
    email,
    loyalty_tier,
    updated_at
FROM {{ source('crm', 'customers') }}

{% endsnapshot %}
```

### check strategy

```sql
-- Use when source has no reliable updated_at column
{% snapshot snp_products %}

{{
    config(
        target_schema  = 'snapshots',
        strategy       = 'check',
        unique_key     = 'product_id',
        check_cols     = ['product_name', 'category_name', 'unit_cost'],
        invalidate_hard_deletes = true
    )
}}

SELECT
    product_id,
    product_name,
    category_name,
    unit_cost
FROM {{ source('erp', 'products') }}

{% endsnapshot %}
```

## Generated Columns

dbt automatically adds these columns to every snapshot table:

| Column | Type | Description |
|--------|------|-------------|
| `dbt_scd_id` | STRING | MD5 hash uniquely identifying each version row |
| `dbt_updated_at` | TIMESTAMP | When dbt last processed this row |
| `dbt_valid_from` | TIMESTAMP | When this version became effective |
| `dbt_valid_to` | TIMESTAMP | When this version expired (NULL = current) |

## invalidate_hard_deletes

When `invalidate_hard_deletes = true`, rows that disappear from the source are closed
by setting `dbt_valid_to` to the current timestamp and are no longer returned as
current records. Without this, deleted source rows remain open forever.

## Consuming Snapshots in Downstream Models

```sql
-- models/marts/core/dim_customer.sql
-- Converts snapshot into clean dim_ with is_current flag and surrogate key
{{ config(materialized='table') }}

SELECT
    -- Generate stable surrogate key from natural key + valid_from
    {{ dbt_utils.generate_surrogate_key(['customer_id', 'dbt_valid_from']) }}
        AS customer_key,

    customer_id             AS customer_natural_key,
    full_name,
    email,
    loyalty_tier,

    CAST(dbt_valid_from AS DATE)    AS valid_from,
    CAST(dbt_valid_to   AS DATE)    AS valid_to,
    dbt_valid_to IS NULL            AS is_current

FROM {{ ref('snp_customers') }}
```

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| Source with `updated_at` | `timestamp` strategy | Fastest; low compute |
| Source without `updated_at` | `check` strategy | Hash-based; specify cols |
| Deleted source rows | `invalidate_hard_deletes = true` | Closes version row |
| Snapshot → dim_ | Filter `dbt_valid_to IS NULL` | Current records only |

## Common Mistakes

### Wrong

```sql
-- Querying snapshot directly in BI tool — raw snapshot columns exposed
SELECT * FROM snapshots.snp_customers WHERE dbt_valid_to IS NULL
-- dbt internal column names leak to BI layer
```

### Correct

```sql
-- Always wrap snapshot in a dim_ model with clean column names
SELECT
    customer_key,
    customer_natural_key,
    loyalty_tier,
    valid_from,
    valid_to,
    is_current
FROM {{ ref('dim_customer') }}
-- BI tools see clean, stable column names
```

## Related

- [patterns/snapshot-to-dim.md](../patterns/snapshot-to-dim.md)
- [concepts/materializations.md](materializations.md)
- [concepts/model-layers.md](model-layers.md)
