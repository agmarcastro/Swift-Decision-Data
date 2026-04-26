# dbt Quick Reference

> Fast lookup tables. For code examples, see linked files.
> **MCP Validated**: 2026-04-24

## Layer Contract Table

| Layer | Prefix | Allowed SQL | Not Allowed |
|-------|--------|-------------|-------------|
| Staging | `stg_` | rename, cast, coalesce, basic cleaning | joins, aggregations, business logic |
| Intermediate | `int_` | joins, unions, pivots, deduplication | direct source() references |
| Fact | `fct_` | aggregation, metric calculation | source() references, raw table names |
| Dimension | `dim_` | attribute selection, SCD logic | source() references |
| Mart / OBT | `obt_`, `rpt_` | joins + aggregations for BI | writing back to staging |

## Materialization Decision Matrix

| Scenario | Materialization | Reason |
|----------|----------------|--------|
| Raw source cleaning | `view` | Zero storage; always fresh |
| Large fact table | `incremental` | Process only new rows |
| Stable reference data | `table` | Fast BI queries |
| Reusable CTE within model | `ephemeral` | No physical table; subquery inline |
| Snapshot (SCD2) | `snapshot` | Built-in history tracking |

## Incremental Strategies (BigQuery)

| Strategy | How It Works | Best For |
|----------|-------------|---------|
| `append` | INSERT new rows only | Immutable event logs |
| `merge` | UPSERT by unique_key | Fact tables with corrections |
| `insert_overwrite` | Replace partitions | Partition-aligned loads |
| `delete+insert` | DELETE then INSERT | When MERGE is too slow |

## Key Macros Cheat Sheet

| Macro | Package | Usage |
|-------|---------|-------|
| `is_incremental()` | dbt core | `{% if is_incremental() %} WHERE ... {% endif %}` |
| `generate_surrogate_key([cols])` | dbt_utils | Creates MD5 surrogate key from column list |
| `dbt_utils.date_spine(...)` | dbt_utils | Generates date spine for gap filling |
| `dbt_utils.get_column_values(...)` | dbt_utils | Dynamic pivot column list |
| `dbt_utils.union_relations(...)` | dbt_utils | Union multiple models dynamically |

## Generic Test Quick Pick

| Goal | Test |
|------|------|
| No duplicate PKs | `unique` |
| No NULL PKs | `not_null` |
| Valid status codes | `accepted_values` |
| FK integrity check | `relationships` |
| Numeric range check | `dbt_utils.accepted_range` |
| Row count check | `dbt_utils.equal_rowcount` |

## Source YAML Required Fields

```yaml
sources:
  - name: raw_crm
    database: project
    schema: raw
    loaded_at_field: _loaded_at      # for freshness
    freshness:
      warn_after: {count: 6, period: hour}
      error_after: {count: 24, period: hour}
    tables:
      - name: customers
        identifier: customers_raw    # actual BQ table name if different
```

## Common Pitfalls

| Don't | Do Instead |
|-------|-----------|
| `FROM project.raw.customers` | `FROM {{ source('raw_crm', 'customers') }}` |
| JOIN in staging model | Move JOINs to int_ layer |
| `SELECT *` in marts | Explicitly select and alias columns |
| Skip unique test on PK | Always add `unique` + `not_null` on surrogate keys |

## Related Documentation

| Topic | Path |
|-------|------|
| Model layers | `concepts/model-layers.md` |
| Incremental pattern | `patterns/incremental-model.md` |
| Full Index | `index.md` |
