# Dimension Tables

> **Purpose**: Dimension types, SCD overview, and special dimension patterns
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

Dimension tables provide the descriptive context — the "who, what, where, when, why,
and how" — of business events stored in fact tables. They are wide (many attributes)
and relatively small. Dimension design determines the quality of filtering, grouping,
and labeling in BI reports.

## Static vs Slowly Changing Dimensions

```
STATIC DIMENSION             SLOWLY CHANGING DIMENSION (SCD)
─────────────────────────    ────────────────────────────────
Attributes never change      Attributes change over time

Examples:                    Examples:
- dim_date (calendar)        - dim_customer (address changes)
- dim_geography (fixed)      - dim_product (price/category)
- dim_currency               - dim_employee (dept transfers)
```

## SCD Type Overview

```
SCD TYPE │ STRATEGY          │ HISTORY │ COMPLEXITY │ STORAGE
─────────┼───────────────────┼─────────┼────────────┼────────
Type 1   │ Overwrite value   │ Lost    │ Low        │ Minimal
Type 2   │ New row + version │ Full    │ Medium     │ High
Type 3   │ Prior value col   │ 1 prior │ Low        │ Minimal
Type 4   │ Mini-dimension    │ Full    │ High       │ Medium
Type 6   │ Type 1+2+3 hybrid │ Full    │ High       │ High
```

## Special Dimension Types

### Junk Dimension

Combines multiple low-cardinality flags/indicators into one dimension to avoid
many narrow columns in the fact table.

```sql
-- Instead of 20 flag columns in the fact table, bundle them
CREATE TABLE dim_order_flags (
    order_flags_key    INT64   NOT NULL,  -- surrogate key
    is_promotional     BOOLEAN,
    is_rush_order      BOOLEAN,
    is_gift            BOOLEAN,
    is_subscription    BOOLEAN,
    payment_method     STRING,            -- 'credit','debit','paypal','apple_pay'
    fulfillment_type   STRING             -- 'standard','express','store_pickup'
);
```

### Degenerate Dimension

An attribute that has dimension-like qualities but belongs in the fact table because
there is no other attribute to justify a separate dimension table.

```sql
-- order_id is a degenerate dimension: it's the source key, not a FK to any dim table
CREATE TABLE fct_order_lines (
    order_line_key  INT64   NOT NULL,
    order_id        STRING  NOT NULL,  -- degenerate dim: transaction number
    invoice_number  STRING,            -- degenerate dim: billing reference
    ...
);
```

### Role-Playing Dimension

A single physical dimension table used multiple times in the same fact table under
different aliases (different business roles).

```sql
-- dim_date is role-played as three different date roles in one fact table
SELECT
    order_date.calendar_year    AS order_year,
    ship_date.month_name        AS ship_month,
    delivery_date.day_of_week   AS delivery_day
FROM fct_order_lines ol
JOIN dim_date order_date    ON ol.order_date_key    = order_date.date_key
JOIN dim_date ship_date     ON ol.ship_date_key     = ship_date.date_key
JOIN dim_date delivery_date ON ol.delivery_date_key = delivery_date.date_key;
```

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| Low-cardinality flag columns | `dim_junk_flags` | Bundle 3-20 flags |
| Source transaction number | Degenerate dim in fact | No separate dim table |
| Same dim, multiple roles | Role-play with aliases | One physical table |
| Attribute that rarely changes | SCD Type 1 | Fast + simple |
| Attribute with full history | SCD Type 2 | Add valid_from/to/is_current |

## Common Mistakes

### Wrong

```sql
-- 15 separate flag columns in the fact table pollutes the schema
CREATE TABLE fct_orders (
    ...
    is_promotional     BOOLEAN,
    is_rush_order      BOOLEAN,
    is_gift            BOOLEAN,
    is_subscription    BOOLEAN
    -- grows unbounded as new flags added
);
```

### Correct

```sql
-- Bundle flags into dim_order_flags; use single FK in fact table
CREATE TABLE fct_orders (
    ...
    order_flags_key    INT64  -- FK → dim_order_flags.order_flags_key
);
```

## Related

- [scd-types.md](scd-types.md)
- [fact-tables.md](fact-tables.md)
- [patterns/star-schema-design.md](../patterns/star-schema-design.md)
- [patterns/scd2-implementation.md](../patterns/scd2-implementation.md)
