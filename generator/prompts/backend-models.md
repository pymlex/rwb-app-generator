Generate exactly backend/DomainModels.cs and backend/migrations/002_domain.sql.
All declarations use the global namespace to match the fixed platform. No namespace declaration.
Design a typed contract for the supplied business requirements and API blueprint.
DomainModels.cs must contain request DTOs, response DTOs, and public interface IDomainService.
Every public service operation returns Task<OperationResult<TDto>> and receives Actor actor.
Include Task Initialise() for idempotent startup. Include a Tick method only when time-based
domain transitions require a background worker. Expose all information the UI needs.
Critical write methods receive string? idempotencyKey. Optional pagination parameters have bounds.
The fixed Actor has Subject as STRING and IsAdmin as bool. Demo subjects are exactly "driver"
and "admin". OwnerSubject fields MUST be strings. Never parse Actor.Subject as a GUID.
Domain entity IDs may be GUIDs. Do not conflate ownership subjects with entity IDs.
Use immutable records for DTOs. Do not put business logic or route handlers in this file.
The SQL file contains actual normalised domain tables, foreign keys, unique constraints, indexes,
and all constraints needed to prevent invalid concurrent states. Do NOT recreate documents,
outbox, audit_events or api_idempotency: these platform tables already exist.
Use PostGIS geometry with SRID 4326 for geospatial domains and a GiST geography index for distance.
Street WKT lines are matched with ST_DWithin in metres. Do not use ST_Contains for line geometry.
Polygon boundaries use ST_Covers. Provider entityState values must be compared case-insensitively.
If active sessions or loans are exclusive, enforce exclusivity at DATABASE level.
Keep money as integer minor units. Preserve provider IDs separately from application IDs.
Use the supplied reference_data profile as the source schema. Include original source identifiers,
prices, timing constraints, original geometry and an explicit approximation flag in relevant DTOs.
Store original source fields alongside normalised indexed fields. A Polygon column cannot hold
supplied LINESTRING WKT. Use compatible geometry and geographic-distance indexes.
Ensure all blueprint paths and operations can be implemented through the interface.
Add explicit ADMIN-only deterministic demo time and step controls when required to demonstrate
time-based behaviour without waiting. Separate demo time from actual time in response DTOs.
Do not seed random IDs in migrations. All migrations must be idempotent.
