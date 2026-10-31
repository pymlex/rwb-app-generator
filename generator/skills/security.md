# Security and concurrency

Actor.Subject is an authenticated string identity. Entity IDs are separate domain identifiers.
Enforce ownership in every server query or mutation, including reads addressed by an entity ID.
Admin role policy permits administration. The frontend role check is not an authorisation boundary.
Use RequestKeys.Execute for critical operations and pass the actor, route, original request and key.
Lock the affected aggregate and enforce invariants in SQL constraints as well as application checks.
Different idempotency keys must not bypass exclusivity or stock bounds under concurrent requests.
Validate required fields, formats, sizes, finite numbers, timestamps, pagination and state transitions.
Return structured problem responses with honest 400, 401, 403, 404, 409 or 422 status codes.
Never return success for an operation that did not persist its promised state change.
Do not expose credentials or connection strings in responses, logs, source or generated documentation.
External industrial integrations use explicit adapters or mocks. They do not replace core domain behaviour.

