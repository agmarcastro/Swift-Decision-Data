# Sources and Refs

> **Purpose**: source() vs ref(), freshness checks, source YAML, and why never hardcode table names
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

`source()` and `ref()` are dbt's compile-time dependency declarations. They replace
raw table names so dbt can build a DAG, swap environments automatically, and track
lineage. Never use hardcoded table names in models — it bypasses dbt's graph resolution
and breaks lineage documentation, environment switching, and CI testing.

## source() — For Raw Tables

`source()` references tables that dbt does not create. It maps a logical source name
to a physical schema and table in the warehouse.

```yaml
# models/staging/crm/_crm__sources.yml
version: 2

sources:
  - name: crm                          # logical source name
    database: my_project               # GCP project
    schema: raw_crm                    # BigQuery dataset
    loaded_at_field: _loaded_at        # column used for freshness
    freshness:
      warn_after:  {count: 6,  period: hour}
      error_after: {count: 24, period: hour}
    tables:
      - name: customers
        description: "Raw customer records from CRM export"
        identifier: customers_raw      # actual BQ table name (if different)
      - name: orders
        description: "Raw orders from CRM"
        loaded_at_field: created_at    # override freshness field per-table
        freshness:
          warn_after:  {count: 1, period: hour}
          error_after: {count: 4, period: hour}
```

```sql
-- models/staging/crm/stg_crm__customers.sql
SELECT
    id              AS customer_id,
    full_name,
    email
FROM {{ source('crm', 'customers') }}   -- resolves to raw_crm.customers_raw
-- dbt compiles to: `my_project`.`raw_crm`.`customers_raw`
```

## ref() — For dbt Models

`ref()` references models dbt creates. It resolves to the correct schema per target
environment (dev/prod) and registers the dependency in the DAG.

```sql
-- models/intermediate/int_orders_joined.sql
SELECT
    o.order_id,
    o.ordered_at,
    c.customer_id,
    c.loyalty_tier
FROM {{ ref('stg_crm__orders') }}    AS o   -- dep: stg_crm__orders
JOIN {{ ref('stg_crm__customers') }} AS c   -- dep: stg_crm__customers
    ON o.customer_id = c.customer_id

-- In dev: resolves to dev_username.stg_crm__orders
-- In prod: resolves to prod.stg_crm__orders
-- dbt automatically runs deps first
```

## Freshness Check

Run `dbt source freshness` to check all sources with freshness config. Fails CI if
source data is stale before expensive model runs.

```bash
# Check freshness of all sources
dbt source freshness

# Check specific source
dbt source freshness --select source:crm
```

## Why Never Hardcode Table Names

```sql
-- WRONG: hardcoded table name
SELECT * FROM `my_project.raw_crm.customers_raw`
-- Breaks in dev environment
-- Not in DAG — lineage is invisible
-- No freshness check
-- Cannot be overridden by --target

-- CORRECT: use source()
SELECT * FROM {{ source('crm', 'customers') }}
-- Works in all environments
-- In the DAG — lineage is visible in dbt docs
-- Freshness checks apply
```

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| `source('crm', 'customers')` | Physical table reference | Use in stg_ models only |
| `ref('stg_crm__customers')` | Model reference | Use in all non-staging models |
| `dbt source freshness` | Freshness status report | Run before model run in CI |

## Common Mistakes

### Wrong

```sql
-- Using source() in a mart model (should use ref() to staging)
SELECT * FROM {{ source('crm', 'customers') }}  -- only valid in stg_ layer
```

### Correct

```sql
-- Use ref() to the staging model in marts
SELECT * FROM {{ ref('stg_crm__customers') }}
```

## Related

- [model-layers.md](model-layers.md)
- [patterns/staging-model.md](../patterns/staging-model.md)
- [tests.md](tests.md)
