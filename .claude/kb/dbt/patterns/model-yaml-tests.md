# Model YAML Tests Pattern

> **Purpose**: Complete _models.yml with all standard tests: unique, not_null, relationships, accepted_values, dbt_utils
> **MCP Validated**: 2026-04-24

## When to Use

- Adding the standard test suite to a new mart model
- Creating a reference _models.yml that covers all test types
- Onboarding a new dbt project with a complete testing baseline

## Implementation

```yaml
# models/marts/core/_core__models.yml
# Complete testing example covering all standard test types

version: 2

models:

  # ── Fact Table Tests ─────────────────────────────────────────────────────
  - name: fct_order_lines
    description: >
      Order lines fact table. grain: one row per order line item.
      Incremental load via MERGE on order_line_key.
    config:
      tags: ['facts', 'core']

    columns:
      # Surrogate PK: always unique + not_null, always error severity
      - name: order_line_key
        description: "Surrogate primary key"
        tests:
          - unique:
              severity: error
          - not_null:
              severity: error

      # Foreign key with referential integrity test
      - name: order_date_key
        description: "FK to dim_date"
        tests:
          - not_null
          - relationships:
              to: ref('dim_date')
              field: date_key
              severity: warn     # warn so pipeline doesn't block on dim_date gaps

      - name: customer_key
        tests:
          - not_null
          - relationships:
              to: ref('dim_customer')
              field: customer_key
              where: "is_current = true"   # only check against current dim rows

      - name: product_key
        tests:
          - not_null
          - relationships:
              to: ref('dim_product')
              field: product_key

      # Enum / status column
      - name: order_status
        tests:
          - not_null
          - accepted_values:
              values: ['placed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded']
              severity: warn

      # Numeric range tests (dbt_utils)
      - name: quantity_ordered
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 1
              max_value: 10000
              inclusive: true

      - name: net_amount
        tests:
          - not_null
          - dbt_utils.accepted_range:
              min_value: 0
              inclusive: true

      - name: ordered_at
        tests:
          - not_null

  # ── Dimension Table Tests ────────────────────────────────────────────────
  - name: dim_customer
    description: "Customer dimension with SCD2 history."
    columns:
      - name: customer_key
        tests: [unique, not_null]

      - name: customer_natural_key
        tests: [not_null]

      - name: email
        tests:
          - not_null:
              severity: warn
          - dbt_utils.not_constant   # email must have more than one distinct value

      - name: loyalty_tier
        tests:
          - accepted_values:
              values: ['bronze', 'silver', 'gold', 'platinum']

      - name: valid_from
        tests: [not_null]

      - name: is_current
        tests: [not_null]

  # ── Staging Model Tests ──────────────────────────────────────────────────
  - name: stg_crm__customers
    description: "Staged customers from raw CRM. No joins, no business logic."
    columns:
      - name: customer_id
        tests: [unique, not_null]

      - name: email
        tests: [not_null]

      - name: loyalty_tier
        tests:
          - accepted_values:
              values: ['bronze', 'silver', 'gold', 'platinum']
              severity: warn

      - name: updated_at
        tests: [not_null]
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| PK tests | `error` severity | Duplicate PKs are always a blocking failure |
| FK tests | `warn` severity | Avoids pipeline failure on dim timing gaps |
| Accepted values | `warn` severity | New unexpected values alert without blocking |
| Range tests | `error` on PK; `warn` on measures | Tune per business criticality |

## Example Usage

```bash
# Validate test YAML syntax
dbt parse

# Run all tests in the core mart
dbt test --select marts.core

# Run only not_null tests
dbt test --select fct_order_lines,test_type:not_null

# Run relationship tests only (FK integrity)
dbt test --select fct_order_lines,test_type:relationships
```

## See Also

- [concepts/tests.md](../concepts/tests.md)
- [patterns/staging-model.md](staging-model.md)
- [patterns/incremental-model.md](incremental-model.md)
