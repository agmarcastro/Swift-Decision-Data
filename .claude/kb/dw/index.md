# Dimensional Modeling Knowledge Base

> **Purpose**: Kimball-style dimensional modeling for data warehouse design
> **MCP Validated**: 2026-04-24

## Quick Navigation

### Concepts (< 150 lines each)

| File | Purpose |
|------|---------|
| [concepts/dimensional-modeling.md](concepts/dimensional-modeling.md) | Kimball methodology, bus matrix, conformed dimensions, grain |
| [concepts/fact-tables.md](concepts/fact-tables.md) | Fact table types, measure additivity, surrogate vs natural keys |
| [concepts/dimension-tables.md](concepts/dimension-tables.md) | Dimension types, SCD overview, junk/degenerate/role-playing dims |
| [concepts/scd-types.md](concepts/scd-types.md) | SCD Type 1/2/3 mechanics and when to use each |
| [concepts/star-vs-snowflake.md](concepts/star-vs-snowflake.md) | Schema trade-offs and decision guide |

### Patterns (< 200 lines each)

| File | Purpose |
|------|---------|
| [patterns/star-schema-design.md](patterns/star-schema-design.md) | Full DDL for orders star schema with surrogate keys and FKs |
| [patterns/scd2-implementation.md](patterns/scd2-implementation.md) | MERGE-based SCD2 upsert in BigQuery SQL |
| [patterns/one-big-table.md](patterns/one-big-table.md) | OBT pattern for BI consumption with STRUCT usage |
| [patterns/date-dimension.md](patterns/date-dimension.md) | Generating dim_date in BigQuery with calendar flags |

---

## Quick Reference

- [quick-reference.md](quick-reference.md) - Fact type matrix, SCD rules, grain naming

---

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Grain** | The lowest level of detail stored in a fact table — must be declared first |
| **Conformed Dimension** | Dimension shared across multiple fact tables for cross-process analysis |
| **Surrogate Key** | System-generated integer PK replacing natural keys in dimension tables |
| **Bus Matrix** | Grid mapping business processes (rows) to shared dimensions (columns) |
| **SCD Type 2** | Versioned history rows with valid_from/valid_to/is_current for tracking change |

---

## Learning Path

| Level | Files |
|-------|-------|
| **Beginner** | concepts/dimensional-modeling.md, concepts/star-vs-snowflake.md |
| **Intermediate** | concepts/fact-tables.md, concepts/dimension-tables.md, patterns/star-schema-design.md |
| **Advanced** | concepts/scd-types.md, patterns/scd2-implementation.md, patterns/one-big-table.md |

---

## Agent Usage

| Agent | Primary Files | Use Case |
|-------|---------------|----------|
| dw-specialist | concepts/dimensional-modeling.md, patterns/star-schema-design.md | Design fact/dim schema |
| dw-specialist | patterns/scd2-implementation.md, concepts/scd-types.md | Implement change tracking |
| dw-specialist | patterns/one-big-table.md, patterns/date-dimension.md | Build mart layer |
