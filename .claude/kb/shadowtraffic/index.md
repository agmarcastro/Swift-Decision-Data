# ShadowTraffic Knowledge Base

> **Purpose**: Synthetic data generation platform using a JSON DSL for Kafka, PostgreSQL, and other targets
> **MCP Validated**: 2026-04-24

## Quick Navigation

### Concepts (< 150 lines each)

| File | Purpose |
|------|---------|
| [concepts/generators.md](concepts/generators.md) | `_gen` DSL primitives: uuid, string, int, oneOf, stateMachine, lookup, and more |
| [concepts/connections.md](concepts/connections.md) | Kafka and PostgreSQL connection config; serializer selection |
| [concepts/throttle.md](concepts/throttle.md) | Rate controls: throttleMs, throughput, maxEvents, maxMs, delay |
| [concepts/state-machines.md](concepts/state-machines.md) | stateMachine generator: states, transitions, weights, terminal states |
| [concepts/local-pool.md](concepts/local-pool.md) | History pools and `lookup` for cross-topic referential integrity |

### Patterns (< 200 lines each)

| File | Purpose |
|------|---------|
| [patterns/kafka-topic-generator.md](patterns/kafka-topic-generator.md) | Complete single-topic Kafka generator with realistic fields |
| [patterns/cross-topic-relationships.md](patterns/cross-topic-relationships.md) | Parent/child topic linking via history pool + lookup |
| [patterns/order-lifecycle-state-machine.md](patterns/order-lifecycle-state-machine.md) | Stateful order status workflow with weighted transitions |
| [patterns/throttle-strategies.md](patterns/throttle-strategies.md) | Rate control recipes for common throughput scenarios |

---

## Quick Reference

- [quick-reference.md](quick-reference.md) — Generator DSL cheat sheet, Faker namespace table, config skeleton

---

## Key Concepts

| Concept | Description |
|---------|-------------|
| **`_gen` function** | JSON map with a `_gen` key; replaces any literal value in a config |
| **Generator** | Backend-specific config block (topic, key, value for Kafka; table, row for Postgres) |
| **Connection** | Named backend target declared under `"connections"` with `"kind"` field |
| **localConfigs** | Per-generator overrides for throttle, history size, schema hints |
| **stateMachine** | Stateful `_gen` function that emits values according to state transitions |
| **lookup** | `_gen` function that reads from another generator's history pool |

---

## Learning Path

| Level | Files |
|-------|-------|
| **Beginner** | concepts/generators.md, concepts/connections.md, quick-reference.md |
| **Intermediate** | patterns/kafka-topic-generator.md, concepts/throttle.md, patterns/throttle-strategies.md |
| **Advanced** | concepts/state-machines.md, concepts/local-pool.md, patterns/cross-topic-relationships.md, patterns/order-lifecycle-state-machine.md |

---

## Agent Usage

| Agent | Primary Files | Use Case |
|-------|---------------|----------|
| shadowtraffic-specialist | all concepts + patterns | Design and validate ShadowTraffic configs |
| shadowtraffic-specialist | patterns/kafka-topic-generator.md | Bootstrap a new topic generator |
| shadowtraffic-specialist | patterns/cross-topic-relationships.md | Link parent/child entities across topics |

---

## When to Use Each File

- **Debugging a broken `_gen` expression** → `concepts/generators.md`
- **Setting up a new Kafka connection** → `concepts/connections.md`
- **Controlling data volume or run time** → `concepts/throttle.md` + `patterns/throttle-strategies.md`
- **Modeling an entity lifecycle (order, session, cart)** → `concepts/state-machines.md` + `patterns/order-lifecycle-state-machine.md`
- **Linking orders to customers by ID** → `concepts/local-pool.md` + `patterns/cross-topic-relationships.md`
- **Starting a new topic from scratch** → `patterns/kafka-topic-generator.md`
