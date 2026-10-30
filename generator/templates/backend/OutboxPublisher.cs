using Confluent.Kafka;
using Npgsql;

public sealed class OutboxPublisher(NpgsqlDataSource database, IConfiguration configuration, ILogger<OutboxPublisher> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var bootstrap = configuration["KAFKA_BOOTSTRAP_SERVERS"] ?? "kafka:9092";
        using var producer = new ProducerBuilder<string, string>(new ProducerConfig
        {
            BootstrapServers = bootstrap,
            EnableIdempotence = true,
            MessageTimeoutMs = 10000,
            Acks = Acks.All
        }).Build();
        while (!stoppingToken.IsCancellationRequested)
        {
            await using var connection = await database.OpenConnectionAsync(stoppingToken);
            await using var transaction = await connection.BeginTransactionAsync(stoppingToken);
            await using var read = new NpgsqlCommand("SELECT id,aggregate_id,payload::text FROM outbox WHERE published_at IS NULL ORDER BY id LIMIT 20 FOR UPDATE SKIP LOCKED", connection, transaction);
            await using var reader = await read.ExecuteReaderAsync(stoppingToken);
            var pending = new List<(long Id, string Key, string Payload)>();
            while (await reader.ReadAsync(stoppingToken))
                pending.Add((reader.GetInt64(0), reader.GetString(1), reader.GetString(2)));
            await reader.CloseAsync();
            foreach (var item in pending)
            {
                var result = await producer.ProduceAsync("domain.events.v1", new Message<string, string> { Key = item.Key, Value = item.Payload }, stoppingToken);
                if (result.Status != PersistenceStatus.Persisted)
                {
                    logger.LogError("Kafka did not persist outbox event {Id}", item.Id);
                    break;
                }
                await using var mark = new NpgsqlCommand("UPDATE outbox SET published_at=now() WHERE id=$1", connection, transaction);
                mark.Parameters.AddWithValue(item.Id);
                await mark.ExecuteNonQueryAsync(stoppingToken);
            }
            await transaction.CommitAsync(stoppingToken);
            await Task.Delay(TimeSpan.FromSeconds(2), stoppingToken);
        }
    }
}
