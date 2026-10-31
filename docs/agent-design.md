# Agent orchestration design

The design separates analysis, architecture, implementation, review and verification so that each worker receives the evidence needed for its task within the jury model's context and rate limits. This is an engineering hypothesis to test, not a measured claim that adding agents improves application quality.

## Rationale

[MetaGPT](https://arxiv.org/abs/2308.00352) describes software engineering roles coordinated through standard procedures and intermediate outputs. We adopt explicit responsibilities, typed deliverables and intermediate checks. Its benchmark results do not establish performance for this project, Qwen or the hackathon cases.

[Agentless](https://arxiv.org/abs/2407.01489) shows why a simple localization, repair and validation process is a necessary comparison for more elaborate agent systems. Its task is repository issue repair rather than requirements-to-application generation. We therefore treat a simpler workflow as a baseline and retain deterministic validation instead of assuming agent autonomy is beneficial.

[Anthropic's multi-agent research report](https://www.anthropic.com/engineering/multi-agent-research-system) motivates separate worker contexts and clear delegation boundaries, while also describing token overhead and the difficulty of tightly dependent coding tasks. We apply scoped context and bounded effort. Its research-task gains and parallel execution results are not evidence of gains in our application generator.

[LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) supplies stateful graph orchestration and allows deterministic checks alongside model-driven work. Its [workflow and agent guide](https://docs.langchain.com/oss/python/langgraph/workflows-agents) distinguishes predefined workflows from agents that choose tools and actions. Graph nodes with different persona names alone do not demonstrate autonomous multi-agent behavior.

## Responsibilities and communication

The intended system has specialist workers coordinated by a supervisor policy:

- The analyst extracts source-grounded FRs, acceptance criteria and consequential questions.
- The architect converts reviewed analysis into shared API, data, event and screen contracts.
- Backend workers produce models, bounded service modules and routes against those contracts.
- The reviewer inspects source and returns structured defects with severity, file, exact evidence and affected FRs.
- Frontend workers consume actual backend contracts and split controller logic from presentation.
- The tester creates assertions against the business requirements. The documenter describes the supplied implementation.
- The supervisor routes build and review failures back to the relevant worker within a repair budget. Deterministic build, test and security gates decide execution outcomes.

All model roles use the same jury Qwen endpoint from the organiser VM. Different responsibilities do not imply different model providers or independent inference servers.

The communication unit is a validated artifact or a structured defect report. Durable run artifacts are the shared memory. Each worker's working memory is a fresh bounded context containing its assignment, selected requirements, applicable knowledge and permitted artifact slices. Passing an ever-growing conversation transcript to every worker would defeat this boundary.

Handoffs should identify sender, recipient, input artifact hashes and expected output. An artifact manifest records FR coverage, but coverage links alone cannot prove the requirement passed. Build errors, failed assertions and review findings are evidence for repairs. Reviewer approval cannot substitute for compiler or runtime results.

## Knowledge and tools

Role-specific retrieval selects relevant corporate documentation instead of appending the complete corpus. Retrieval selections and source hashes must remain observable so missing knowledge can be diagnosed. Contract-critical facts must be passed explicitly rather than left to a similarity search.

An optional bounded tool loop is being developed for `search_knowledge` and `read_artifact`. Its acceptance conditions are an explicit tool-call budget, role-specific file allowlists, bounded result size and logged tool requests and outcomes. Workers may request more relevant context before finalizing a structured artifact. This capability must not be described as operational until its tests and a VM run confirm it.

The distinction from persona prompt chaining is the combination of isolated worker memory, structured communication, bounded information-seeking decisions and feedback-driven supervisor routing. The current graph and skill loader are implementation components. End-to-end agent behavior and product correctness still require execution evidence.

## Resource and failure policy

Qwen calls run sequentially intentionally. They share the observed 30,000-token-per-minute jury limit, and application modules depend on common contracts. Agent count is not permission to issue concurrent requests against the same allowance.

Each request needs separate checks for estimated proxy reservation, native context capacity and output allowance. A request larger than the full rate window must be split or reduced. Waiting cannot make it valid. Retry a temporary rate window only when server evidence supports that diagnosis. A truncated output is a failed artifact, not a usable partial implementation. See [rate limit diagnosis](rate-limits.md).

Events should record role handoffs, selected skills, context size, token estimates, actual input/output/reasoning usage, cache hits, HTTP attempts, review findings, gate outcomes and repair routing. Content-addressed artifacts support reuse only when their effective inputs match. Full generation attempts, resumes, model calls and repair passes must be counted separately. No external tracing service is needed to retain these local run records.

## Ablation protocol

This is a planned comparison, not a completed experiment.

1. Freeze two unrelated synthetic business fixtures and an independent acceptance checklist before running either design. Never use the official hidden case before its evaluation slot.
2. Compare a simple fixed-stage baseline with the scoped-worker graph using the same jury Qwen, generic platform, fixtures, dependency versions, output requirements and total generation budget. Keep isolated output directories and record the exact generator revisions.
3. Compare full acceptance success first. Also record maximum request context, total input/output/reasoning tokens, wall time, model time, HTTP attempts and repair count. Retain failed runs and manual interventions.
4. Separate cold runs from cache-assisted resumes. Use repeated matched runs where the available budget permits, report sample sizes and do not infer statistical superiority from two fixtures.
5. If resources permit, disable scoped retrieval or model-selected tool requests one at a time. This distinguishes their contribution from code splitting, review feedback and simply spending more tokens.

The result should report observed tradeoffs, including cases where the simpler baseline succeeds more cheaply. Until these measurements exist, the defensible claim is that the design exposes context, contracts and feedback explicitly.
