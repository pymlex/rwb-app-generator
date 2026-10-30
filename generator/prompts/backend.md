Generate exactly backend/Domain.cs and backend/migrations/002_domain.sql.
Implement ALL blueprint endpoints and business requirements with working persistence and validation.
Use global namespace and public static class Domain with:
public static Task Initialise(WebApplication app)
public static void Map(WebApplication app)
Initialise runs after all migrations and must seed reproducible demo data idempotently using SQL.
Every mapped domain endpoint must RequireAuthorization("admin") or RequireAuthorization("driver")
and RequireRateLimiting("api"). The admin can access driver endpoints but driver cannot access admin data.
Do not require auth on /health or /openapi: these are already provided by the fixed Program.cs.
Read identity from HttpContext.User and filter owned resources. Use parameterised Npgsql queries.
Only use BCL, ASP.NET Core, Npgsql and the supplied Store API. No EF, Dapper or other dependencies.
Use explicit IResult return types for route handlers with more than one result type to avoid C# inference issues.
Use Results.Problem for errors. Return 400 for invalid data, 404 for absent records, 409 for conflicts.
Request validation must be explicit: minimal API records do not automatically run DataAnnotations.
Store exposes Get(kind,id), List(kind,limit), Save(kind,id,body,eventType,actor,idempotencyKey).
Save is atomic for one document and its outbox event. For multi-row business operations use your own
Npgsql transaction and insert outbox rows in that SAME transaction. Never commit state before its event.
Use unique constraints or row locks for concurrency-sensitive state transitions and idempotency.
Migrations run in filename order and must be idempotent. Keep all schema names consistent.
Define request and response records in Domain.cs after the Domain class, or nested within it.
Expose enough deterministic demo controls to exercise time-dependent behaviours without waiting in real time.
Any simulated clock MUST be explicitly a demo input and must not silently affect production defaults.
Any location logic MUST use PostGIS with longitude first, WGS84, geography distances in metres.
If applicable, load data/parking-zones.json when present using the supplied source schema:
{result:"Success",data:{city:"spb",zones:[{externalZoneId,displayName,geometry:"LINESTRING (...) or POLYGON (...) WKT",price:integer minor units,priceDescription,minTime,timeStep,entityState}]}}.
Expose a domain collection endpoint returning actual geometries for frontend mapping.
If no external file is present, seed enough documented synthetic fixtures to demonstrate all transitions.
Do not assume prices are roubles when they are integer minor units. Do not conflate provider segment IDs
with official zone numbers. Financial confirmation must not charge real money.
Keep implementation compact enough to fit this response but complete. No comments or TODOs.
