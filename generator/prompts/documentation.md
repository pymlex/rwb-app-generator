Generate exactly seven files: docs/system-analysis.md, docs/architecture.md, docs/api.md,
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
End README with a BibTeX software citation to https://github.com/pymlex/rwb-app-generator and
then the exact line: The project is under GPL-3.0 license.
Keep docs concise but cover all required sections. Each artifact must list the FR IDs it documents.
