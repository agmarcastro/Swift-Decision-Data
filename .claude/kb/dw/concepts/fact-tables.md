# Fact Tables

> **Purpose**: Types of fact tables, measure additivity, and key design rules
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

Fact tables store the quantitative measurements of business events. Each row corresponds
to a single measurement event at a declared grain level. Fact tables are narrow (mostly
foreign keys and numeric measures) and very wide (many rows). The three types differ in
how they capture time and state.

## The Three Fact Table Types

```
TRANSACTION FACT         PERIODIC SNAPSHOT          ACCUMULATING SNAPSHOT
───────────────────      ──────────────────────     ─────────────────────────
One row per event        One row per entity          One row per lifecycle
Sparse, grows forever    per time period             Updated in place
e.g. order line          e.g. monthly inventory      e.g. order fulfillment

Columns:                 Columns:                    Columns:
- event_date_key         - snapshot_date_key         - order_date_key
- dims...                - entity_key                - pick_date_key
- qty, amount            - balance, qty              - ship_date_key
                                                     - deliver_date_key
                                                     - days_to_ship (lag)
```

## Measure Additivity

```sql
-- ADDITIVE: safe to SUM across any dimension
SELECT SUM(extended_amount)   -- revenue: sum by date, product, region — all valid
FROM fct_order_lines;

-- SEMI-ADDITIVE: sum across products OK, NOT across dates
-- (account balance at month-end shouldn't be summed across months)
SELECT
    snapshot_date_key,
    SUM(balance_amount) AS total_portfolio  -- valid: sum across accounts on one date
FROM fct_account_monthly
WHERE snapshot_date_key = 20240131
GROUP BY 1;

-- NON-ADDITIVE: never SUM, always compute
-- (profit_margin % cannot be summed)
SELECT
    SUM(profit_amount) / NULLIF(SUM(revenue_amount), 0) AS margin_pct
FROM fct_order_lines;
```

## Surrogate vs Natural Keys

```sql
-- Surrogate key (INT64): system-generated, stable, fast JOIN
-- Natural key (STRING): source system ID, used for lineage only
CREATE TABLE fct_order_lines (
    -- Surrogate key — PK for this fact row
    order_line_key    INT64   NOT NULL,

    -- Foreign keys to dimension surrogates (fast INT64 joins)
    order_date_key    INT64   NOT NULL,   -- FK → dim_date.date_key
    customer_key      INT64   NOT NULL,   -- FK → dim_customer.customer_key
    product_key       INT64   NOT NULL,   -- FK → dim_product.product_key
    store_key         INT64   NOT NULL,   -- FK → dim_store.store_key

    -- Degenerate dimensions (stored in fact, no dim table)
    order_id          STRING  NOT NULL,   -- source order ID
    order_line_number INT64   NOT NULL,   -- line position

    -- Additive measures
    quantity_ordered  INT64,
    unit_price        NUMERIC,
    extended_amount   NUMERIC,
    discount_amount   NUMERIC,

    -- Audit
    _loaded_at        TIMESTAMP
);
```

## Accumulating Snapshot Example

```sql
-- grain: one row per order, updated as order moves through fulfillment stages
CREATE TABLE fct_order_fulfillment (
    order_fulfillment_key   INT64   NOT NULL,
    order_natural_key       STRING  NOT NULL,

    -- Multiple date foreign keys (one per lifecycle milestone)
    order_placed_date_key   INT64,
    payment_date_key        INT64,
    pick_date_key           INT64,
    ship_date_key           INT64,
    delivery_date_key       INT64,
    return_date_key         INT64,

    -- Lag measures (semi-additive; use AVG not SUM)
    days_to_payment         INT64,
    days_to_ship            INT64,
    days_to_delivery        INT64,

    -- Status flag
    order_status            STRING   -- 'placed','shipped','delivered','returned'
);
```

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| Business event (transaction) | Transaction fact row | Append-only |
| Period-end state | Periodic snapshot row | Upsert by entity+period key |
| Lifecycle entity | Accumulating snapshot row | UPDATE milestone date keys |

## Common Mistakes

### Wrong

```sql
-- Storing a non-additive measure that will be incorrectly SUMmed
INSERT INTO fct_daily_sales
SELECT date_id, SUM(revenue) / COUNT(orders) AS avg_order_value  -- non-additive!
```

### Correct

```sql
-- Store additive components; compute ratio in the BI layer
INSERT INTO fct_daily_sales
SELECT date_id, SUM(revenue) AS total_revenue, COUNT(orders) AS order_count
-- BI tool computes: total_revenue / order_count = avg_order_value
```

## Related

- [dimensional-modeling.md](dimensional-modeling.md)
- [dimension-tables.md](dimension-tables.md)
- [patterns/star-schema-design.md](../patterns/star-schema-design.md)
