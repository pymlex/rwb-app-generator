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
        var failureCount = 0;
        while (!stoppingToken.IsCancellationRequested)
        {
            var published = await PublishBatch(producer, stoppingToken);
            failureCount = published ? 0 : Math.Min(failureCount + 1, 4);
            var delay = published ? 2 : Math.Min(30, 2 << failureCount);
            await Task.Delay(TimeSpan.FromSeconds(delay), stoppingToken);
        }
    }

    private async Task<bool> PublishBatch(IProducer<string, string> producer, CancellationToken stoppingToken)
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
            DeliveryResult<string, string> result;
            try
            {
                result = await producer.ProduceAsync("domain.events.v1", new Message<string, string> { Key = item.Key, Value = item.Payload }, stoppingToken);
            }
            catch (ProduceException<string, string> exception) when (!exception.Error.IsFatal && exception.Error.Code is
                ErrorCode.Local_MsgTimedOut or ErrorCode.Local_TimedOut or ErrorCode.Local_TimedOutQueue or
                ErrorCode.Local_Transport or ErrorCode.Local_AllBrokersDown or ErrorCode.Local_QueueFull or
                ErrorCode.Local_Resolve or ErrorCode.BrokerNotAvailable or ErrorCode.LeaderNotAvailable or
                ErrorCode.NotEnoughReplicas or ErrorCode.NotEnoughReplicasAfterAppend or
                ErrorCode.NetworkException or ErrorCode.RequestTimedOut)
            {
                await transaction.RollbackAsync(stoppingToken);
                logger.LogError(exception, "Kafka delivery failed for outbox event {Id}; batch remains pending, error code {Code}", item.Id, exception.Error.Code);
                return false;
            }
            if (result.Status != PersistenceStatus.Persisted)
            {
                await transaction.RollbackAsync(stoppingToken);
                logger.LogError("Kafka did not acknowledge durable persistence for outbox event {Id}; batch remains pending", item.Id);
                return false;
            }
            await using var mark = new NpgsqlCommand("UPDATE outbox SET published_at=now() WHERE id=$1", connection, transaction);
            mark.Parameters.AddWithValue(item.Id);
            await mark.ExecuteNonQueryAsync(stoppingToken);
        }
        await transaction.CommitAsync(stoppingToken);
        return true;
    }
}
