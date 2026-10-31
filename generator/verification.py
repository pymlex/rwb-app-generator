import json
import os
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from generator.models import Analysis, Check, Evidence
from generator.reports import write_reports
from generator.storage import write_json


def run_check(
    root: Path, name: str, command: list[str], execute: bool, sudo_password: str | None = None
) -> Check:
    if not execute:
        return Check(
            name=name,
            command=command,
            status="not_run",
            exit_code=None,
            duration_seconds=0,
            log="Execution not requested",
        )
    started = time.monotonic()
    executable = ["sudo", "-S", "-p", "", *command] if sudo_password else command
    result = subprocess.run(
        executable,
        cwd=root,
        input=sudo_password + "\n" if sudo_password else None,
        capture_output=True,
        text=True,
        timeout=1800,
        check=False,
    )
    log = result.stdout + result.stderr
    secrets = [
        value
        for key, value in os.environ.items()
        if any(term in key for term in ["TOKEN", "PASSWORD", "API_KEY"]) and len(value) > 6
    ]
    if sudo_password:
        secrets.append(sudo_password)
    for value in secrets:
        log = log.replace(value, "[REDACTED]")
    check = Check(
        name=name,
        command=command,
        status="passed" if result.returncode == 0 else "failed",
        exit_code=result.returncode,
        duration_seconds=round(time.monotonic() - started, 3),
        log=log[-24000:],
    )
    write_json(root / "reports" / f"{name}.json", check.model_dump())
    return check


def structural(root: Path) -> Check:
    required = [
        "backend/Domain.cs",
        "backend/DomainModels.cs",
        "backend/migrations/002_domain.sql",
        "frontend/src/app.ts",
        "frontend/src/app.types.ts",
        "frontend/src/app.html",
        "frontend/src/app.css",
        "docs/system-analysis.md",
        "docker-compose.yml",
    ]
    missing = [name for name in required if not (root / name).is_file()]
    defects = [f"Missing: {name}" for name in missing]
    if not list((root / "tests").glob("test_acceptance*.py")):
        defects.append("Missing: tests/test_acceptance*.py")
    services = sorted((root / "backend").glob("DomainService*.cs"))
    if not services:
        defects.append("Missing: backend/DomainService*.cs")
    sources = required[:2] + required[3:7] + [str(path.relative_to(root)) for path in services]
    for name in sources:
        if (root / name).is_file():
            content = (root / name).read_text(encoding="utf-8")
            if re.search(r"\bTODO\b|NotImplementedException|YOUR_API_KEY", content):
                defects.append(f"Unimplemented content: {name}")
    return Check(
        name="structure",
        command=[],
        status="failed" if defects else "passed",
        exit_code=int(bool(defects)),
        duration_seconds=0,
        log="\n".join(defects) or "Required artifacts present",
    )


def backend_build(root: Path, execute: bool, sudo_password: str | None = None) -> Check:
    locked = run_check(
        root,
        "backend-dependency-lock",
        ["docker", "compose", "--profile", "checks", "run", "--rm", "backend-lock"],
        execute,
        sudo_password,
    )
    if locked.status == "failed":
        return locked
    return run_check(
        root,
        "backend-build",
        ["docker", "compose", "build", "backend"],
        execute,
        sudo_password,
    )


def verify(
    root: Path, execute: bool = False, deploy: bool = False, sudo_password: str | None = None
) -> list[Check]:
    checks = [structural(root)]
    checks.append(
        run_check(
            root,
            "compose-config",
            ["docker", "compose", "config", "--quiet"],
            execute,
            sudo_password,
        )
    )
    checks.append(
        run_check(
            root,
            "dependency-lock",
            ["docker", "compose", "--profile", "checks", "run", "--rm", "lock"],
            execute,
            sudo_password,
        )
    )
    checks.append(
        run_check(
            root,
            "backend-dependency-lock",
            ["docker", "compose", "--profile", "checks", "run", "--rm", "backend-lock"],
            execute,
            sudo_password,
        )
    )
    checks.append(
        run_check(
            root, "build", ["docker", "compose", "--parallel", "1", "build"], execute, sudo_password
        )
    )
    build_passed = checks[-1].status == "passed"
    checks.append(
        run_check(
            root,
            "unit",
            ["docker", "compose", "--profile", "checks", "run", "--rm", "--build", "unit"],
            execute and build_passed,
            sudo_password,
        )
    )
    checks.append(
        run_check(
            root,
            "dependency-audit",
            ["docker", "compose", "--profile", "checks", "run", "--rm", "audit"],
            execute and build_passed,
            sudo_password,
        )
    )
    if deploy:
        checks.append(
            run_check(
                root,
                "deployment",
                ["docker", "compose", "up", "-d", "--wait", "--wait-timeout", "180", "frontend"],
                execute and build_passed,
                sudo_password,
            )
        )
        deployed = checks[-1].status == "passed"
        checks.append(
            run_check(
                root,
                "acceptance",
                ["docker", "compose", "--profile", "checks", "run", "--rm", "acceptance"],
                execute and deployed,
                sudo_password,
            )
        )
    write_json(root / "reports" / "checks.json", [check.model_dump() for check in checks])
    write_reports(root, checks)
    return checks


def report(root: Path, analysis: Analysis, checks: list[Check], elapsed: float) -> dict:
    passed = [check.name for check in checks if check.status == "passed"]
    manifest = json.loads(
        (root / ".pipeline" / "artifact-manifest.json").read_text(encoding="utf-8")
    )
    acceptance = next((check for check in checks if check.name == "acceptance"), None)
    named_tests = []
    if acceptance:
        named_tests = [
            {
                "name": match[1] + " (" + match[3] + ")",
                "requirement_id": "FR-" + match[2],
                "status": "passed"
                if match[4] == "ok"
                else "failed"
                if match[4] in {"FAIL", "ERROR"}
                else "not_run",
            }
            for match in re.finditer(
                r"\b(test_FR_(\d{3})\w*)\s+\(([^)\n]+)\)\s+\.\.\.\s+(ok|FAIL|ERROR|skipped[^\n]*)",
                acceptance.log,
            )
        ]
    write_json(root / "reports" / "requirement-tests.json", named_tests)
    review_path = root / "reports" / "requirement-review.json"
    review_entries = (
        json.loads(review_path.read_text(encoding="utf-8")) if review_path.is_file() else []
    )
    reviewed = {entry["requirement_id"]: entry for entry in review_entries}
    known_ids = {requirement.id for requirement in analysis.requirements}
    if len(reviewed) != len(review_entries) or set(reviewed) - known_ids:
        raise ValueError("Requirement review contains duplicate or unknown requirement identifiers")
    evidence = []
    for requirement in analysis.requirements:
        files = [entry["path"] for entry in manifest if requirement.id in entry["requirement_ids"]]
        tests = [test for test in named_tests if test["requirement_id"] == requirement.id]
        review = reviewed.get(requirement.id, {})
        status = "unverified"
        if any(test["status"] == "failed" for test in tests) or review.get("status") == "failed":
            status = "failed"
        elif (
            acceptance
            and acceptance.status == "passed"
            and tests
            and all(test["status"] == "passed" for test in tests)
            and review.get("status") == "passed"
            and review.get("evidence")
            and files
        ):
            status = "passed"
        evidence.append(
            Evidence(
                requirement_id=requirement.id,
                files=files,
                checks=[test["name"] for test in tests],
                status=status,
            )
        )
    write_json(root / "reports" / "traceability.json", [entry.model_dump() for entry in evidence])
    events = [
        json.loads(line)
        for line in (root / ".pipeline" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    calls = [entry for entry in events if entry["kind"] == "model_completed"]
    usage = {
        key: sum(entry.get("usage", {}).get(key, 0) or 0 for entry in calls)
        for key in ["prompt_tokens", "completion_tokens", "total_tokens"]
    }
    usage["reasoning_tokens"] = sum(
        (entry.get("usage", {}).get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
        or 0
        for entry in calls
    )
    failed = any(check.status == "failed" for check in checks)
    complete = all(check.status == "passed" for check in checks) and "acceptance" in passed
    must_ids = {
        requirement.id for requirement in analysis.requirements if requirement.priority == "must"
    }
    covered = {entry.requirement_id for entry in evidence if entry.status == "passed"}
    release_ready = complete and must_ids <= covered
    result = {
        "status": "failed" if failed else "verified" if release_ready else "generated_unverified",
        "runtime_verified": complete,
        "release_ready": release_ready,
        "coverage_status": "passed" if must_ids <= covered else "unverified",
        "duration_seconds": round(elapsed, 2),
        "model_calls": len(calls),
        "repairs": sum(entry["kind"] == "repair_started" for entry in events),
        "usage": usage,
        "checks": {check.name: check.status for check in checks},
    }
    starts = [entry for entry in events if entry["kind"] == "run_started"]
    result["invocations"] = len(starts)
    result["api_attempts"] = sum(
        entry["kind"] == "model_http_attempt"
        or entry["kind"] == "model_started"
        and not entry.get("http_tracking")
        for entry in events
    )
    result["model_seconds"] = round(sum(entry.get("duration_seconds", 0) for entry in calls), 2)
    if starts:
        result["wall_seconds_since_first_start"] = round(
            (datetime.now(UTC) - datetime.fromisoformat(starts[0]["time"])).total_seconds(), 2
        )
    write_json(root / "reports" / "summary.json", result)
    lines = [
        "# Verification report",
        "",
        f"Overall status: {result['status']}",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {check.name}: {check.status}. Evidence: {check.name}.json" for check in checks)
    lines.extend(
        [
            "",
            "## Requirement evidence",
            "",
            "Artifact links identify intended coverage. A requirement passes only with named successful runtime tests and independent assertion review in requirement-review.json. Missing evidence remains unverified.",
            "",
            "## Resource usage",
            "",
            json.dumps(usage),
            "",
            f"Model calls: {len(calls)}. Repairs: {result['repairs']}. Elapsed seconds: {elapsed:.2f}.",
        ]
    )
    (root / "reports" / "verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_reports(root, checks)
    return result
