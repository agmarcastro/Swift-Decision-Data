# dbt Tests

> **Purpose**: Generic tests, singular tests, dbt_utils tests, and severity levels
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

dbt tests are assertions that run against model data after each build. They catch data
quality issues (nulls, duplicates, broken FK relationships) before downstream consumers
see bad data. Two types exist: generic tests (reusable, declared in YAML) and singular
tests (bespoke SQL queries). Tests have configurable severity levels (warn vs error).

## Generic Tests (YAML-Declared)

```yaml
# models/marts/core/_core__models.yml
version: 2

models:
  - name: fct_order_lines
    description: "Order lines fact table. grain: one row per order line item."
    columns:
      - name: order_line_key
        description: "Surrogate PK"
        tests:
          - unique
          - not_null

      - name: order_date_key
        tests:
          - not_null
          - relationships:              # FK integrity test
              to: ref('dim_date')
              field: date_key

      - name: order_status
        tests:
          - accepted_values:
              values: ['placed', 'processing', 'shipped', 'delivered', 'cancelled']

      - name: net_amount
        tests:
          - not_null
          - dbt_utils.accepted_range:   # numeric range test
              min_value: 0
              inclusive: true
```

## The Four Core Generic Tests

```yaml
# unique: no duplicate values in column
- unique

# not_null: no NULL values
- not_null

# accepted_values: column values must be in this list
- accepted_values:
    values: ['active', 'inactive', 'pending']
    quote: true   # default true for strings; set false for numeric

# relationships: FK exists in referenced model
- relationships:
    to: ref('dim_customer')
    field: customer_key
```

## Singular Tests (Custom SQL)

Singular tests are SQL files in the `tests/` directory. The test fails if the query
returns any rows.

```sql
-- tests/assert_order_amount_positive.sql
-- Fails if any order has a negative net_amount (should be impossible)
SELECT
    order_line_key,
    net_amount
FROM {{ ref('fct_order_lines') }}
WHERE net_amount < 0
```

## Test Severity Levels

```yaml
models:
  - name: fct_order_lines
    columns:
      - name: net_amount
        tests:
          - not_null:
              severity: warn          # warn (continue run) vs error (fail run)
              warn_if: ">10"          # warn only if more than 10 rows fail
              error_if: ">1000"       # error if more than 1000 rows fail

      - name: order_line_key
        tests:
          - unique:
              severity: error         # always fail on duplicate PKs
```

## Quick Reference

| Input | Output | Notes |
|-------|--------|-------|
| Surrogate PK column | `unique` + `not_null` | Always both, always error severity |
| FK column | `relationships` | Validates referential integrity |
| Status/type column | `accepted_values` | Catch unexpected codes early |
| Numeric measure | `dbt_utils.accepted_range` | Prevent negative quantities |
| Custom business rule | Singular test SQL | Returns rows on failure |

## Common Mistakes

### Wrong

```yaml
# Testing only PK, ignoring FK and range tests
- name: fct_order_lines
  columns:
    - name: order_line_key
      tests:
        - unique
        - not_null
    # No tests on other columns — silent data quality issues
```

### Correct

```yaml
# Test all critical columns
- name: fct_order_lines
  columns:
    - name: order_line_key
      tests: [unique, not_null]
    - name: customer_key
      tests: [not_null, {relationships: {to: ref('dim_customer'), field: customer_key}}]
    - name: net_amount
      tests: [not_null, {dbt_utils.accepted_range: {min_value: 0}}]
```

## Related

- [patterns/model-yaml-tests.md](../patterns/model-yaml-tests.md)
- [sources-and-refs.md](sources-and-refs.md)
