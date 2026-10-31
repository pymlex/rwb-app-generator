# Backend implementation

Use the fixed .NET 10, C# 14, Npgsql 10 platform and its global namespace.
Typed DTOs and IDomainService are the shared contract. Implement only assigned operations.
Partial DomainService files share the fixed database and configuration fields and constructor.
Use parameterised SQL, explicit PostgreSQL types for null parameters, and invariant numeric parsing.
Use an explicit nullable type for a conditional integer-or-null expression, not an untyped var.
Npgsql timestamptz values must have UTC offset zero. Validate and convert timestamps explicitly.
Async readers must be closed before issuing another command on the same connection.
Immutable DTO changes use record with expressions. DomainJson handles persisted web JSON casing.
Do not assume another worker created private helpers. Use the actual interface or your own prefixed helpers.
Startup seeds must preserve existing state and stable identities. Restart is not a reset operation.
Schema repair must migrate existing data safely with idempotent ALTER statements where needed.

