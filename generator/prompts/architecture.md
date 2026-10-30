Design the smallest maintainable complete implementation of the supplied analysis.
Produce a coherent API contract with exact request and response field names and types.
Use /api/v1 paths. Auth is fixed bearer tokens from ADMIN_TOKEN and DRIVER_TOKEN environment
variables, roles admin and driver. Never add JWT packages or a second authentication system.
List every endpoint the frontend and tests will need, including seed and demo scenario controls.
Use PostgreSQL, PostGIS for geographic operations, a transactional outbox and Kafka events.
Identify all entities, invariants and acceptance tests. Distinguish test controls from live operation.
If location data is involved, validate coordinate ranges, reject stale points and model geofence uncertainty.
If the source data contains WKT lines, these are street segments, not authoritative zone polygons.
Document any distance threshold as a configurable assumption with metres as the unit.
When domain tables are needed, create SQL migrations. Available Store JSON documents are an
auxiliary facility and should not replace relational constraints on critical business state.
Do not introduce extra dependencies or additional services beyond the fixed platform.
Design all workflows so they can be demonstrated through API and Angular UI without editing source.
