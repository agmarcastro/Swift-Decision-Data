# Cross-Topic Relationships

> **Purpose**: Link parent and child topics via history pools and `lookup` for referential integrity
> **MCP Validated**: 2026-04-24

## When to Use

- Orders must reference valid customer IDs that were already generated
- Line items must belong to an existing order
- Any child entity requires a consistent foreign key to a parent entity
- Testing consumers that join two Kafka topics by a shared key

## Implementation

```json
{
  "generators": [
    {
      "topic": "customers",
      "key": {
        "customer_id": { "_gen": "uuid" }
      },
      "value": {
        "customer_id": { "_gen": "uuid" },
        "full_name":   { "_gen": "string", "expr": "#{Name.full_name}" },
        "email":       { "_gen": "string", "expr": "#{Internet.email_address}" },
        "phone":       { "_gen": "string", "expr": "#{PhoneNumber.cell_phone}" },
        "city":        { "_gen": "string", "expr": "#{Address.city}" },
        "country":     { "_gen": "string", "expr": "#{Address.country}" },
        "created_at":  { "_gen": "now" }
      },
      "localConfigs": {
        "throttleMs": 1000,
        "maxHistoryEvents": 300
      }
    },
    {
      "topic": "orders",
      "key": {
        "order_id": { "_gen": "uuid" }
      },
      "vars": {
        "parentCustomer": {
          "_gen": "lookup",
          "topic": "customers"
        }
      },
      "value": {
        "order_id":    { "_gen": "uuid" },
        "customer_id": {
          "_gen": "var",
          "var": "parentCustomer",
          "path": ["value", "customer_id"]
        },
        "customer_name": {
          "_gen": "var",
          "var": "parentCustomer",
          "path": ["value", "full_name"]
        },
        "amount":    { "_gen": "uniformDistribution", "bounds": [10.0, 500.0], "decimals": 2 },
        "status":    { "_gen": "oneOf", "choices": ["CREATED", "PROCESSING", "SHIPPED"] },
        "placed_at": { "_gen": "now" }
      },
      "localConfigs": {
        "throttleMs": 150
      }
    },
    {
      "topic": "order-items",
      "key": {
        "item_id": { "_gen": "uuid" }
      },
      "vars": {
        "parentOrder": {
          "_gen": "lookup",
          "topic": "orders"
        }
      },
      "value": {
        "item_id":   { "_gen": "uuid" },
        "order_id":  {
          "_gen": "var",
          "var": "parentOrder",
          "path": ["value", "order_id"]
        },
        "product":   { "_gen": "string", "expr": "#{Commerce.product_name}" },
        "quantity":  { "_gen": "uniformDistribution", "bounds": [1, 5] },
        "unit_price": { "_gen": "normalDistribution", "mean": 29.99, "sd": 15.0, "decimals": 2 }
      },
      "localConfigs": {
        "throttleMs": 80
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
| `maxHistoryEvents` on parent | system default | Larger = more unique parents available for lookup |
| `strategy` on lookup | `"random"` | `"first"` or `"last"` for ordered fan-out |
| `path` on lookup | — | Drill path into event: `["value", "field"]` |
| `throttleMs` parent vs child | — | Parent slower than child = realistic fan-out ratio |

## Example Usage

Verify referential integrity across topics during a dry run:

```bash
docker run --rm --net=host \
  -v $(pwd)/config.json:/config.json \
  shadowtraffic/shadowtraffic:latest \
  --config /config.json --stdout --sample 20
```

Expected output pattern: ~1 customer event for every ~6 order events, and ~3 items per order.

## See Also

- [local-pool.md](../concepts/local-pool.md)
- [generators.md](../concepts/generators.md)
- [kafka-topic-generator.md](kafka-topic-generator.md)
- [order-lifecycle-state-machine.md](order-lifecycle-state-machine.md)
