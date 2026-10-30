using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Npgsql;
using NpgsqlTypes;

public sealed record Actor(string Subject, bool IsAdmin)
{
    public static Actor From(HttpContext context) => new(
        context.User.FindFirstValue(ClaimTypes.NameIdentifier) ?? throw new InvalidOperationException("Authenticated subject is required"),
        context.User.IsInRole("admin"));
    public static Actor System => new("system", true);
}

public sealed record OperationResult<T>(int StatusCode, T? Data, string? Detail = null)
{
    public IResult ToHttp() => Detail is null
        ? Results.Json(Data, statusCode: StatusCode)
        : Results.Problem(Detail, statusCode: StatusCode);
}

public static class DomainJson
{
    public static readonly JsonSerializerOptions Options = new(JsonSerializerDefaults.Web);
    public static T Read<T>(string json) => JsonSerializer.Deserialize<T>(json, Options)
        ?? throw new InvalidOperationException("Persisted JSON is null");
    public static string Write<T>(T value) => JsonSerializer.Serialize(value, Options);
}

public static class DomainEvents
{
    public static async Task<Guid> Append(
        NpgsqlConnection connection, NpgsqlTransaction transaction,
        string aggregateId, string eventType, Actor actor, object data)
    {
        var eventId = Guid.NewGuid();
        var occurredAt = DateTimeOffset.UtcNow;
        var payload = DomainJson.Write(new { eventId, version = 1, type = eventType, occurredAt, aggregateId, actor = actor.Subject, data });
        await using var command = new NpgsqlCommand("INSERT INTO audit_events(event_id,aggregate_id,event_type,actor_id,payload,occurred_at) VALUES($1,$2,$3,$4,$5,$6); INSERT INTO outbox(aggregate_id,event_type,payload) VALUES($2,$3,$5)", connection, transaction);
        command.Parameters.AddWithValue(eventId);
        command.Parameters.AddWithValue(aggregateId);
        command.Parameters.AddWithValue(eventType);
        command.Parameters.AddWithValue(actor.Subject);
        command.Parameters.AddWithValue(NpgsqlDbType.Jsonb, payload);
        command.Parameters.AddWithValue(occurredAt);
        await command.ExecuteNonQueryAsync();
        return eventId;
    }
}

public static class RequestKeys
{
    public static async Task<OperationResult<T>> Execute<T>(
        NpgsqlDataSource database, Actor actor, string? key, string route,
        object request, Func<NpgsqlConnection, NpgsqlTransaction, Task<OperationResult<T>>> action)
    {
        if (key is null || !Regex.IsMatch(key, "\\A[A-Za-z0-9_.:-]{8,128}\\z"))
            return new(400, default, "Idempotency-Key must contain 8 to 128 permitted characters");
        var requestHash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(route + "\n" + DomainJson.Write(request))));
        await using var connection = await database.OpenConnectionAsync();
        await using var transaction = await connection.BeginTransactionAsync();
        await using var gate = new NpgsqlCommand("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", connection, transaction);
        gate.Parameters.AddWithValue(actor.Subject + ":" + key);
        await gate.ExecuteNonQueryAsync();
        await using var lookup = new NpgsqlCommand("SELECT request_hash,response::text,status_code FROM api_idempotency WHERE actor_id=$1 AND key=$2", connection, transaction);
        lookup.Parameters.AddWithValue(actor.Subject);
        lookup.Parameters.AddWithValue(key);
        await using var reader = await lookup.ExecuteReaderAsync();
        if (await reader.ReadAsync())
        {
            var existingHash = reader.GetString(0);
            var response = reader.GetString(1);
            var status = reader.GetInt32(2);
            await reader.CloseAsync();
            return existingHash == requestHash
                ? new(status, DomainJson.Read<T>(response))
                : new(409, default, "Idempotency-Key was already used for a different request");
        }
        await reader.CloseAsync();
        var result = await action(connection, transaction);
        if (result.StatusCode >= 400)
            return result;
        await using var remember = new NpgsqlCommand("INSERT INTO api_idempotency(actor_id,key,request_hash,response,status_code) VALUES($1,$2,$3,$4,$5)", connection, transaction);
        remember.Parameters.AddWithValue(actor.Subject);
        remember.Parameters.AddWithValue(key);
        remember.Parameters.AddWithValue(requestHash);
        remember.Parameters.AddWithValue(NpgsqlDbType.Jsonb, DomainJson.Write(result.Data));
        remember.Parameters.AddWithValue(result.StatusCode);
        await remember.ExecuteNonQueryAsync();
        await transaction.CommitAsync();
        return result;
    }
}
