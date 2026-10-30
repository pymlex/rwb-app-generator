# Architecture decisions

## ADR-001. Shared contract before code generation

Status: accepted by the implementation team, pending external review.

Independent backend and frontend prompts tend to drift in paths, names and domain states. A validated requirements model and an API blueprint precede implementation. The actual backend source is then supplied to frontend and acceptance-test generation.

A monolithic generation request would use fewer calls but would make local repair expensive and risk truncation. Uncoordinated role agents would permit more concurrency but require repeated reconciliation. Six bounded stages preserve a common contract while keeping completed work reusable.

The consequence is sequential generation of dependent artifacts. Concurrency is reserved for independent infrastructure operations. The responsibility belongs to team TLE.

## ADR-002. Fixed platform and generated domain modules

Status: accepted.

The generator owns platform dependencies, container configuration, authentication, rate limiting and the document outbox. Qwen owns the domain module, domain migration, Angular component, acceptance suite and domain documentation. Generated file paths are checked against an exact stage allowlist.

An unrestricted coding agent would support a broader solution space but could change the required stack or run arbitrary host commands. A fixed business application would fail the hidden case. A domain module on a fixed platform retains generality within the required stack and reduces infrastructure repair work.

Generated code is still untrusted code. Path validation is not a sandbox. Docker builds must run on dedicated infrastructure. Acceptance tests run without a Docker socket and cannot write to the mounted source directory.

## ADR-003. Local lexical knowledge retrieval

Status: accepted.

The organiser VM has 4 GB RAM. SQLite FTS5 provides offline document retrieval with BM25 ranking and no extra model, embedding endpoint or vector service. Chunks retain source names and SHA-256 fingerprints. Retrieval snapshots accompany each run.

Embedding retrieval could improve semantic matching but would add a service, evaluation burden and memory use. Lexical retrieval can miss paraphrases. The role prompts therefore retain a mandatory checklist while retrieved source material provides detailed corporate conventions.

## ADR-004. Transactional outbox

Status: accepted.

Business state and an event must either both commit or neither commit. The shared Store writes a JSON document, optional idempotency key and outbox row in one PostgreSQL transaction. Relational domain operations must apply the same rule within their own transaction.

A background publisher locks pending rows with SKIP LOCKED, publishes to Kafka using the aggregate ID as key and marks delivered rows. A crash after publication but before the database commit can cause redelivery. Consumers must deduplicate by eventId. Kafka producer idempotence does not make the database-to-broker handoff exactly once.

The prototype uses a single broker. Broker loss and backup policy remain production concerns.

## ADR-005. Angular PWA for mobile

Status: accepted based on the organisers' exported clarification of 30 October 2026.

The organisers permit PWA instead of Kotlin with equal evaluation treatment. A shared Angular implementation keeps mobile and admin workflows on one contract, avoids Android SDK installation on the VM and permits demonstration in a browser. Installation and browser geolocation need HTTPS outside localhost. Native background location tracking is outside this PWA prototype.
