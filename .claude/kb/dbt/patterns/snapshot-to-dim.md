# Snapshot to Dimension Pattern

> **Purpose**: Convert a dbt snapshot into a clean dim_ model with is_current, surrogate key, tests
> **MCP Validated**: 2026-04-24

## When to Use

- A dbt snapshot (`snp_`) exists and needs to be exposed as a BI-ready dimension
- Cleaning up dbt internal column names (`dbt_valid_from`) into business-friendly names
- Adding a surrogate key and `is_current` flag for star schema joins

## Implementation

```sql
-- snapshots/snp_customers.sql (prerequisite — the source snapshot)
{% snapshot snp_customers %}
{{
    config(
        target_schema          = 'snapshots',
        strategy               = 'timestamp',
        unique_key             = 'customer_id',
        updated_at             = 'updated_at',
        invalidate_hard_deletes = true
    )
}}
SELECT customer_id, full_name, email, loyalty_tier, city, state_code, updated_at
FROM {{ source('crm', 'customers') }}
{% endsnapshot %}
```

```sql
-- models/marts/core/dim_customer.sql
-- Converts snp_customers into a clean SCD2 dimension
-- grain: one row per customer version (current + historical)

{{ config(
    materialized = 'table',
    tags         = ['marts', 'core', 'dimensions']
) }}

WITH snapshot_base AS (
    SELECT
        customer_id,
        full_name,
        email,
        loyalty_tier,
        city,
        state_code,
        dbt_valid_from,
        dbt_valid_to,
        dbt_scd_id
    FROM {{ ref('snp_customers') }}
),

with_surrogate_key AS (
    SELECT
        -- Stable INT64 surrogate key: hash of natural key + version start
        {{ dbt_utils.generate_surrogate_key(['customer_id', 'dbt_valid_from']) }}
            AS customer_key,

        -- Natural key (source identifier)
        customer_id             AS customer_natural_key,

        -- Business attributes
        full_name,
        LOWER(TRIM(email))      AS email,
        loyalty_tier,
        city,
        state_code,

        -- Version control columns (clean names for BI)
        CAST(dbt_valid_from AS DATE)    AS valid_from,
        CAST(dbt_valid_to   AS DATE)    AS valid_to,
        dbt_valid_to IS NULL            AS is_current,

        -- Snapshot metadata
        dbt_scd_id              AS scd_row_id

    FROM snapshot_base
)

SELECT * FROM with_surrogate_key
```

```yaml
# models/marts/core/_core__models.yml (dim_customer section)
  - name: dim_customer
    description: "Customer dimension with SCD2 history from snp_customers snapshot."
    columns:
      - name: customer_key
        description: "Surrogate PK. Unique per customer version."
        tests:
          - unique
          - not_null

      - name: customer_natural_key
        description: "Source CRM customer ID."
        tests:
          - not_null

      - name: is_current
        description: "TRUE for the active customer version."
        tests:
          - not_null

      - name: valid_from
        tests:
          - not_null

      - name: loyalty_tier
        tests:
          - accepted_values:
              values: ['bronze', 'silver', 'gold', 'platinum']
              severity: warn
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| Snapshot strategy | `timestamp` | Requires `updated_at` column in source |
| Surrogate key | `generate_surrogate_key(['customer_id', 'dbt_valid_from'])` | Unique per version |
| `is_current` | `dbt_valid_to IS NULL` | Standard current-record filter |
| `invalidate_hard_deletes` | `true` | Closes versions for deleted source rows |

## Example Usage

```bash
# Run snapshot first, then dimension model
dbt snapshot --select snp_customers
dbt run --select dim_customer
dbt test --select dim_customer

# Verify no duplicate current rows
# Run: SELECT customer_natural_key, COUNT(*) FROM dim_customer
#      WHERE is_current GROUP BY 1 HAVING COUNT(*) > 1
```

## See Also

- [concepts/snapshots.md](../concepts/snapshots.md)
- [concepts/scd-types.md](../../dw/concepts/scd-types.md)
- [patterns/incremental-model.md](incremental-model.md)
