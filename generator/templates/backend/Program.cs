using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Threading.RateLimiting;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.RateLimiting;
using Microsoft.Extensions.Options;
using Npgsql;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddProblemDetails();
builder.Services.AddOpenApi();
builder.Services.AddSingleton(NpgsqlDataSource.Create(builder.Configuration["DATABASE_URL"]
    ?? throw new InvalidOperationException("DATABASE_URL is required")));
builder.Services.AddSingleton<Store>();
builder.Services.AddHostedService<OutboxPublisher>();
builder.Services.AddAuthentication("Bearer").AddScheme<AuthenticationSchemeOptions, TokenHandler>("Bearer", null);
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("admin", policy => policy.RequireRole("admin"));
    options.AddPolicy("driver", policy => policy.RequireRole("driver", "admin"));
});
builder.Services.AddRateLimiter(options => options.AddFixedWindowLimiter("api", limiter =>
{
    limiter.PermitLimit = 120;
    limiter.Window = TimeSpan.FromMinutes(1);
    limiter.QueueLimit = 0;
}).RejectionStatusCode = 429);
var app = builder.Build();
app.UseExceptionHandler();
app.UseStatusCodePages();
app.UseAuthentication();
app.UseAuthorization();
app.UseRateLimiter();
await app.Services.GetRequiredService<Store>().Initialise();
await Domain.Initialise(app);
app.MapOpenApi();
app.UseSwaggerUI(options => options.SwaggerEndpoint("/openapi/v1.json", "API v1"));
app.MapGet("/health/live", () => Results.Ok(new { status = "alive" }));
app.MapGet("/health/ready", async (NpgsqlDataSource database) =>
{
    await using var command = database.CreateCommand("SELECT 1");
    await command.ExecuteScalarAsync();
    return Results.Ok(new { status = "ready" });
});
Domain.Map(app);
await app.RunAsync();

public sealed class TokenHandler(
    IOptionsMonitor<AuthenticationSchemeOptions> options,
    ILoggerFactory logger,
    UrlEncoder encoder,
    IConfiguration configuration) : AuthenticationHandler<AuthenticationSchemeOptions>(options, logger, encoder)
{
    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        var header = Request.Headers.Authorization.ToString();
        if (!header.StartsWith("Bearer ", StringComparison.Ordinal))
            return Task.FromResult(AuthenticateResult.NoResult());
        var token = Encoding.UTF8.GetBytes(header[7..]);
        foreach (var role in new[] { "admin", "driver" })
        {
            var expected = configuration[$"{role.ToUpperInvariant()}_TOKEN"];
            if (!string.IsNullOrEmpty(expected) && CryptographicOperations.FixedTimeEquals(token, Encoding.UTF8.GetBytes(expected)))
            {
                var identity = new ClaimsIdentity(new[] { new Claim(ClaimTypes.NameIdentifier, role), new Claim(ClaimTypes.Role, role) }, "Bearer");
                return Task.FromResult(AuthenticateResult.Success(new AuthenticationTicket(new ClaimsPrincipal(identity), "Bearer")));
            }
        }
        return Task.FromResult(AuthenticateResult.Fail("Invalid access token"));
    }
}

public partial class Program;
