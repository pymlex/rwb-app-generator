# RWB App Generator

Team TLE builds a requirements-driven application generator for the RWB hackathon. Business requirements are the domain input. Qwen3.8-27B produces system analysis, API contracts, domain code, an Angular interface, acceptance tests and handover documentation.

The generated stack is Angular 20.1.6 with Angular Material and PWA support, ASP.NET Core on .NET 10, PostgreSQL with PostGIS, Kafka and Docker Compose. Python orchestrates generation. Corporate documentation is indexed locally with SQLite FTS5 and retrieved with source hashes.

## Generation

Python 3.12 or later is required. Docker Compose is required for execution checks.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
$env:QWEN_BASE_URL = "http://10.10.10.10:4000/v1"
$env:QWEN_API_KEY = Read-Host "Qwen API key"
python main.py index knowledge/sources
python main.py generate examples/parking.md --output runs/parking
```

On the organisers' VM use the same commands with `source .venv/bin/activate` and environment variables exported by the shell. The internal Qwen endpoint is reachable from the VM.

Generation saves structured requirements, a shared API blueprint, source files, documents, requirement links and per-call token usage. Stage results are cached by prompt, schema and model inputs. Repeating the same run reuses completed model calls. Changed business requirements require a new output directory.

Critical ambiguities produce `docs/clarifications.json` and pause generation. Supply a JSON object mapping question IDs to answers through `--answers answers.json` and resume the same output directory. The completed analysis is reused and the answers are retained separately.

## Execution

```powershell
python runs/parking/scripts/configure.py
python main.py verify runs/parking --execute --deploy
```

Generated applications listen on port 8080. The Swagger interface is at `/swagger/index.html`. API contracts are at `/openapi/v1.json`. Administrator and driver access tokens are generated in the application's local `.env` file. They are never embedded in frontend assets.

Checks use fixed Docker commands. The model cannot select host shell commands or modify platform dependencies. Acceptance tests execute in a container with a read-only filesystem, dropped capabilities and no Docker socket. Docker builds remain privileged infrastructure and require a trusted operator.

## Evidence

Each output contains `reports/checks.json`, individual check logs, `reports/security.json`, `reports/traceability.json`, `reports/summary.json` and a readable verification report. A check that was not executed is reported as `not_run`. Generated requirement links describe intended coverage and do not prove that a requirement passed.

The parking case is a preparation fixture. No parking-specific code is built into the generator. A second requirements file uses the same stages and platform templates.

## Development

```powershell
python -m pytest
python -m ruff check .
```

Core modules are under `generator/`. Role instructions are under `generator/prompts/`. Target stack files are under `generator/templates/`. See [implementation status](docs/status.md), [architecture decisions](docs/architecture.md) and [evaluation procedure](docs/evaluation.md).

## Current constraints

Generation and verification are separate. A successful generation is not a successful deployment. The live parking run and its check reports are pending. Demo bearer tokens must be replaced with enterprise identity integration for production. PWA installation and browser geolocation require HTTPS outside localhost.

```bibtex
@software{tle2026rwb,
  author = {TLE},
  title = {RWB App Generator},
  year = {2026},
  url = {https://github.com/pymlex/rwb-app-generator}
}
```

The project is under GPL-3.0 license.
