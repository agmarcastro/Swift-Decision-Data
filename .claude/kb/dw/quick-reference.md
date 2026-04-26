# Dimensional Modeling Quick Reference

> Fast lookup tables. For code examples, see linked files.
> **MCP Validated**: 2026-04-24

## Fact Table Type Decision Matrix

| Business Question | Fact Type | Grain Example | Key Trait |
|-------------------|-----------|---------------|-----------|
| "How many orders per day?" | Transaction | One row per order line | Sparse; additive |
| "What is inventory at month-end?" | Periodic Snapshot | One row per product per month | Regular cadence |
| "How long did the order take?" | Accumulating Snapshot | One row per order lifecycle | Multiple date FKs |

## Measure Additivity Rules

| Measure Type | SUM across dates | SUM across products | Example |
|--------------|-----------------|---------------------|---------|
| Additive | Yes | Yes | revenue, units_sold |
| Semi-additive | No | Yes | account_balance, inventory_qty |
| Non-additive | No | No | ratio, percentage, rate |

## SCD Type Selection Rules

| Question | Answer | Use SCD |
|----------|--------|---------|
| Does history matter? | No | Type 1 (overwrite) |
| Need full row history? | Yes | Type 2 (versioned rows) |
| Only current + one prior? | Yes | Type 3 (prior columns) |
| High-volume + audit separate? | Yes | Type 4 (mini-dimension) |
| Type 2 + current overwrite? | Yes | Type 6 (hybrid) |

## SCD2 Required Columns

| Column | Type | Purpose |
|--------|------|---------|
| `surrogate_key` | INTEGER | System-generated PK |
| `natural_key` | STRING/INT | Source system identifier |
| `valid_from` | DATE/TIMESTAMP | Row effective start |
| `valid_to` | DATE/TIMESTAMP | Row effective end (NULL = current) |
| `is_current` | BOOLEAN | Fast filter for active record |
| `row_hash` | STRING | MD5/SHA256 of tracked attributes |

## Grain Naming Convention

| Grain Level | Example Table Name | Grain Comment |
|-------------|--------------------|---------------|
| Order header | `fct_orders` | One row per order |
| Order line | `fct_order_lines` | One row per order line item |
| Daily snapshot | `fct_inventory_daily` | One row per product per calendar day |
| Monthly snapshot | `fct_account_monthly` | One row per account per month-end |

## Schema Pattern Quick Pick

| Scenario | Choose | Why |
|----------|--------|-----|
| BI tool with many joins | Star schema | Simpler queries, faster aggregations |
| Storage is critical | Snowflake schema | Normalized dims save space |
| Analytics / flat BI | One Big Table (OBT) | Zero-join mart, fastest reads |
| Shared dimensions | Conformed dimensions | Enables cross-process analysis |

## Common Pitfalls

| Don't | Do Instead |
|-------|-----------|
| Declare grain vaguely | Write grain as a comment: `-- grain: one row per order line` |
| Store metrics in dimensions | Put all numeric measures in fact tables |
| Use natural keys as fact FKs | Always join through surrogate keys |
| Mix SCD strategies per table | Pick one SCD type per dimension, document it |

## Related Documentation

| Topic | Path |
|-------|------|
| Star Schema DDL | `patterns/star-schema-design.md` |
| SCD2 MERGE | `patterns/scd2-implementation.md` |
| Full Index | `index.md` |
