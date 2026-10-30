# Requirements compliance

This is a derived checklist for the full pipeline track. It does not replace the organiser requirements. An unchecked item is pending independent evidence, even when a template or generation prompt exists. The baseline below was reviewed on 30 October 2026 before a successful complete application run. Generated application paths are relative to its output directory. Repository paths describe the generator.

## Sources and precedence

- **CASE**: the primary full-cycle corporate application pipeline case. References below name its original section headings and numbered stages.
- **SLIDES**: the Russtech case presentation. Its technology stack and parking scenario were compared with CASE.
- **SA**: the supplied system analysis documentation rules. The permitted derived text is [system-analysis-rules.txt](../knowledge/sources/system-analysis-rules.txt).
- **REQ**: the full requirements document template. The permitted derivative is [requirements-template.txt](../knowledge/sources/requirements-template.txt).
- **SERVICE**: the service description template. The permitted derivative is [service-template.txt](../knowledge/sources/service-template.txt).
- **API**: the method description template. The permitted derivative is [api-template.txt](../knowledge/sources/api-template.txt).
- **ADR**: the architecture decision template. The permitted derivative is [adr-template.txt](../knowledge/sources/adr-template.txt).
- **CLARIFICATIONS**: organiser answers from 27 and 30 October 2026. This document records the decisions relevant to implementation without publishing the chat export or personal messages.
- **USER**: project instructions require exclusive use of the organiser VM and Qwen API, confidentiality of original source files and credentials, team attribution and a collaborative branch workflow.

CASE defines the deliverable. Explicit organiser clarifications resolve Kotlin versus PWA and the scope of the required technology stack. Template examples are not invented customer requirements. An inapplicable template section must have a specific reason. Unknown approval, ownership, performance or deployment facts must remain unknown rather than being fabricated.

## Interpretation decisions

- The deliverable is a reusable requirements-to-application pipeline. A manually implemented parking application alone does not satisfy the selected full pipeline track. CASE, Subject of development.
- Business requirements are the only domain input. Generic stack templates, corporate rules, retrieval skills and a small number of consequential clarification answers are allowed. CASE, Task and Subject of development.
- Angular and C# are compulsory in generated applications. The generator may use Python, LangGraph or other orchestration technology. CLARIFICATIONS, 27 October FAQ and 30 October 11:50, 12:09 and 13:07.
- An Angular PWA is an accepted substitute for the native Kotlin mobile client without a score penalty. A driver mobile interface and the administrative web interface are still required for parking. CLARIFICATIONS, 27 October FAQ and 30 October 12:18 and 12:58.
- The prescribed model generates project artifacts. The user's stricter instruction allows only the jury Qwen API from the organiser VM. No external provider or local replacement model is authorised. CASE, Technology stack, and USER.
- Kafka belongs in generated applications when events are exchanged. It is not a requirement for the generator. Organisers say it is not universally mandatory but is required by their corporate event exchange convention. CLARIFICATIONS, 30 October 15:01 and 15:27.
- GitLab CI/CD or a comparable automated build, test and deployment mechanism is permitted by CASE, Stage 6. CASE, Expected result, separately requests a repository in the local GitLab. GitHub does not by itself prove that submission requirement. The CI runner belongs on the team's VM. CLARIFICATIONS, 30 October 14:53.
- The limit of three evaluated generations concerns whole generation attempts during evaluation. It is not a limit of three LLM calls, agents or development runs. Calls, retries, output reasoning tokens and full run duration must still be measured. CASE, Efficiency measurement, and CLARIFICATIONS, 30 October 15:01.
- The real hidden case must first be run and built during official evaluation. An unrelated synthetic fixture is only a readiness test and must never be presented as the hidden case. CASE, Expected result.
- The stack specifies PostgreSQL 17.9 with Debian package version `17.9-1.pgdg12+1`. Matching the major version or an image tag alone is insufficient evidence. CASE and SLIDES, Technology stack.
- `postgis-jdbc 2.5.0` is a JDBC client entry in CASE. It does not justify adding a Java runtime to the required C# backend. Document its inapplicability to the Npgsql client while providing actual PostgreSQL/PostGIS functionality. SLIDES lists PostGIS without a JDBC client version.

## Pipeline and analysis

- [ ] **GEN-01** Accept previously unseen business requirements and complete the lifecycle without domain-specific manual code changes. Pointers: `generator/pipeline.py`, `generator/agents.py`, `main.py`. Evidence: successful parking and unrelated synthetic runs on the same generator revision. Source: CASE, Subject of development and Stages 1–7.
- [ ] **GEN-02** Persist generated source, documents, infrastructure, test results and provenance as repository-ready artifacts. Evidence: artifact manifest and clean generated repository. Pointers: `generator/storage.py`, generated `.pipeline/` and `reports/`. Source: CASE, Subject of development and Expected result.
- [ ] **GEN-03** Identify goals, roles, FRs, NFRs, constraints, entities, scenarios, integration points, security, acceptance criteria, risks and ambiguities. Evidence: reviewed `analysis.json` and `docs/system-analysis.md`. Pointers: `generator/models.py`, `generator/prompts/analysis.md`. Source: CASE, Stage 1.
- [ ] **GEN-04** Give each FR a stable identifier and trace it to the original business statement, implementation and meaningful acceptance assertions. Merely associating every passed check with every FR is insufficient. Pointers: `generator/models.py`, `generator/verification.py`, generated `reports/traceability.json`. Source: CASE, Stages 2 and 5, and SA §3.
- [ ] **GEN-05** Separate customer requirements, assumptions, unresolved questions and explicit answers. Stop for critical ambiguities and ask only questions that affect architecture, security or the user journey. Evidence: questions and answer provenance with no silent defaults for blocking decisions. Source: CASE, Subject of development and Stage 2.
- [ ] **GEN-06** Keep API contracts, database model, documentation, UI calls and implemented behavior consistent. Evidence: typed contracts, build results, endpoint assertions and independent artifact review. Pointers: backend generation stages and generated OpenAPI. Source: CASE, Stage 2.
- [ ] **GEN-07** Restrict each role to relevant skills and artifacts while preserving required information across handoffs. Evidence: stage inputs, retrieval selections, token budgets and persisted communication. Pointers: `generator/knowledge.py`, `generator/budget.py`, `generator/agents.py`. Source: CASE, minimal intervention and efficiency, plus USER multi-agent instruction.

## System analysis and corporate documentation

- [ ] **DOC-01** Produce a separate Markdown analysis containing purpose, scope, role permissions, use cases, FRs, NFRs, components, data model, contracts, events, integrations, input constraints, errors, acceptance criteria, assumptions and questions. Pointer: `generator/prompts/documentation.md`. Evidence: actual generated `docs/system-analysis.md`. Source: CASE, Stage 2.
- [ ] **DOC-02** Include contents, revision history, responsible roles, truthful approval status, terminology, source references, business purpose, limits and measurable success criteria. Do not invent names, Jira tasks, reviewers or approvals. Source: SA §2 and REQ §2.
- [ ] **DOC-03** Give use cases an ID, actors, preconditions, main flow, alternatives, exception flow, postconditions and expected result. Source: SA §2.5 and REQ §2.5.6.
- [ ] **DOC-04** Preserve editable UML sequence diagrams and applicable structural diagrams. README Mermaid alone does not replace generated product diagrams. Explain the Markdown equivalent of Confluence-specific macros rather than claiming Confluence publication. Source: SA §2.6, REQ §2.5.7 and USER Mermaid instruction.
- [ ] **DOC-05** Describe each screen's controls, visibility and enabled states, required fields, masks or regexes, empty and error states, completion behavior and field-to-backend mapping. Link each action to the actual API method. Document absent design mockups explicitly. Source: SA §3.1 and REQ §3.1.
- [ ] **DOC-06** Describe database tables, field types, requiredness, PKs, FKs, constraints and relationships with an ER diagram where useful. Resolve the template's inconsistent naming prose by adopting one documented SQL convention. Source: SA §3.2.3 and REQ §3.2.3.
- [ ] **DOC-07** For every actual endpoint document purpose, revision, authentication, permitted roles, headers, path/query/body models, requiredness, enums, defaults, lengths, formats, bounds, examples, success and error responses, table interaction, algorithm, validation and external dependencies. Include Swagger and OpenAPI links. Source: API and SA §3.2.4.
- [ ] **DOC-08** Document transport security and version, exchange pattern, pagination, timeout, caching applicability, source-to-API mapping and failure behavior. Do not claim HTTPS when the prototype serves HTTP. Source: SA §3.2.4.
- [ ] **DOC-09** Document internal and external integration message schemas, triggers, frequency, security and sequence diagrams. Source: SA §3.2.1 and §3.3.
- [ ] **DOC-10** Include actual service technology, links, resource requirements, tested operating limits, failure behavior, auth, existing and absent environments, build, deployment, configuration, CI variables, network connectivity and access. Source: SERVICE and SA §3.2.2.
- [ ] **DOC-11** Document security, performance, scalability, recovery, backups, retention, access management, audit, remote support and monitoring. Separate unmeasured targets from measured results. Source: SA §3.4 and §4, REQ §4.
- [ ] **DOC-12** For material architectural decisions record context, status, alternatives with benefits and costs, decision, consequences and responsible team. Source: ADR.
- [ ] **DOC-13** Produce product description, architecture, API and data model, launch instructions, user guide, development handoff, testing and security reports and known limitations. Source: CASE, Stage 7.

## Generated application, infrastructure and security

- [ ] **APP-01** Pin Angular 20.1.6, .NET 10 and C# 14. Evidence: resolved dependency versions and compiler output on the organiser VM. Pointers: `generator/templates/frontend/package.json`, backend project and Dockerfiles. Source: CASE and SLIDES, Technology stack.
- [ ] **APP-02** Prove PostgreSQL package `17.9-1.pgdg12+1` and functional PostGIS. Evidence: `dpkg-query`, server version, `PostGIS_Full_Version()` and a real geospatial assertion. Pointer: `generator/templates/database/Dockerfile`. Current image template does not yet prove the Debian package version. Source: CASE and SLIDES, Technology stack.
- [ ] **APP-03** Apply the selected UI Kit consistently and implement responsive layouts, main and alternate paths, loading, empty and error states, access restrictions and feedback. Evidence: browser inspection and real backend user journeys. Pointers: Angular Material template and frontend generation prompts. Source: CASE, Stage 3.
- [ ] **APP-04** Use real persistence and backend operations for core logic. Mocks are allowed only for documented external integrations. No success response may substitute for missing business behavior. Source: CASE, Stages 3–4.
- [ ] **APP-05** Provide versioned OpenAPI with typed requests and responses, requiredness, length and format checks, regexes where relevant, uniform errors, auth, authorization, rate limits, critical-operation idempotency and logging. Evidence: positive, negative, cross-role and replay assertions. Pointers: `generator/templates/backend/Program.cs`, `DomainSupport.cs`, generated domain code. Source: CASE, API and events requirements.
- [ ] **APP-06** Give events a documented domain schema, version, ID, occurrence time and replay rules. Verify transactional persistence, Kafka delivery and duplicate handling rather than only starting the broker. Pointers: `OutboxPublisher.cs`, `DomainSupport.cs`, migrations and generated event contracts. Source: CASE, API and events requirements.
- [ ] **APP-07** Supply Dockerfiles, Compose, variable configuration, migrations, idempotent initialisation, health checks, demo data and launch instructions. Evidence: clean build and launch without source editing. Source: CASE, Stage 6.
- [ ] **APP-08** Supply application `/metrics` and document service health as Healthy, Degraded or Unhealthy with meaningful database and broker criteria. The template's OS/Docker Zabbix and Elasticsearch/Kibana infrastructure must either exist with evidence or be explicitly marked inapplicable to the isolated prototype with reasons. Pointer: backend platform and generated operations documentation. Source: SERVICE, Monitoring and Logging.
- [ ] **APP-09** Address SERVICE's restart endpoint requirement explicitly. Any restart capability must have restricted administration access and a defined scope. Document container restart policy and operational recovery as the chosen prototype mechanism where applicable. Do not add unrestricted host controls or a Docker socket to the application. Source: SERVICE, Application monitoring, and CASE, security.
- [ ] **APP-10** Run automated build, unit, integration, API, core-scenario, static-analysis, dependency and CVE checks. Save execution logs, defects, severity and final status. Scanner configuration alone is not a passing result. Pointers: `generator/verification.py`, generated tests and `reports/`. Source: CASE, Stage 5.
- [ ] **APP-11** Demonstrate automated build, test and deployment with retained artifacts on the organiser VM. Confirm GitLab 19.4.2 submission access or document the accepted equivalent automation separately from repository submission. Pointers: generated `.gitlab-ci.yml` and CLI verifier. Source: CASE, Stage 6 and Expected result, plus CLARIFICATIONS.
- [ ] **APP-12** Keep API keys, passwords, tokens, raw source PDFs, explanation and chat exports out of all published history and logs. Allowed derivatives must contain no embedded credentials. Evidence: secret and filename history audit of all published refs. Source: CASE, Stage 6, and USER.

## Parking acceptance case

Every item below requires generated implementation, API evidence and visible driver/admin behavior where applicable. The provider data contains street geometries. Proximity to a supplied LINESTRING must not be described as an authoritative official zone polygon. A provider segment identifier must not be silently relabelled as the official zone number. Missing boundary or official numbering data requires an explicit limitation and a documented demo geometry policy.

- [ ] **PARK-01** Determine a vehicle location from GPS or a real advancing demo route. Source: CASE, Appendix §3 and §5.
- [ ] **PARK-02** Determine paid-area membership, show zone identification, supplied or explicitly synthetic boundaries and available parking parameters. Test coordinate units and entry/exit thresholds. Source: Appendix §3.
- [ ] **PARK-03** Persist an active session, its vehicle and owner, end time and state. Repeat and concurrent requests must not create contradictory sessions. Source: Appendix §3–4 and API idempotency requirement.
- [ ] **PARK-04** Track movement and distinguish initial entry, remaining in an area, exit and transition to another area. Source: Appendix §3 and §6 steps 1–3 and 7–8.
- [ ] **PARK-05** Start or confirm a session through the driver UI and show its actual persisted expiry and remaining time. Source: Appendix §6 steps 4–5.
- [ ] **PARK-06** Emit and display the ten-minute warning and expiry behavior. A controllable demo clock may accelerate time but must exercise the same domain logic and prevent repeated duplicate warnings. Source: Appendix §3 and §6 step 6.
- [ ] **PARK-07** Warn on exit and zone transition and prompt the driver to check whether new payment is needed. Do not silently invent refunds or cancel paid periods without an explicit decision. Source: Appendix §3 and §6 step 8.
- [ ] **PARK-08** Provide the official payment destination and a replaceable adapter/mock for unavailable external provider integration. No real payment or proprietary payment mechanism is required. Source: Appendix §5.
- [ ] **PARK-09** Show a driver map, current area, session status, countdown, notifications, payment action, route and session history. Source: Appendix §3–4.
- [ ] **PARK-10** Show vehicles, areas, active sessions, routes, events and history in the Angular admin interface with actual role enforcement. Source: Appendix §4.
- [ ] **PARK-11** Complete all nine demonstration steps and retain event/history evidence. Restart the application and verify state persists and seeds do not duplicate. Source: Appendix §6 and CASE, Stage 6.

## Evaluation and delivery gate

- [ ] **EVAL-01** Keep immutable run identity and distinguish full generation attempts, resumes, per-stage model calls, HTTP retries, repairs, cache hits and manual clarification. Report input, output and reasoning tokens, model duration, full duration and build/test/deployment status. Pointers: `.pipeline/events.jsonl`, `generator/verification.py`, generated `reports/summary.json`. Source: CASE, Efficiency measurement.
- [ ] **EVAL-02** Demonstrate a repeat run without corrupting artifacts, duplicate initial data or silent reuse of stale requirements. Source: CASE, Efficiency and reproducibility criteria.
- [ ] **EVAL-03** Complete the preparation case and an unrelated synthetic fixture without bespoke fixes to generated domain code. Record the exact generator revision, inputs and retained evidence. Source: CASE, universal pipeline and Expected result.
- [ ] **EVAL-04** Preserve the official hidden case for its evaluation slot and enforce at most three whole evaluated generation attempts using the demonstration key. Do not count synthetic fixtures as official evidence. Source: CASE, Expected result, and CLARIFICATIONS.
- [ ] **EVAL-05** Provide the expert an accessible deployed prototype, clean-environment launch instructions, source repository and evidence artifacts. Account for the organiser's pre-recorded solution presentation requirement without claiming it has been recorded. Source: CASE, Expected result, and CLARIFICATIONS, submission instructions.

Completion means all applicable items above have named evidence and reviewed results. No complete run, clean deployment, security clearance or full requirement coverage is claimed by this checklist.
