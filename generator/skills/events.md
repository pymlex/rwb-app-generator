# Transactional events

State changes, audit evidence and outbox insertion commit in one PostgreSQL transaction.
Use DomainEvents.Append on the same connection and transaction as the mutation.
Do not publish to Kafka before committing business state. The outbox publisher handles delivery.
Events carry eventId, version, type, occurredAt, aggregateId, actor and a small domain payload.
Kafka delivery is at least once. Consumers deduplicate by eventId and preserve aggregate-key ordering.
Warning and expiry transitions need database-level deduplication, not only in-memory flags.
Use the actual domain clock in payload data. The envelope occurrence time records real publication context.
Expose relevant event history through authorised API reads so UI and acceptance tests can verify effects.
Transient broker failure leaves pending outbox rows intact and visible in metrics.

