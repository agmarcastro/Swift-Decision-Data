# Dimensional Modeling

> **Purpose**: Kimball methodology for designing analytical data warehouses
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

Dimensional modeling (Kimball methodology) structures data warehouse tables into facts
(numeric measurements of business events) and dimensions (descriptive context for those
events). The goal is query simplicity and analytical performance, not third-normal-form
storage efficiency. The bus matrix governs how dimensions are shared across subject areas.

## Core Principles

```
Business Process → Declare Grain → Identify Dimensions → Identify Facts

Example:
Process: Order fulfillment
Grain:   One row per order line item
Dims:    dim_customer, dim_product, dim_date, dim_store
Facts:   quantity_ordered, unit_price, extended_amount, discount_amount
```

## The Bus Matrix

The enterprise bus matrix is a grid mapping business processes (rows) to conformed
dimensions (columns). A checkmark means that process uses that dimension.

```
                        │ Date │ Customer │ Product │ Store │ Supplier │
────────────────────────┼──────┼──────────┼─────────┼───────┼──────────┤
fct_orders              │  ✓   │    ✓     │    ✓    │   ✓   │          │
fct_inventory_snapshot  │  ✓   │          │    ✓    │   ✓   │    ✓     │
fct_customer_service    │  ✓   │    ✓     │         │   ✓   │          │
```

## Grain Declaration

Grain is the single most important design decision. It defines exactly what one row
in a fact table represents. Declare it before anything else.

```sql
-- GOOD: Grain is explicit and atomic
-- grain: one row per order line item per fulfillment event
CREATE TABLE fct_order_lines (
    order_line_key  INT64   NOT NULL,  -- surrogate key
    order_date_key  INT64   NOT NULL,  -- FK to dim_date
    customer_key    INT64   NOT NULL,  -- FK to dim_customer
    product_key     INT64   NOT NULL,  -- FK to dim_product
    quantity_ordered INT64,
    unit_price       NUMERIC,
    extended_amount  NUMERIC           -- additive measure
);

-- BAD: Grain is ambiguous (header and line mixed)
CREATE TABLE fct_orders_bad (
    order_id       INT64,
    customer_id    INT64,
    product_id     INT64,
    order_total    NUMERIC,            -- header-level (not line-level)
    line_amount    NUMERIC             -- line-level — grain conflict!
);
```

## Conformed Dimensions

A conformed dimension has consistent column names, keys, and attribute values across
all fact tables that reference it. This enables cross-process drilldown and JOIN.

```sql
-- dim_date is conformed: all fct_ tables use the same date_key
SELECT
    d.calendar_year,
    d.month_name,
    SUM(o.extended_amount)   AS order_revenue,
    SUM(i.units_on_hand)     AS inventory_units
FROM dim_date d
LEFT JOIN fct_order_lines o   ON d.date_key = o.order_date_key
LEFT JOIN fct_inventory_daily i ON d.date_key = i.snapshot_date_key
GROUP BY 1, 2
ORDER BY 1, 2;
```

## Quick Reference

| Term | Definition | Key Rule |
|------|-----------|----------|
| Grain | What one fact row represents | Must be declared first |
| Conformed Dimension | Shared dim across fact tables | Same keys + attributes |
| Bus Matrix | Dim/fact coverage grid | Design tool, not deployed |
| Surrogate Key | System-generated integer PK | Never expose natural key as FK |
| Degenerate Dimension | Dim attribute stored in fact | No corresponding dim table |

## Common Mistakes

### Wrong

```sql
-- Grain not declared; mixing header and line attributes
CREATE TABLE fct_sales (
    order_id INT64,
    order_header_discount NUMERIC,  -- header grain
    line_quantity INT64              -- line grain → ambiguous!
);
```

### Correct

```sql
-- grain: one row per order line item
CREATE TABLE fct_order_lines (
    order_line_key INT64 NOT NULL,
    order_id       INT64 NOT NULL,  -- degenerate dimension (order header ref)
    line_quantity  INT64,
    line_amount    NUMERIC
);
```

## Related

- [fact-tables.md](fact-tables.md)
- [dimension-tables.md](dimension-tables.md)
- [star-vs-snowflake.md](star-vs-snowflake.md)
- [patterns/star-schema-design.md](../patterns/star-schema-design.md)
