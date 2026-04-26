# Connections

> **Purpose**: Configure output targets — Kafka, PostgreSQL, and other backends
> **Confidence**: 0.95
> **MCP Validated**: 2026-04-24

## Overview

Connections are top-level named objects that declare where ShadowTraffic writes events. Each
generator references a connection implicitly (single-connection configs) or explicitly by name.
The `kind` field selects the backend driver. Connection-level settings apply to all generators
unless overridden in a generator's `localConfigs`.

## The Pattern

```json
{
  "connections": {
    "localKafka": {
      "kind": "kafka",
      "producerConfigs": {
        "bootstrap.servers": "localhost:9092",
        "key.serializer":   "io.shadowtraffic.kafka.serdes.JsonSerializer",
        "value.serializer": "io.shadowtraffic.kafka.serdes.JsonSerializer"
      }
    },
    "localPostgres": {
      "kind": "postgres",
      "connectionConfigs": {
        "host":     "localhost",
        "port":     5432,
        "username": "postgres",
        "password": "postgres",
        "db":       "mydb"
      }
    }
  }
}
```

## Kafka Connection

| Field | Required | Description |
|-------|----------|-------------|
| `kind` | yes | `"kafka"` |
| `producerConfigs.bootstrap.servers` | yes | Broker address(es) |
| `producerConfigs.key.serializer` | yes | Serializer class for keys |
| `producerConfigs.value.serializer` | yes | Serializer class for values |
| `topicPolicy` | no | `"create"`, `"dropAndCreate"`, or `"manual"` |
| `sendSynchronous` | no | Boolean; default `false` |

Built-in serializers:
- `io.shadowtraffic.kafka.serdes.JsonSerializer` — plain JSON
- `io.confluent.kafka.serializers.KafkaAvroSerializer` — Confluent Avro
- `io.confluent.kafka.serializers.KafkaJsonSchemaSerializer` — JSON Schema

Schema Registry (when using Confluent serializers):
```json
"producerConfigs": {
  "schema.registry.url": "http://localhost:8081",
  "basic.auth.user.info": "user:password"
}
```

## Kafka Generator Fields

| Field | Required | Description |
|-------|----------|-------------|
| `topic` | yes | Target topic name |
| `key` | no | Message key shape |
| `value` | yes | Message value shape |
| `headers` | no | Map of header key/value `_gen` expressions |
| `localConfigs` | no | Per-generator overrides (throttle, schema hints) |

## PostgreSQL Connection

| Field | Required | Description |
|-------|----------|-------------|
| `kind` | yes | `"postgres"` |
| `connectionConfigs.host` | yes | DB server host |
| `connectionConfigs.port` | yes | DB server port |
| `connectionConfigs.db` | yes | Database name |
| `connectionConfigs.username` | yes | Auth username |
| `connectionConfigs.password` | yes | Auth password |

## PostgreSQL Generator Fields

| Field | Required | Description |
|-------|----------|-------------|
| `table` | yes | Target table name |
| `row` | yes | Column map with `_gen` expressions |
| `op` | no | `"insert"` (default), `"update"`, `"delete"` |
| `where` | conditional | Required for `update`/`delete`; equality map |

```json
{
  "table": "orders",
  "row": {
    "id":     { "_gen": "uuid" },
    "amount": { "_gen": "uniformDistribution", "bounds": [5, 500] }
  },
  "op": "insert"
}
```

## Common Mistakes

### Wrong — missing `kind` field

```json
{ "localKafka": { "bootstrap.servers": "localhost:9092" } }
```

### Correct

```json
{
  "localKafka": {
    "kind": "kafka",
    "producerConfigs": { "bootstrap.servers": "localhost:9092", ... }
  }
}
```

## Related

- [generators.md](generators.md)
- [throttle.md](throttle.md)
- [kafka-topic-generator.md](../patterns/kafka-topic-generator.md)
- [cross-topic-relationships.md](../patterns/cross-topic-relationships.md)
