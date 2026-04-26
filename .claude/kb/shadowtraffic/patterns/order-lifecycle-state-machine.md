# Order Lifecycle State Machine

> **Purpose**: Stateful order status workflow with weighted transitions and terminal states
> **MCP Validated**: 2026-04-24

## When to Use

- Simulating an order tracking system where each order progresses through statuses
- Testing downstream consumers that react to status-change events
- Modeling realistic cancellation and return rates via weighted transitions
- Demonstrating event sourcing patterns where each transition emits a new event

## Implementation

```json
{
  "generators": [
    {
      "topic": "order-lifecycle",
      "key": {
        "order_id": { "_gen": "uuid" }
      },
      "value": {
        "order_id":    { "_gen": "uuid" },
        "customer_id": { "_gen": "uuid" },
        "amount":      { "_gen": "normalDistribution", "mean": 95.0, "sd": 45.0, "decimals": 2 },
        "status": {
          "_gen": "stateMachine",
          "initial": "CREATED",
          "states": {
            "CREATED": {
              "status": "CREATED",
              "message": "Order placed successfully"
            },
            "PAYMENT_PENDING": {
              "status": "PAYMENT_PENDING",
              "message": "Awaiting payment confirmation"
            },
            "PAID": {
              "status": "PAID",
              "message": "Payment confirmed"
            },
            "PROCESSING": {
              "status": "PROCESSING",
              "message": "Order is being prepared",
              "localConfigs": { "throttleMs": 3000 }
            },
            "SHIPPED": {
              "status": "SHIPPED",
              "message": "Order dispatched"
            },
            "DELIVERED": {
              "status": "DELIVERED",
              "message": "Order delivered to customer"
            },
            "CANCELLED": {
              "status": "CANCELLED",
              "message": "Order cancelled"
            },
            "RETURNED": {
              "status": "RETURNED",
              "message": "Order returned by customer"
            }
          },
          "transitions": {
            "CREATED": [
              { "to": "PAYMENT_PENDING", "weight": 95 },
              { "to": "CANCELLED",       "weight": 5 }
            ],
            "PAYMENT_PENDING": [
              { "to": "PAID",      "weight": 88 },
              { "to": "CANCELLED", "weight": 12 }
            ],
            "PAID": [
              { "to": "PROCESSING", "weight": 100 }
            ],
            "PROCESSING": [
              { "to": "SHIPPED",   "weight": 92 },
              { "to": "CANCELLED", "weight": 8 }
            ],
            "SHIPPED": [
              { "to": "DELIVERED", "weight": 93 },
              { "to": "RETURNED",  "weight": 7 }
            ],
            "DELIVERED":  null,
            "CANCELLED":  null,
            "RETURNED":   null
          }
        },
        "updated_at": { "_gen": "now" }
      },
      "localConfigs": {
        "throttleMs": 800,
        "maxHistoryEvents": 200
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

| Setting | Value | Description |
|---------|-------|-------------|
| `initial` | `"CREATED"` | All orders begin in CREATED state |
| `DELIVERED`, `CANCELLED`, `RETURNED` transitions | `null` | Terminal states — generator stops for that entity |
| `PROCESSING.localConfigs.throttleMs` | `3000` | Slow down while in PROCESSING to simulate real latency |
| `throttleMs` (generator) | `800` | One event every ~800ms across all state transitions |

## Transition Probability Summary

| From | To | Approximate Rate |
|------|----|-----------------|
| CREATED | PAYMENT_PENDING | 95% |
| CREATED | CANCELLED | 5% |
| PAYMENT_PENDING | PAID | 88% |
| PAYMENT_PENDING | CANCELLED | 12% |
| PAID | PROCESSING | 100% |
| PROCESSING | SHIPPED | 92% |
| PROCESSING | CANCELLED | 8% |
| SHIPPED | DELIVERED | 93% |
| SHIPPED | RETURNED | 7% |

## Example Usage

```bash
docker run --rm --net=host \
  -v $(pwd)/order-lifecycle.json:/config.json \
  shadowtraffic/shadowtraffic:latest \
  --config /config.json --stdout --sample 30
```

## See Also

- [state-machines.md](../concepts/state-machines.md)
- [kafka-topic-generator.md](kafka-topic-generator.md)
- [cross-topic-relationships.md](cross-topic-relationships.md)
- [throttle-strategies.md](throttle-strategies.md)
