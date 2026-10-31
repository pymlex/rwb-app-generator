Generate only the files explicitly listed at the end of this request. The complete set contains docs/system-analysis.md, docs/architecture.md, docs/api.md,
docs/user-guide.md, docs/development.md, docs/limitations.md and README.md.
Document the ACTUAL supplied backend and frontend rather than the unimplemented blueprint.
Use English. Do not use comments, emoji, prose parentheses, semicolons, filler, promotional adjectives,
or sections called Notes, Recommendations or Next steps. No claims that checks passed.
system-analysis.md must implement corporate templates: contents, revision history, accountable team,
approval status explicitly not reviewed, terms, source documents, purpose, scope, constraints,
measurable acceptance criteria, role permissions, use cases with preconditions, main flows,
alternatives, exceptions, postconditions, FR identifiers, NFRs, frontend screens and states,
backend services, relational data model with keys and constraints, API references, integrations,
metrics, security, performance targets marked as unmeasured, reliability, backup and retention,
assumptions, critical questions. Mark inapplicable template sections with reasons.
architecture.md must include Mermaid C4Context and C4Container diagrams and an ER diagram,
a UML sequence diagram with meaningful alternative branches, a state diagram where relevant,
and ADR sections covering context, status, alternatives, decision, consequences and responsible team.
Describe transactional outbox, at-least-once Kafka delivery and consumer eventId deduplication.
api.md must describe each actual endpoint: authorization, path/query/body parameters, requiredness,
types and bounds, example requests and responses, error codes, database interaction, transaction
and external integration. Link /swagger/index.html and /openapi/v1.json.
user-guide.md covers token entry, real user journeys, demo mode and interpreting domain states.
development.md covers module boundaries, migrations, CI, acceptance tests, extensions and handoff.
limitations.md must honestly describe token-based demo auth, HTTP versus HTTPS, missing enterprise
identity provider, Kafka single node, any prototype constraints, geospatial uncertainty where relevant,
and verification status as pending reports/summary.json. Never label planned features implemented.
README.md describes product, stack, prerequisites Docker Compose, environment setup using
python scripts/configure.py, docker compose up -d --build --wait frontend, localhost:8080,
docker compose --profile checks run --rm acceptance, documentation and evidence locations.
Do not add a project BibTeX citation or claim a sole author. Attribute the project to the team.
End README with the exact line: The project is under GPL-3.0 license.
Keep docs concise but cover all required sections. Each artifact must list the FR IDs it documents.
system-analysis.md also gives compact tables of domain events, input constraints per field and the error catalogue with HTTP status. It adds a traceability table from each FR to its endpoints and to the acceptance test prefix test_FR_nnn.
Do not invent person names, Jira tasks, reviewers, approval dates or versions. Write not specified for every unknown owner, approval, performance or deployment fact. The approval sheet uses the regulation status requires approval with the comment not reviewed and no approver name or date.
Revision history has columns version, task link, change, author and date, with the single row 1.0 by team TLE and date not specified. Responsible roles list customer, project manager, developer and analyst with names not specified.
Every use case has an ID from UC-001, a title, actors, preconditions, a numbered main flow, alternative flows AP1 onward, exception flows EX1 onward, postconditions, an expected result and the FR IDs it realises.
For every screen describe controls with visibility by role, enabled conditions and placeholder. Describe input fields with required flag, format, mask or regex and an example. Describe empty, loading, error and completion states. Map each field and action to the actual API method and request field. State that no design mockups or Figma links were supplied and that screens are described from the generated interface.
Describe every table with columns field, type, required, key and constraint. Include the platform tables documents, outbox, audit_events, api_idempotency, idempotency and schema_migrations. State the SQL naming convention actually used in the migrations, which is snake_case on the platform tables, and that the template text about camel case conflicts with its own order_id example.
system-analysis.md covers the nonfunctional sections for security, performance, scalability, reliability and recovery, backup and archiving, access management, logging, monitoring, audit and remote access. Mark every figure not measured by a run as an unmeasured target and give a reason for each section that is not applicable.
api.md opens with conventions stated once. They give transport security and version as configured, which is cleartext HTTP through Nginx on port 8080 and never HTTPS, the synchronous JSON exchange pattern, bearer authentication, common headers Authorization and Idempotency-Key, the shared RFC 7807 error model, rate limiting, pagination or its absence, timeouts, caching applicability and behaviour when the database or broker is unavailable.
Per endpoint api.md adds purpose, revision 1.0, permitted roles, enum values, defaults, formats and lengths, validation rules, tables read or written, and the algorithm as main flow and exception flow. Group endpoints compactly and do not repeat the shared conventions.
architecture.md states that Mermaid code blocks are the editable Markdown equivalent of the Confluence PlantUML macro and that nothing is published to Confluence.
architecture.md documents the event contract as a table of event types with trigger, aggregate and payload fields. It gives the envelope eventId, version, type, occurredAt, aggregateId, actor and data, the Kafka topic domain.events.v1 keyed by aggregateId, the polling publisher, at-least-once delivery and consumer deduplication. It describes any external integration as an adapter with message schema, trigger, frequency and a sequence diagram, or states that none exists.
Write an ADR only for a real choice evidenced by the requirements, the fixed platform or the generated design. Each ADR lists at least two alternatives, each with benefits and costs. Use status proposed unless an approval is evidenced.
development.md includes the service description from the service template. It has a technology table with application type, frameworks, system software and Swagger link, resource requirements as defined in docker-compose.yml with database 512 MB, Kafka 640 MB, backend 384 MB and frontend 96 MB, tested operating limits stated as not measured, fault tolerance, authorization, environments Prod, Stage and Test with absent and the reason where none exists, build, deployment and configuration. It has a table of environment and CI variables with purpose and never values, covering POSTGRES_PASSWORD, ADMIN_TOKEN, DRIVER_TOKEN, APP_PORT and APP_ENV_FILE. It describes network connectivity with only the frontend port published, build and deployment on the GitLab runner tagged organiser-vm, and access as not specified.
limitations.md states that the service template items Zabbix OS and Docker monitoring and Elasticsearch and Kibana log shipping are not part of the prototype. Describe recovery as an operator action and never claim automatic restart or a restart endpoint unless the supplied evidence shows one.
README.md links the verification outputs reports/verification.md and reports/summary.json and, when present, docs/test-report.md and docs/security-report.md. It states that these reports come from the verification command and not from documentation generation.
