Generate exactly backend/Domain.cs. This file ONLY maps HTTP endpoints to the supplied IDomainService.
Implement public static class Domain with:
public static void Configure(IServiceCollection services, IConfiguration configuration)
public static Task Initialise(WebApplication app)
public static void Map(WebApplication app)
Configure registers DomainService as IDomainService singleton and any DomainWorker actually present.
Initialise awaits the service Initialise method. Map registers all actual blueprint endpoints.
Each domain endpoint must RequireAuthorization("driver") or RequireAuthorization("admin") and
RequireRateLimiting("api"). The admin role satisfies the driver policy. Actor.From(context)
returns the actor. Do not parse its Subject as a GUID. Do not register /api/v1/me, health,
Swagger or OpenAPI: these are already provided by Program.cs.
Map route and request DTO arguments to the ACTUAL service methods exactly. Do not invent methods.
Use explicit async Task<IResult> lambda return types and return serviceResult.ToHttp().
Critical writes read context.Request.Headers["Idempotency-Key"].ToString(). Missing keys are
rejected by RequestKeys. Include typed Produces<TDto> declarations for accurate OpenAPI schemas.
For roles and authentication, trust the fixed platform. Do not implement another token system.
No SQL, in-memory domain state, background Task.Run loops or fake route responses in this file.
