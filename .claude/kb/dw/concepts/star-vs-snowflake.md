# Star vs Snowflake Schema

> **Purpose**: Trade-offs between denormalized and normalized schemas; decision guide
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

Star schema denormalizes dimensions into flat, wide tables joined directly to the fact
table — optimized for query simplicity and performance. Snowflake schema normalizes
dimension attributes into additional tables — optimized for storage efficiency and
consistency. Modern columnar warehouses (BigQuery, Redshift, Snowflake) favor star
schemas because storage is cheap and JOIN overhead is significant.

## The Pattern

```
STAR SCHEMA                        SNOWFLAKE SCHEMA
───────────────────────────────    ─────────────────────────────────
fct_order_lines                    fct_order_lines
  ├── dim_customer (flat)            ├── dim_customer
  │   full_name                      │   customer_key
  │   city                           │   city_key → dim_city
  │   state                          │               city_name
  │   country                        │               state_key → dim_state
  │   loyalty_tier                   │                           country_key
  │   ...20 more attrs               │                           ...
  ├── dim_product (flat)             ├── dim_product
  └── dim_date (flat)                │   product_key
                                     │   category_key → dim_category
                                     └── dim_date
```

## Trade-off Comparison

| Dimension | Star | Snowflake |
|-----------|------|-----------|
| Query complexity | Simple (1 join per dim) | Complex (cascading joins) |
| Query performance | Faster (fewer joins) | Slower (more joins) |
| Storage size | Larger (denormalized) | Smaller (normalized) |
| BI tool compatibility | Excellent (flat dims) | Needs relationship config |
| Data redundancy | Higher (repeated values) | Lower |
| Update anomalies | Possible (if updated) | Prevented by normalization |
| ETL complexity | Simpler | More complex |

## When to Use Star Schema

```sql
-- Best for: BI tools (Looker, Tableau, Power BI), analyst self-service, fast aggregations
-- dim_customer is flat — no further joins needed
SELECT
    c.loyalty_tier,
    c.state,
    SUM(ol.extended_amount) AS revenue
FROM fct_order_lines ol
JOIN dim_customer c ON ol.customer_key = c.customer_key
GROUP BY 1, 2;
-- Two-table JOIN, simple and fast
```

## When to Use Snowflake Schema

```sql
-- Best for: storage-critical environments, strict data governance, DW feeds OLTP
-- Product category is normalized into dim_product_category
SELECT
    pc.category_name,
    SUM(ol.extended_amount) AS revenue
FROM fct_order_lines ol
JOIN dim_product p      ON ol.product_key    = p.product_key
JOIN dim_category pc    ON p.category_key    = pc.category_key  -- extra join
GROUP BY 1;
-- More joins, but category metadata is maintained in one place
```

## One Big Table (OBT) — The Flat Extreme

```sql
-- OBT: pre-join everything into a single wide mart table
-- Zero joins at query time; best for embedded analytics, Looker PDTs
SELECT
    order_year,
    customer_loyalty_tier,
    product_category_name,
    SUM(extended_amount) AS revenue
FROM mart_orders_obt  -- everything already joined in
GROUP BY 1, 2, 3;
```

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| BI tool with analyst users | Star schema | Minimize required SQL knowledge |
| Storage-constrained DW | Snowflake schema | Normalize repeated string attrs |
| Pre-aggregated BI dashboard | OBT mart | Join done once at build time |
| Cross-process analysis | Conformed dims in star | Share dim across fact tables |

## Common Mistakes

### Wrong

```sql
-- Snowflaking a dimension that has low cardinality and rarely changes
-- city has only 500 rows — the JOIN overhead exceeds storage savings
JOIN dim_city ON dim_customer.city_key = dim_city.city_key  -- unnecessary
```

### Correct

```sql
-- Flatten low-cardinality attributes directly into the dimension
-- city, state, country are denormalized into dim_customer
SELECT c.city, c.state, c.country FROM dim_customer c;  -- no extra join
```

## Related

- [dimensional-modeling.md](dimensional-modeling.md)
- [patterns/star-schema-design.md](../patterns/star-schema-design.md)
- [patterns/one-big-table.md](../patterns/one-big-table.md)
