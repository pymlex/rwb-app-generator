Generate exactly the output_path named in the task, as one partial class DomainService.
The fixed DomainService.cs already declares the constructor and fields database and configuration.
Do not redeclare these fields, the constructor or the class primary constructor.
Implement ONLY the method signatures listed in assigned_methods with working SQL persistence.
Other interface methods are generated in separate partial files and may be called by exact signature.
Use public sealed partial class DomainService : IDomainService. Add required using directives.
Do not define helper names shared across modules. Prefix private helpers with the module identifier.
Do not assume helpers exist in other partial files. Only fixed fields and interface methods are shared.
Only BCL, Npgsql and supplied platform helpers are available. Do not change the interface or DTOs.
Use parameterised SQL. Use DomainJson.Read<T> and DomainJson.Write for all JSON persistence.
Actor.Subject is a STRING "driver" or "admin". Scope driver records to the matching OwnerSubject.
Admins can list all records and inspect all history. An actor must never gain access by specifying
another owner's entity ID. Validate every input explicitly, including NaN, future and stale GPS.
Use RequestKeys.Execute<TDto> for critical create/confirm/approve operations. It runs the supplied
action in a transaction, locks each actor/key, compares payload hashes, caches successful results,
returns 409 for key reuse with different input, and rolls back non-success results.
Your action must additionally lock the aggregate row and use relational constraints to protect
against two simultaneous requests with DIFFERENT keys. Never catch and ignore database errors.
Append domain changes using DomainEvents.Append in the SAME transaction as the state update.
This helper writes both audit_events and outbox with eventId, version, actor and timestamps.
Keep document Store out of core relational business state. Do not bypass these helpers.
Use record 'with' expressions instead of assigning init-only DTO properties.
Initialise must be repeatable with no duplicate entities, drivers, zones or sessions after restart.
Use deterministic fixture IDs and ON CONFLICT updates. Seed a driver owning records with subject
"driver". Any synthetic fixtures must be explicitly marked synthetic and used only for demo.
The supplied reference_data profile identifies actual source files and exact collection schemas.
For source import or geospatial operations, load the geospatial skill and use those facts.
Preserve source identifiers and original fields. Do not invent a replacement source schema.
Use DomainEvents for actual state transitions, notifications and expiry as required.
Time-based warnings must be computed by a real background service or deterministically evaluated
on polling, without duplicates. Implement demo clock advance and reset if the interface includes them.
If a background worker is required, define DomainWorker in this file, inject IDomainService,
and evaluate due transitions periodically. Do not merely return 'scenario started' without moving
the actual stored vehicle and producing the specified events.
Implement every demo step as a real call to domain operations. Do not clear normal user data in reset.
No real charges or refunds. Use an adapter for the simulated provider confirmation and document it.
Do not call any LLM or unrelated service. No TODOs, empty workflow methods, fake success or comments.

For geospatial zone matching, LINESTRING and MULTILINESTRING require ST_DWithin on geography
using a configurable lane-distance threshold in metres. Treat a default of 15 metres as a documented
approximation assumption, not an authoritative boundary. Never replace source lines with polygons.
For POLYGON and MULTIPOLYGON use ST_Covers, including boundary points, plus a separate configurable
GPS-noise threshold in metres via ST_DWithin on geography for nearby outside points marked approximate.
For GEOMETRYCOLLECTION use ST_CollectionExtract(geometry, 2) for lines and
ST_CollectionExtract(geometry, 3) for polygons, then apply the corresponding matching rule.
Skip empty components and never cast an unfiltered mixed collection to geography.
When several zones match, select the nearest by ST_Distance on geography in metres and use a stable
source identifier to break ties. Preserve source geometry and expose approximation metadata.
Provide deterministic fixtures so generated acceptance tests can assert a curbside line match,
inside/outside lane thresholds, multiline, polygon interior/boundary, GPS noise, mixed/empty
collections and nearest-zone selection. Use actual source coordinates when reference data exists.
