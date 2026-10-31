Run from the generator checkout on the organiser VM, with Qwen configured per README.
Record `git rev-parse HEAD`. Generation must copy the current platform templates;
old output trees alone do not prove these changes work.

```bash
.venv/bin/python -m ruff check generator tests main.py
.venv/bin/python -m pytest -q
.venv/bin/python -m pip_audit
.venv/bin/python main.py generate examples/parking.md --answers examples/parking-answers.json --output runs/parking
test -f runs/parking/.env || .venv/bin/python runs/parking/scripts/configure.py
.venv/bin/python main.py verify runs/parking --execute --deploy
.venv/bin/python main.py generate examples/inventory.md --output runs/inventory
test -f runs/inventory/.env || .venv/bin/python runs/inventory/scripts/configure.py
APP_PORT=8082 .venv/bin/python main.py verify runs/inventory --execute --deploy
```

Keep organiser reference JSON in `runs/parking/backend/data` before generation.
Use distinct Compose project names if the output directories share a basename.
Do not print `.env`, tokens or secret-bearing reports. If Docker requires sudo,
append `--sudo` to `main.py verify`; prefer the organiser's Docker group setup.

For individual platform gates, from the generated application directory:

```bash
mkdir -p reports
docker compose config --quiet
docker compose --profile checks run --rm lock
docker compose --profile checks run --rm backend-lock
docker compose --parallel 1 build
docker compose --profile checks run --rm --build unit
docker compose --profile checks build audit
docker compose --profile checks run --rm audit
docker compose --profile checks run --rm sast
docker compose up -d --wait --wait-timeout 180 frontend
docker compose --profile checks run --rm acceptance
docker compose --profile checks run --rm --build spectral
docker compose --profile checks run --rm --build schemathesis
docker compose --profile checks run --rm --build e2e
curl --silent --show-error --head http://localhost:8080/
curl --silent --show-error --head http://localhost:8080/api/v1/me
```

Expected evidence: `reports/security.json`, `sast.json`, `sast-context.json`,
`openapi.json`, `spectral.json`, `schemathesis.xml`, `schemathesis.log`, `e2e.json`,
and the individual verification check JSON files. A failed scanner/tool remains a
failure. Runtime contract and browser checks require successful deployment.
Check OSM tiles (if used), the SVG map, Swagger, browser geolocation, service worker
registration, offline shell and PWA installation in a browser; use HTTPS outside
localhost. CSP/Permissions-Policy must also be present on the 401 response.
Configure E2E_SCENARIO for actual domain forms as described in `checks/e2e/README.md`.

Only if semgrep.dev is inaccessible from the VM:

```bash
SAST_ENGINE=dotnet SAST_FALLBACK_REASON='semgrep.dev unreachable from organiser VM' \
  python3 scripts/sast-service.py
# The selector above writes the reason; execute the explicitly selected fallback:
docker compose --profile checks run --rm sast-dotnet
```

To select the same fallback through generator verification, from its checkout:

```bash
SAST_ENGINE=dotnet SAST_FALLBACK_REASON='semgrep.dev unreachable from organiser VM' \
  .venv/bin/python main.py verify runs/parking --execute --deploy
```

Validate GitLab CI both as an MR (build/test/security/report, no deploy) and on the
default branch (all five stages). Ensure the runner has tag `organiser-vm`, Docker
access and protected `APP_ENV_FILE` for stable application credentials. Confirm
that simultaneous pipelines use their own image tags and acceptance runs against
the image built by that pipeline. Retain stage artifacts and `ci-stages.json`.

For named-driver/domain isolation, follow `checks/IDENTITIES.md`: add two named
tokens to the protected application configuration, set a real OWNERSHIP_SCENARIO,
recreate backend, and run `ownership-acceptance`. `reports/ownership.json` must
prove foreign read/write 404, unchanged state, and a successful owner mutation.
Until then, actual generated-domain isolation remains an explicit limitation.
For A-05 run the commands in `checks/IMAGE-DIGESTS.md` and return manifest digests.
