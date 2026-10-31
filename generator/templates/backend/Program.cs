using System.Diagnostics;
using System.Globalization;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using System.Threading.RateLimiting;
using Confluent.Kafka;
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
builder.Services.AddSingleton<ServiceHealth>();
builder.Services.AddSingleton<ServiceMetrics>();
builder.Services.AddHostedService<OutboxPublisher>();
builder.Services.AddAuthentication("Bearer").AddScheme<AuthenticationSchemeOptions, TokenHandler>("Bearer", null);
builder.Services.AddAuthorization(options =>
{
    options.AddPolicy("admin", policy => policy.RequireRole("admin"));
    options.AddPolicy("driver", policy => policy.RequireRole("driver", "admin"));
});
builder.Services.AddRateLimiter(options =>
{
    options.RejectionStatusCode = 429;
    options.AddPolicy("api", context => RateLimitPartition.GetFixedWindowLimiter(
        context.User.FindFirstValue(ClaimTypes.NameIdentifier) ?? context.Connection.RemoteIpAddress?.ToString() ?? "anonymous",
        _ => new FixedWindowRateLimiterOptions { PermitLimit = 120, Window = TimeSpan.FromMinutes(1), QueueLimit = 0 }));
});
DriverIdentities.Parse(builder.Configuration);
Domain.Configure(builder.Services, builder.Configuration);
var app = builder.Build();
app.Use(async (context, next) =>
{
    var started = Stopwatch.GetTimestamp();
    var completed = false;
    try
    {
        await next(context);
        completed = true;
    }
    finally
    {
        app.Services.GetRequiredService<ServiceMetrics>().Observe(
            context.Response.StatusCode,
            Stopwatch.GetElapsedTime(started),
            !completed);
    }
});
app.UseExceptionHandler();
app.UseStatusCodePages();
app.UseAuthentication();
app.UseAuthorization();
app.UseRateLimiter();
await app.Services.GetRequiredService<Store>().Initialise();
await Domain.Initialise(app);
app.MapOpenApi();
app.UseSwaggerUI(options => options.SwaggerEndpoint("/openapi/v1.json", "API v1"));
app.MapGet("/api/v1/me", (HttpContext context) => Results.Ok(new { subject = Actor.From(context).Subject, role = context.User.IsInRole("admin") ? "admin" : "driver" })).RequireAuthorization().RequireRateLimiting("api");
app.MapGet("/health/live", () => Results.Ok(new { status = "Healthy" }));
app.MapGet("/health", async (ServiceHealth health, CancellationToken cancellationToken) =>
    await health.Check(cancellationToken));
app.MapGet("/health/ready", async (ServiceHealth health, CancellationToken cancellationToken) =>
    await health.Check(cancellationToken));
app.MapGet("/metrics", async (ServiceMetrics metrics, ServiceHealth health, CancellationToken cancellationToken) =>
{
    var pending = await health.PendingOutbox(cancellationToken);
    return Results.Text(metrics.Render(pending), "text/plain; version=0.0.4; charset=utf-8");
});
Domain.Map(app);
await app.RunAsync();

public sealed class ServiceHealth(NpgsqlDataSource database, IConfiguration configuration, ILogger<ServiceHealth> logger)
{
    public async Task<long?> PendingOutbox(CancellationToken cancellationToken)
    {
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(2));
        try
        {
            await using var command = database.CreateCommand("SELECT count(*) FROM outbox WHERE published_at IS NULL");
            command.CommandTimeout = 2;
            return Convert.ToInt64(await command.ExecuteScalarAsync(timeout.Token), CultureInfo.InvariantCulture);
        }
        catch (NpgsqlException)
        {
            logger.LogWarning("Database health probe failed");
            return null;
        }
        catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested && timeout.IsCancellationRequested)
        {
            logger.LogWarning("Database health probe timed out");
            return null;
        }
    }

    public async Task<IResult> Check(CancellationToken cancellationToken)
    {
        var databaseProbe = PendingOutbox(cancellationToken);
        var kafkaProbe = KafkaAvailable(cancellationToken);
        await Task.WhenAll(databaseProbe, kafkaProbe);
        var pending = await databaseProbe;
        var kafkaHealthy = await kafkaProbe;
        var status = pending is null ? "Unhealthy" : kafkaHealthy ? "Healthy" : "Degraded";
        return Results.Json(new
        {
            status,
            checks = new
            {
                database = pending is null ? "Unhealthy" : "Healthy",
                kafka = kafkaHealthy ? "Healthy" : "Unhealthy"
            }
        }, statusCode: status == "Healthy" ? 200 : 503);
    }

    private async Task<bool> KafkaAvailable(CancellationToken cancellationToken)
    {
        try
        {
            using var admin = new AdminClientBuilder(new AdminClientConfig
            {
                BootstrapServers = configuration["KAFKA_BOOTSTRAP_SERVERS"] ?? "kafka:9092",
                SocketTimeoutMs = 2000,
                SocketConnectionSetupTimeoutMs = 2000
            }).Build();
            var metadata = await Task.Run(() => admin.GetMetadata(TimeSpan.FromSeconds(2)), cancellationToken);
            if (metadata.Brokers.Count > 0)
                return true;
            logger.LogWarning("Kafka health probe returned no brokers");
            return false;
        }
        catch (KafkaException)
        {
            logger.LogWarning("Kafka health probe failed");
            return false;
        }
    }
}

public sealed class ServiceMetrics
{
    private readonly long started = Stopwatch.GetTimestamp();
    private long requests;
    private long errors;
    private long durationTicks;

    public void Observe(int statusCode, TimeSpan duration, bool aborted)
    {
        Interlocked.Increment(ref requests);
        Interlocked.Add(ref durationTicks, duration.Ticks);
        if (aborted || statusCode >= 400)
            Interlocked.Increment(ref errors);
    }

    public string Render(long? pending)
    {
        var output = new StringBuilder();
        output.AppendLine("# HELP rwb_http_requests_total Completed HTTP requests.");
        output.AppendLine("# TYPE rwb_http_requests_total counter");
        output.AppendLine("rwb_http_requests_total " + Interlocked.Read(ref requests).ToString(CultureInfo.InvariantCulture));
        output.AppendLine("# HELP rwb_http_errors_total HTTP requests returning 4xx or 5xx, or aborted by an exception.");
        output.AppendLine("# TYPE rwb_http_errors_total counter");
        output.AppendLine("rwb_http_errors_total " + Interlocked.Read(ref errors).ToString(CultureInfo.InvariantCulture));
        output.AppendLine("# HELP rwb_http_request_duration_seconds_total Sum of completed HTTP request durations in seconds.");
        output.AppendLine("# TYPE rwb_http_request_duration_seconds_total counter");
        output.AppendLine("rwb_http_request_duration_seconds_total " + (Interlocked.Read(ref durationTicks) / (double)TimeSpan.TicksPerSecond).ToString("R", CultureInfo.InvariantCulture));
        output.AppendLine("# HELP rwb_uptime_seconds Time since this application process started.");
        output.AppendLine("# TYPE rwb_uptime_seconds gauge");
        output.AppendLine("rwb_uptime_seconds " + Stopwatch.GetElapsedTime(started).TotalSeconds.ToString("R", CultureInfo.InvariantCulture));
        output.AppendLine("# HELP rwb_database_probe_success Whether the current metrics database probe succeeded.");
        output.AppendLine("# TYPE rwb_database_probe_success gauge");
        output.AppendLine("rwb_database_probe_success " + (pending is null ? "0" : "1"));
        output.AppendLine("# HELP rwb_outbox_pending Number of outbox rows awaiting publication; absent when the database probe fails.");
        output.AppendLine("# TYPE rwb_outbox_pending gauge");
        if (pending is not null)
            output.AppendLine("rwb_outbox_pending " + pending.Value.ToString(CultureInfo.InvariantCulture));
        return output.ToString();
    }
}

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
        foreach (var driver in DriverIdentities.Parse(configuration))
        {
            if (CryptographicOperations.FixedTimeEquals(token, Encoding.UTF8.GetBytes(driver.Value)))
            {
                var identity = new ClaimsIdentity(new[] { new Claim(ClaimTypes.NameIdentifier, driver.Key), new Claim(ClaimTypes.Role, "driver") }, "Bearer");
                return Task.FromResult(AuthenticateResult.Success(new AuthenticationTicket(new ClaimsPrincipal(identity), "Bearer")));
            }
        }
        return Task.FromResult(AuthenticateResult.Fail("Invalid access token"));
    }
}

public partial class Program;
