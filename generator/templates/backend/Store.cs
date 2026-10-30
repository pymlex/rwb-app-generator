using System.Text.Json;
using Npgsql;
using NpgsqlTypes;

public sealed class Store(NpgsqlDataSource database)
{
    public async Task Initialise()
    {
        foreach (var path in Directory.GetFiles(Path.Combine(AppContext.BaseDirectory, "migrations"), "*.sql").Order())
        {
            var sql = await File.ReadAllTextAsync(path);
            await using var command = database.CreateCommand(sql);
            await command.ExecuteNonQueryAsync();
        }
    }

    public async Task<JsonElement?> Get(string kind, string id)
    {
        await using var command = database.CreateCommand("SELECT body::text FROM documents WHERE kind=$1 AND id=$2");
        command.Parameters.AddWithValue(kind);
        command.Parameters.AddWithValue(id);
        var value = await command.ExecuteScalarAsync();
        return value is string json ? JsonSerializer.Deserialize<JsonElement>(json) : null;
    }

    public async Task<List<JsonElement>> List(string kind, int limit = 200)
    {
        await using var command = database.CreateCommand("SELECT body::text FROM documents WHERE kind=$1 ORDER BY updated_at DESC LIMIT $2");
        command.Parameters.AddWithValue(kind);
        command.Parameters.AddWithValue(Math.Clamp(limit, 1, 1000));
        await using var reader = await command.ExecuteReaderAsync();
        var result = new List<JsonElement>();
        while (await reader.ReadAsync())
            result.Add(JsonSerializer.Deserialize<JsonElement>(reader.GetString(0)));
        return result;
    }

    public async Task<bool> Save(string kind, string id, object body, string eventType, string actor, string? idempotencyKey = null)
    {
        await using var connection = await database.OpenConnectionAsync();
        await using var transaction = await connection.BeginTransactionAsync();
        if (idempotencyKey is not null)
        {
            await using var dedupe = new NpgsqlCommand("INSERT INTO idempotency(key) VALUES($1) ON CONFLICT DO NOTHING", connection, transaction);
            dedupe.Parameters.AddWithValue(kind + ":" + id + ":" + idempotencyKey);
            if (await dedupe.ExecuteNonQueryAsync() == 0)
                return false;
        }
        var json = JsonSerializer.Serialize(body, new JsonSerializerOptions(JsonSerializerDefaults.Web));
        await using var write = new NpgsqlCommand("INSERT INTO documents(kind,id,body) VALUES($1,$2,$3) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body,updated_at=now()", connection, transaction);
        write.Parameters.AddWithValue(kind);
        write.Parameters.AddWithValue(id);
        write.Parameters.AddWithValue(NpgsqlDbType.Jsonb, json);
        await write.ExecuteNonQueryAsync();
        var envelope = JsonSerializer.Serialize(new { eventId = Guid.NewGuid(), version = 1, type = eventType, occurredAt = DateTimeOffset.UtcNow, aggregateId = id, actor, data = body });
        await using var publish = new NpgsqlCommand("INSERT INTO outbox(aggregate_id,event_type,payload) VALUES($1,$2,$3)", connection, transaction);
        publish.Parameters.AddWithValue(id);
        publish.Parameters.AddWithValue(eventType);
        publish.Parameters.AddWithValue(NpgsqlDbType.Jsonb, envelope);
        await publish.ExecuteNonQueryAsync();
        await transaction.CommitAsync();
        return true;
    }
}
