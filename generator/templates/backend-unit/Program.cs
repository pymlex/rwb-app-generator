using System.Security.Claims;
using System.Text.Json;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Npgsql;

namespace Rwb.Platform.Unit;

internal static class Runner
{
    public static async Task<int> Main()
    {
        var cases = new List<(string Name, Func<Task> Execute)>
        {
            ("DomainJson writes camelCase and round-trips immutable records", JsonRoundTrip),
            ("DomainJson reads differently cased web fields without losing values", JsonCaseInsensitive),
            ("DomainJson rejects null instead of silently returning an empty record", JsonNullRejected),
            ("Actor preserves string driver subjects and role boundaries", DriverIdentity),
            ("Actor recognizes the admin role independently of subject text", AdminIdentity),
            ("Actor rejects an identity missing its subject", MissingIdentityRejected),
            ("OperationResult preserves successful response status and payload", SuccessResult),
            ("Named driver tokens and owner isolation pass real HTTP acceptance", IdentityAcceptance.Run)
        };
        foreach (var status in new[] { 400, 403, 409, 422 })
            cases.Add(($"OperationResult preserves problem response {status}", () => ProblemResult(status)));
        foreach (var input in new (string Name, string? Key)[]
        {
            ("null", null),
            ("empty", ""),
            ("too short", new string('a', 7)),
            ("too long", new string('a', 129)),
            ("space", "abcd efgh"),
            ("slash", "abcd/efgh"),
            ("trailing newline", "abcdefgh\n"),
            ("embedded newline", "abcd\nefgh"),
            ("unicode", "abcdéefgh")
        })
            cases.Add(($"RequestKeys rejects {input.Name} before opening a connection", () => InvalidKey(input.Key)));
        var failures = 0;
        foreach (var test in cases)
        {
            try
            {
                await test.Execute();
                Console.WriteLine($"PASS {test.Name}");
            }
            catch (AssertionFailure failure)
            {
                failures++;
                Console.Error.WriteLine($"FAIL {test.Name}: {failure.Message}");
            }
        }
        Console.WriteLine($"Platform unit checks: {cases.Count}, failures: {failures}");
        return failures == 0 ? 0 : 1;
    }

    private static readonly Snapshot Original = new(
        Guid.Parse("5a55f510-b031-4935-818b-173723df6851"),
        23,
        12.75m,
        DateTimeOffset.Parse("2026-10-30T12:30:00+00:00", System.Globalization.CultureInfo.InvariantCulture));

    private static Task JsonRoundTrip()
    {
        var json = DomainJson.Write(Original);
        using var parsed = JsonDocument.Parse(json);
        Ensure(parsed.RootElement.TryGetProperty("itemId", out _), "Web serialization must use itemId");
        Ensure(!parsed.RootElement.TryGetProperty("ItemId", out _), "CLR property casing must not leak into the web contract");
        Ensure(DomainJson.Read<Snapshot>(json) == Original, "Immutable values changed during serialization");
        return Task.CompletedTask;
    }

    private static Task JsonCaseInsensitive()
    {
        var json = "{\"ITEMID\":\"5a55f510-b031-4935-818b-173723df6851\",\"QUANTITY\":23,\"AMOUNT\":12.75,\"CHANGEDAT\":\"2026-10-30T12:30:00+00:00\"}";
        Ensure(DomainJson.Read<Snapshot>(json) == Original, "Web field casing reset persisted record values");
        return Task.CompletedTask;
    }

    private static Task JsonNullRejected()
    {
        var rejected = false;
        try
        {
            DomainJson.Read<Snapshot>("null");
        }
        catch (InvalidOperationException)
        {
            rejected = true;
        }
        Ensure(rejected, "Null storage content must be rejected");
        return Task.CompletedTask;
    }

    private static Task DriverIdentity()
    {
        var context = Context("driver-subject", "driver");
        var actor = Actor.From(context);
        Ensure(actor.Subject == "driver-subject", "String subject was changed or coerced into an identifier");
        Ensure(!actor.IsAdmin, "A driver gained admin privileges");
        return Task.CompletedTask;
    }

    private static Task AdminIdentity()
    {
        var actor = Actor.From(Context("person-17", "admin"));
        Ensure(actor.Subject == "person-17" && actor.IsAdmin, "Admin identity did not preserve its claims");
        var impersonator = Actor.From(Context("admin", "driver"));
        Ensure(!impersonator.IsAdmin, "Subject text must not grant an admin role");
        return Task.CompletedTask;
    }

    private static Task MissingIdentityRejected()
    {
        var rejected = false;
        try
        {
            Actor.From(new DefaultHttpContext());
        }
        catch (InvalidOperationException)
        {
            rejected = true;
        }
        Ensure(rejected, "Missing identity must not receive a default subject");
        return Task.CompletedTask;
    }

    private static Task SuccessResult()
    {
        var result = new OperationResult<Snapshot>(201, Original).ToHttp();
        Ensure(result is IStatusCodeHttpResult { StatusCode: 201 }, "Created result lost its HTTP status");
        Ensure(result is IValueHttpResult { Value: Snapshot value } && value == Original, "Created result lost its payload");
        return Task.CompletedTask;
    }

    private static Task ProblemResult(int status)
    {
        const string detail = "The requested state transition conflicts with persisted state";
        var result = new OperationResult<Snapshot>(status, null, detail).ToHttp();
        Ensure(result is IStatusCodeHttpResult code && code.StatusCode == status, "Problem result lost its HTTP status");
        Ensure(result is IValueHttpResult { Value: ProblemDetails problem } && problem.Detail == detail && problem.Status == status,
            "Problem result must preserve its structured failure details");
        return Task.CompletedTask;
    }

    private static async Task InvalidKey(string? key)
    {
        await using var database = NpgsqlDataSource.Create("Host=127.0.0.1;Port=1;Database=unreachable;Username=unit;Timeout=1;Pooling=false");
        var invoked = false;
        var result = await RequestKeys.Execute<Snapshot>(
            database,
            new Actor("driver-subject", false),
            key,
            "/api/v1/unit-only",
            Original,
            (_, _) =>
            {
                invoked = true;
                return Task.FromResult(new OperationResult<Snapshot>(201, Original));
            });
        Ensure(result.StatusCode == 400, "Malformed request key was accepted");
        Ensure(!invoked, "Malformed request key reached the transactional mutation");
        Ensure(result.Detail is not null, "Rejected request key must explain its validation failure");
    }

    private static DefaultHttpContext Context(string subject, string role) => new()
    {
        User = new ClaimsPrincipal(new ClaimsIdentity(new[]
        {
            new Claim(ClaimTypes.NameIdentifier, subject),
            new Claim(ClaimTypes.Role, role)
        }, "unit"))
    };

    private static void Ensure(bool condition, string detail)
    {
        if (!condition)
            throw new AssertionFailure(detail);
    }

    private sealed class AssertionFailure(string message) : Exception(message);
    public sealed record Snapshot(Guid ItemId, int Quantity, decimal Amount, DateTimeOffset ChangedAt);
}
