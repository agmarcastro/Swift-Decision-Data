# dbt Model Layers

> **Purpose**: Staging → Intermediate → Marts layer contract; naming conventions
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

dbt projects are organized into layers of increasing semantic complexity. Each layer
has a strict contract: what SQL transformations are allowed, what it can reference,
and how it is named. This separation makes models reusable, testable, and predictable.
Violating layer contracts causes tightly coupled, untestable models.

## The Layer Contract

```
RAW / SOURCE
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STAGING  (stg_)                                                 │
│ - Source: source() references only                              │
│ - SQL: rename, cast, coalesce, basic null handling              │
│ - No: JOINs, aggregations, business logic                       │
│ - Materialization: view (default) or table for large sources    │
│ - 1 model per source table                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │ ref()
┌────────────────────────────▼────────────────────────────────────┐
│ INTERMEDIATE  (int_)                                            │
│ - Source: ref() to staging only                                 │
│ - SQL: JOINs, unions, pivots, deduplication, window functions   │
│ - No: direct source() references, final business metrics        │
│ - Materialization: view or ephemeral                            │
│ - Not exposed to BI tools                                       │
└────────────────────────────┬────────────────────────────────────┘
                             │ ref()
┌────────────────────────────▼────────────────────────────────────┐
│ MARTS  (fct_, dim_, obt_, rpt_)                                 │
│ - Source: ref() to staging or intermediate                      │
│ - SQL: final aggregation, surrogate key generation, SCD logic   │
│ - Materialization: table or incremental                         │
│ - Exposed to BI tools and downstream consumers                  │
└─────────────────────────────────────────────────────────────────┘
```

## Naming Conventions

```
stg_{source}__{entity}     stg_crm__customers
                           stg_shopify__orders
                           stg_postgres__payments

int_{entity}_{verb}        int_orders_joined
                           int_customer_order_summary
                           int_sessions_unioned

fct_{event_plural}         fct_orders
                           fct_order_lines
                           fct_sessions

dim_{entity}               dim_customer
                           dim_product
                           dim_date

obt_{subject}              obt_orders          (one big table mart)
rpt_{audience}_{subject}   rpt_finance_revenue (report-specific mart)
```

## Directory Structure

```
models/
├── staging/
│   ├── crm/
│   │   ├── _crm__sources.yml        # source definitions
│   │   ├── stg_crm__customers.sql
│   │   └── stg_crm__contacts.sql
│   └── shopify/
│       ├── _shopify__sources.yml
│       └── stg_shopify__orders.sql
├── intermediate/
│   └── int_orders_joined.sql
└── marts/
    ├── core/
    │   ├── fct_orders.sql
    │   ├── dim_customer.sql
    │   └── _core__models.yml        # tests and column docs
    └── finance/
        └── rpt_finance_revenue.sql
```

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| Raw source table | `stg_` model | One stg_ per source table |
| Multi-source join | `int_` model | Keep complexity out of marts |
| Business-ready dataset | `fct_` or `dim_` | Materialized table, tested |
| BI consumer dataset | `obt_` or `rpt_` | Flat, pre-joined |

## Common Mistakes

### Wrong

```sql
-- stg_ model with JOIN and business logic — layer violation
-- models/staging/stg_orders.sql
SELECT
    o.id,
    o.customer_id,
    c.loyalty_tier,                           -- JOIN in staging: wrong!
    o.amount * 0.9 AS discounted_amount       -- business logic: wrong!
FROM {{ source('raw', 'orders') }} o
JOIN {{ source('raw', 'customers') }} c ON o.customer_id = c.id
```

### Correct

```sql
-- stg_ model: only rename + cast
-- models/staging/stg_raw__orders.sql
SELECT
    id              AS order_id,
    customer_id,
    CAST(amount AS NUMERIC) AS order_amount,
    created_at      AS ordered_at
FROM {{ source('raw', 'orders') }}
```

## Related

- [sources-and-refs.md](sources-and-refs.md)
- [materializations.md](materializations.md)
- [patterns/staging-model.md](../patterns/staging-model.md)
