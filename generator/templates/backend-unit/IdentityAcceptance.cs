using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Security.Claims;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Rwb.Platform.Unit;

internal static class IdentityAcceptance
{
    private const string AliceToken = "fixture-alice-access-token";
    private const string BobToken = "fixture-bob-access-token";
    private const string LegacyToken = "fixture-legacy-access-token";
    private const string AdminToken = "fixture-admin-access-token";

    public static async Task Run()
    {
        foreach (var invalid in new[]
        {
            "alice", "alice:", "admin:token", "system:token", "driver:token", ":token",
            "alice:token,bob:token", "alice:one,alice:two", "alice:has space", "alice:token,",
            "alice:" + LegacyToken, "alice:" + AdminToken
        })
        {
            var rejected = false;
            try { DriverIdentities.Parse(Configuration(invalid)); }
            catch (InvalidOperationException) { rejected = true; }
            Require(rejected, "Malformed or ambiguous driver configuration was accepted");
        }
        Require(DriverIdentities.Parse(Configuration("")).Count == 0, "Legacy configuration must remain valid");
        Require(!new Actor("alice", false).Owns("ALICE"), "Owner comparison must remain case-sensitive");
        Require(OwnedResource.Read<object>(Actor.System, null, null).StatusCode == 404, "Missing objects must remain missing for admins");

        var builder = WebApplication.CreateSlimBuilder();
        builder.Logging.ClearProviders();
        builder.Configuration.AddConfiguration(Configuration($"alice:{AliceToken},bob:{BobToken}"));
        builder.Services.AddAuthentication("Bearer")
            .AddScheme<AuthenticationSchemeOptions, TokenHandler>("Bearer", null);
        builder.Services.AddAuthorization();
        await using var app = builder.Build();
        app.Urls.Add("http://127.0.0.1:0");
        app.UseAuthentication();
        app.UseAuthorization();
        app.MapGet("/me", (HttpContext context) => new
        {
            subject = context.User.FindFirstValue(ClaimTypes.NameIdentifier),
            role = context.User.FindFirstValue(ClaimTypes.Role)
        }).RequireAuthorization();
        var mutations = 0;
        app.MapGet("/owned", (HttpContext context) =>
            OwnedResource.Read(Actor.From(context), "alice", new { id = "owned-by-alice" }).ToHttp())
            .RequireAuthorization();
        app.MapPost("/owned", async Task<IResult> (HttpContext context) =>
        {
            var result = await OwnedResource.Execute(Actor.From(context), "alice", () =>
            {
                mutations++;
                return Task.FromResult(new OperationResult<string>(200, "updated"));
            });
            return result.ToHttp();
        }).RequireAuthorization();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(15));
        await app.StartAsync(timeout.Token);
        try
        {
            using var client = new HttpClient(new SocketsHttpHandler { UseProxy = false })
            { BaseAddress = new Uri(app.Urls.Single()), Timeout = TimeSpan.FromSeconds(5) };
            foreach (var (token, subject, role) in new[]
            {
                (AliceToken, "alice", "driver"), (BobToken, "bob", "driver"),
                (LegacyToken, "driver", "driver"), (AdminToken, "admin", "admin")
            })
            {
                client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);
                var me = await client.GetFromJsonAsync<Identity>("/me");
                Require(me?.Subject == subject && me.Role == role, "Token changed its subject or role");
                var expected = subject is "alice" or "admin" ? HttpStatusCode.OK : HttpStatusCode.NotFound;
                using var read = await client.GetAsync("/owned");
                Require(read.StatusCode == expected, "A foreign object was exposed instead of returning 404");
                var before = mutations;
                using var write = await client.PostAsync("/owned", null);
                Require(write.StatusCode == expected, "A foreign mutation did not return 404");
                Require(mutations == before + (expected == HttpStatusCode.OK ? 1 : 0), "Foreign mutation callback executed");
            }
            client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", "invalid-token");
            using var invalid = await client.GetAsync("/me");
            Require(invalid.StatusCode == HttpStatusCode.Unauthorized, "Unknown token was accepted");
            client.DefaultRequestHeaders.Authorization = null;
            using var anonymous = await client.GetAsync("/owned");
            Require(anonymous.StatusCode == HttpStatusCode.Unauthorized, "Anonymous access was accepted");
        }
        finally { await app.StopAsync(); }
    }

    private static IConfiguration Configuration(string drivers) => new ConfigurationBuilder()
        .AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["DRIVER_TOKENS"] = drivers, ["DRIVER_TOKEN"] = LegacyToken, ["ADMIN_TOKEN"] = AdminToken
        }).Build();

    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private sealed record Identity(string Subject, string Role);
}
