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
For geospatial cases load data/parking-zones.json when present with schema:
{result:"Success",data:{city:"spb",zones:[{externalZoneId,displayName,geometry:WKT,price:minor units,
priceDescription,minTime,timeStep,entityState}]}}. Preserve all source fields and stable provider IDs.
Import WKT using ST_GeomFromText with SRID 4326. Compare Active case-insensitively. Return geometries
to the UI. Match lines with configurable distance in METRES and label the result approximate.
Do not silently substitute fabricated polygons for the provided real street segments.
Use DomainEvents for zone entry, exit, transition, session warning and expiry as relevant.
Time-based warnings must be computed by a real background service or deterministically evaluated
on polling, without duplicates. Implement demo clock advance and reset if the interface includes them.
If a background worker is required, define DomainWorker in this file, inject IDomainService,
and evaluate due transitions periodically. Do not merely return 'scenario started' without moving
the actual stored vehicle and producing the specified events.
Implement every demo step as a real call to domain operations. Do not clear normal user data in reset.
No real charges or refunds. Use an adapter for the simulated provider confirmation and document it.
Do not call any LLM or unrelated service. No TODOs, empty workflow methods, fake success or comments.
