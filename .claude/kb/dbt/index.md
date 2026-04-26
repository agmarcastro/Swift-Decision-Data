# dbt Model Design Knowledge Base

> **Purpose**: dbt model layering, sources, materializations, tests, and snapshots
> **MCP Validated**: 2026-04-24

## Quick Navigation

### Concepts (< 150 lines each)

| File | Purpose |
|------|---------|
| [concepts/model-layers.md](concepts/model-layers.md) | Staging → Intermediate → Marts contract and naming |
| [concepts/sources-and-refs.md](concepts/sources-and-refs.md) | source() vs ref(), freshness, why never use raw table names |
| [concepts/materializations.md](concepts/materializations.md) | view/table/incremental/ephemeral; when to use each |
| [concepts/tests.md](concepts/tests.md) | Generic tests, singular tests, severity levels |
| [concepts/snapshots.md](concepts/snapshots.md) | dbt snapshot mechanics, strategies, consuming in downstream models |

### Patterns (< 200 lines each)

| File | Purpose |
|------|---------|
| [patterns/staging-model.md](patterns/staging-model.md) | Canonical stg_ model with source YAML |
| [patterns/incremental-model.md](patterns/incremental-model.md) | Incremental fct_ model with BigQuery MERGE strategy |
| [patterns/snapshot-to-dim.md](patterns/snapshot-to-dim.md) | Converting dbt snapshot to clean dim_ with is_current filter |
| [patterns/model-yaml-tests.md](patterns/model-yaml-tests.md) | Complete _models.yml with all standard tests |

---

## Quick Reference

- [quick-reference.md](quick-reference.md) - Layer contract table, materialization matrix, macro cheat sheet

---

## Key Concepts

| Concept | Description |
|---------|-------------|
| **Layer contract** | Each layer (stg/int/fct/dim) has strict rules on what SQL is allowed |
| **ref()** | Compile-time dependency declaration; never use raw table names in models |
| **is_incremental()** | Macro that activates the WHERE filter only during incremental runs |
| **snapshot** | dbt-native SCD2 history table; feeds dim_ models downstream |
| **source freshness** | Declarative staleness check on raw data before models run |

---

## Learning Path

| Level | Files |
|-------|-------|
| **Beginner** | concepts/model-layers.md, concepts/sources-and-refs.md |
| **Intermediate** | concepts/materializations.md, patterns/staging-model.md, patterns/model-yaml-tests.md |
| **Advanced** | concepts/snapshots.md, patterns/incremental-model.md, patterns/snapshot-to-dim.md |

---

## Agent Usage

| Agent | Primary Files | Use Case |
|-------|---------------|----------|
| dw-specialist | concepts/model-layers.md, patterns/staging-model.md | Design model layer structure |
| dw-specialist | patterns/incremental-model.md, concepts/materializations.md | Build incremental facts |
| dw-specialist | concepts/snapshots.md, patterns/snapshot-to-dim.md | Track dimension history |
