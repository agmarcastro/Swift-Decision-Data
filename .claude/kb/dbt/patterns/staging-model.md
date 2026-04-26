# Staging Model Pattern

> **Purpose**: Canonical stg_ model — source declaration, column rename/cast, no joins, no business logic
> **MCP Validated**: 2026-04-24

## When to Use

- Creating the first dbt model on top of a new raw source table
- Standardizing column names and data types before any downstream transformations
- Adding freshness checks to a source for CI validation

## Implementation

```yaml
# models/staging/crm/_crm__sources.yml
version: 2

sources:
  - name: crm
    database: "{{ var('project_id') }}"
    schema: raw_crm
    description: "CRM system raw exports loaded via Fivetran"
    loaded_at_field: _loaded_at
    freshness:
      warn_after:  {count: 6,  period: hour}
      error_after: {count: 24, period: hour}
    tables:
      - name: customers
        identifier: customers_raw
        description: "All customer records from CRM. One row per customer."
        columns:
          - name: id
            description: "Source CRM customer ID"
          - name: email
            description: "Customer email address"
```

```sql
-- models/staging/crm/stg_crm__customers.sql
-- Layer: staging
-- Contract: rename, cast, coalesce only — no JOINs, no business logic
-- Grain: one row per customer (source system)

{{ config(
    materialized = 'view',
    tags         = ['staging', 'crm']
) }}

WITH source AS (
    SELECT * FROM {{ source('crm', 'customers') }}
),

renamed AS (
    SELECT
        -- Primary key
        id                                      AS customer_id,

        -- Identifiers
        CAST(account_id AS STRING)              AS account_id,

        -- Attributes: rename to snake_case standard
        full_name,
        LOWER(TRIM(email))                      AS email,
        NULLIF(TRIM(phone_number), '')          AS phone_number,

        -- Address
        TRIM(city)                              AS city,
        UPPER(TRIM(state_code))                 AS state_code,
        UPPER(TRIM(country_code))               AS country_code,

        -- Classification
        LOWER(TRIM(loyalty_tier))               AS loyalty_tier,

        -- Timestamps: cast to TIMESTAMP, standardize timezone
        CAST(created_at AS TIMESTAMP)           AS created_at,
        CAST(updated_at AS TIMESTAMP)           AS updated_at,

        -- Soft delete flag
        COALESCE(is_deleted, FALSE)             AS is_deleted,

        -- Audit column from source loader
        _loaded_at

    FROM source
)

SELECT * FROM renamed
```

```yaml
# models/staging/crm/_crm__models.yml
version: 2

models:
  - name: stg_crm__customers
    description: "Staged customer records from CRM. One row per customer."
    columns:
      - name: customer_id
        description: "Source CRM customer ID"
        tests:
          - unique
          - not_null

      - name: email
        tests:
          - not_null

      - name: loyalty_tier
        tests:
          - accepted_values:
              values: ['bronze', 'silver', 'gold', 'platinum']
              severity: warn

      - name: created_at
        tests:
          - not_null
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Materialization | `view` | No storage; always fresh from source |
| Tags | `['staging', 'crm']` | Source-specific tags for selective runs |
| TRIM on strings | Always | Prevent whitespace issues downstream |
| LOWER on email | Always | Normalize before joins |
| COALESCE booleans | Always | Prevent unexpected NULLs |

## Example Usage

```bash
# Run and test this model
dbt run --select stg_crm__customers
dbt test --select stg_crm__customers

# Check source freshness first
dbt source freshness --select source:crm
dbt run --select stg_crm__customers+   # run model + all downstream
```

## See Also

- [concepts/model-layers.md](../concepts/model-layers.md)
- [concepts/sources-and-refs.md](../concepts/sources-and-refs.md)
- [patterns/incremental-model.md](incremental-model.md)
