using Npgsql;

public sealed partial class DomainService : IDomainService
{
    private readonly NpgsqlDataSource database;
    private readonly IConfiguration configuration;

    public DomainService(NpgsqlDataSource database, IConfiguration configuration)
    {
        this.database = database;
        this.configuration = configuration;
    }
}
