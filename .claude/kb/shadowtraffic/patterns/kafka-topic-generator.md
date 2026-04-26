# Kafka Topic Generator

> **Purpose**: Complete pattern for a single Kafka topic producing realistic, typed events
> **MCP Validated**: 2026-04-24

## When to Use

- Generating synthetic events for a single Kafka topic in local or CI testing
- Seeding a topic before running consumer integration tests
- Benchmarking Kafka consumer throughput with realistic payload shapes
- Quickly bootstrapping a new pipeline with representative data

## Implementation

```json
{
  "generators": [
    {
      "topic": "orders",
      "key": {
        "order_id": { "_gen": "uuid" }
      },
      "value": {
        "order_id":    { "_gen": "uuid" },
        "customer_id": { "_gen": "uuid" },
        "status": {
          "_gen": "oneOf",
          "choices": ["CREATED", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"]
        },
        "amount": {
          "_gen": "normalDistribution",
          "mean": 85.0,
          "sd":   40.0,
          "decimals": 2
        },
        "currency": {
          "_gen": "oneOf",
          "choices": ["USD", "EUR", "GBP", "BRL"]
        },
        "customer_name": {
          "_gen": "string",
          "expr": "#{Name.full_name}"
        },
        "shipping_address": {
          "_gen": "string",
          "expr": "#{Address.full_address}"
        },
        "email": {
          "_gen": "string",
          "expr": "#{Internet.email_address}"
        },
        "item_count": {
          "_gen": "uniformDistribution",
          "bounds": [1, 10]
        },
        "coupon_code": {
          "_gen": "weightedOneOf",
          "choices": [
            { "weight": 75, "value": null },
            { "weight": 25, "value": { "_gen": "string", "expr": "#{Number.number_between '10','99'}OFF" } }
          ]
        },
        "placed_at":   { "_gen": "now" },
        "updated_at":  { "_gen": "now" }
      },
      "localConfigs": {
        "throttleMs": 200,
        "maxHistoryEvents": 500
      }
    }
  ],
  "connections": {
    "localKafka": {
      "kind": "kafka",
      "producerConfigs": {
        "bootstrap.servers": "localhost:9092",
        "key.serializer":   "io.shadowtraffic.kafka.serdes.JsonSerializer",
        "value.serializer": "io.shadowtraffic.kafka.serdes.JsonSerializer"
      },
      "topicPolicy": "create"
    }
  }
}
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `topicPolicy` | `"manual"` | `"create"` auto-creates topic if missing |
| `throttleMs` | none | Min ms between events; 200 = ~5 events/sec |
| `maxHistoryEvents` | system default | Pool size for downstream `lookup` calls |
| `decimals` | — | Modifier on numeric generators to round output |

## Example Usage

Dry-run preview — print 10 events to stdout without writing to Kafka:

```bash
docker run --rm \
  -v $(pwd)/config.json:/config.json \
  shadowtraffic/shadowtraffic:latest \
  --config /config.json \
  --stdout --sample 10
```

Continuous generation against local Kafka:

```bash
docker run --rm --net=host \
  -v $(pwd)/config.json:/config.json \
  shadowtraffic/shadowtraffic:latest \
  --config /config.json
```

Watch mode (reload on file change during development):

```bash
docker run --rm --net=host \
  -v $(pwd):/workspace \
  shadowtraffic/shadowtraffic:latest \
  --config /workspace/config.json --watch
```

## See Also

- [connections.md](../concepts/connections.md)
- [generators.md](../concepts/generators.md)
- [throttle-strategies.md](throttle-strategies.md)
- [cross-topic-relationships.md](cross-topic-relationships.md)
