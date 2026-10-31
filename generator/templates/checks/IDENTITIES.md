`DRIVER_TOKEN` still authenticates as subject `driver`, role `driver`; `ADMIN_TOKEN`
still authenticates as subject `admin`, role `admin`. Add optional application
configuration `DRIVER_TOKENS=id:token,id:token` to assign stable named driver
subjects. Tokens and ids must be distinct, ids cannot be `admin`, `driver` or
`system`, and malformed configuration fails startup without printing values.
Store this configuration only in the application's protected environment file.
The frontend continues to accept a single bearer token at sign-in.

`Actor.Owns`, `OwnedResource.Read` and `OwnedResource.Execute` check a persisted
owner subject and return the same 404 for a missing or foreign resource. Admins
retain access to existing resources. Mutation helpers must be called inside the
transaction holding the resource row lock; never pass an owner from request data.
Existing domain SQL must continue to scope lists and queries by `Actor.Subject`.
The legacy subject `driver` and its seeded records remain unchanged.

`backend-unit/IdentityAcceptance.cs` starts a real HTTP server with fixed fixture
credentials and an owned resource. It verifies legacy tokens, two named identities,
admin access, anonymous/invalid 401, foreign read/write 404 and no foreign callback.
It runs in the existing platform unit command without a database or model call.

Known limitation until VM acceptance: the platform fixture proves the helper and
authentication behavior. Each generated domain still needs its own acceptance
scenario creating an object as one named driver, then reading and mutating it as
another driver and asserting 404 plus unchanged persisted state. Source review
must verify that domain SQL uses persisted ownership and scopes collection queries.
Do not claim domain isolation from the platform fixture alone.

For a real generated domain, supply `OWNERSHIP_SCENARIO` with its actual contract.
Example structure (replace paths and fields with those from that domain):

```json
{"create":{"path":"/api/v1/items","body":{"name":"$unique"},"status":201},"id_field":"id","read":"/api/v1/items/{id}","mutate":{"method":"PATCH","path":"/api/v1/items/{id}","body":{"name":"forbidden-change"}}}
```

Store the non-secret scenario in `checks/ownership/scenario.json`, then run:

```bash
export OWNERSHIP_SCENARIO="$(cat checks/ownership/scenario.json)"
docker compose up -d --wait --wait-timeout 180 frontend
docker compose --profile checks run --rm ownership-acceptance
```

The service reads two named tokens from Compose's protected environment and writes
only verdicts to `reports/ownership.json`. A positive owner mutation control on
the same path/body prevents a missing route from passing as a foreign 404. It fails if identities/scenario are
missing. `verify --execute --deploy` and GitLab CI add this check when
`OWNERSHIP_SCENARIO` is configured. No configured scenario means domain isolation
remains the known limitation above; it is never inferred from the platform unit test.
