import json
import sys

import pytest

from generator.models import Analysis, Check, Requirement
from generator.storage import event, write_json
from generator.verification import report, run_check, structural


def test_skipped_execution_is_never_a_pass(tmp_path):
    check = run_check(tmp_path, "unavailable", ["not-a-real-command"], False)
    assert check.status == "not_run"
    assert check.exit_code is None


def test_failed_process_remains_failed(tmp_path):
    check = run_check(tmp_path, "failure", [sys.executable, "-c", "raise SystemExit(7)"], True)
    assert check.status == "failed"
    assert check.exit_code == 7


def test_credentials_are_redacted_from_check_logs(tmp_path, monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "test-sensitive-value")
    check = run_check(
        tmp_path,
        "redaction",
        [sys.executable, "-c", "import os; print(os.environ['QWEN_API_KEY'])"],
        True,
    )
    assert "test-sensitive-value" not in check.log
    assert "[REDACTED]" in check.log


def test_missing_project_is_not_structurally_complete(tmp_path):
    assert structural(tmp_path).status == "failed"


def test_artifacts_and_build_do_not_prove_acceptance(tmp_path):
    analysis = Analysis(
        title="Inventory",
        purpose="Track stock",
        scope="Stock",
        roles=["admin"],
        requirements=[
            Requirement(
                id="FR-001",
                statement="Persist stock",
                source_quote="Persist stock",
                acceptance=["Read back stock"],
                priority="must",
            )
        ],
        nonfunctional=[],
        assumptions=[],
        questions=[],
        entities=["stock"],
        scenarios=[],
        integrations=[],
        risks=[],
    )
    write_json(
        tmp_path / ".pipeline" / "artifact-manifest.json",
        [{"path": "backend/Domain.cs", "requirement_ids": ["FR-001"]}],
    )
    event(
        tmp_path / ".pipeline",
        "model_completed",
        usage={"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50},
    )
    check = Check(
        name="build", command=[], status="passed", exit_code=0, duration_seconds=1, log="compiled"
    )
    result = report(tmp_path, analysis, [check], 2)
    assert result["status"] == "generated_unverified"
    evidence = json.loads((tmp_path / "reports" / "traceability.json").read_text())
    assert evidence[0]["status"] == "unverified"
    assert result["usage"]["total_tokens"] == 50


@pytest.fixture
def modular_project(tmp_path):
    artifacts = {
        "backend/Domain.cs": "public static class Domain {}",
        "backend/DomainModels.cs": "public record Item(string Id);",
        "backend/DomainService.Inventory.cs": "public partial class DomainService {}",
        "backend/migrations/002_domain.sql": "CREATE TABLE items(id text PRIMARY KEY);",
        "frontend/src/app.ts": "export class App {}",
        "frontend/src/app.types.ts": "export interface Item { id: string; }",
        "frontend/src/app.html": "<main>Inventory</main>",
        "frontend/src/app.css": "main { display: grid; }",
        "tests/test_acceptance.py": "import unittest",
        "docs/system-analysis.md": "# Inventory requirements",
        "docker-compose.yml": "services: {}",
    }
    for name, content in artifacts.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


def test_modular_service_parts_are_accepted_without_a_monolithic_service(modular_project):
    assert structural(modular_project).status == "passed"
    (modular_project / "backend/DomainService.Inventory.cs").unlink()
    assert structural(modular_project).status == "failed"


@pytest.mark.parametrize(
    "name",
    [
        "backend/DomainModels.cs",
        "frontend/src/app.types.ts",
        "frontend/src/app.html",
        "frontend/src/app.css",
    ],
)
def test_missing_module_cannot_pass_structure_even_with_a_main_source_file(modular_project, name):
    (modular_project / name).unlink()
    check = structural(modular_project)
    assert check.status == "failed"
    assert name in check.log


def test_unimplemented_service_part_blocks_structure(modular_project):
    (modular_project / "backend/DomainService.Inventory.cs").write_text(
        "public void Save() => throw new NotImplementedException();", encoding="utf-8"
    )
    assert structural(modular_project).status == "failed"


@pytest.fixture
def reviewed_project(tmp_path):
    analysis = Analysis(
        title="Inventory",
        purpose="Track stock",
        scope="Stock persistence",
        roles=["admin"],
        requirements=[
            Requirement(
                id="FR-001",
                statement="Persist stock changes",
                source_quote="Persist stock changes",
                acceptance=["Write stock, restart the service and reread the persisted quantity"],
                priority="must",
            )
        ],
        nonfunctional=[],
        assumptions=[],
        questions=[],
        entities=["stock"],
        scenarios=[],
        integrations=[],
        risks=[],
    )
    write_json(
        tmp_path / ".pipeline" / "artifact-manifest.json",
        [{"path": "backend/DomainService.Inventory.cs", "requirement_ids": ["FR-001"]}],
    )
    event(tmp_path / ".pipeline", "run_started")
    return tmp_path, analysis


def runtime_checks(log, status="passed"):
    return [
        Check(
            name="build",
            command=[],
            status="passed",
            exit_code=0,
            duration_seconds=1,
            log="compiled",
        ),
        Check(
            name="acceptance",
            command=[],
            status=status,
            exit_code=0 if status == "passed" else 1,
            duration_seconds=1,
            log=log,
        ),
    ]


def review_entry(requirement_id="FR-001", status="passed", evidence=None):
    return {
        "requirement_id": requirement_id,
        "status": status,
        "evidence": ["The named test writes stock, restarts the service and rereads it"]
        if evidence is None
        else evidence,
    }


def test_runtime_success_without_independent_requirement_review_is_not_release_ready(
    reviewed_project,
):
    root, analysis = reviewed_project
    result = report(
        root,
        analysis,
        runtime_checks(
            "test_FR_001_persistence (test_acceptance.InventoryTests.test_FR_001_persistence) ... ok\n"
        ),
        3,
    )
    assert result["runtime_verified"] is True
    assert result["release_ready"] is False
    assert result["status"] == "generated_unverified"
    trace = json.loads((root / "reports/traceability.json").read_text())
    assert trace[0]["status"] == "unverified"
    assert trace[0]["checks"] == [
        "test_FR_001_persistence (test_acceptance.InventoryTests.test_FR_001_persistence)"
    ]


def test_review_and_matching_runtime_assertions_provide_requirement_proof(reviewed_project):
    root, analysis = reviewed_project
    write_json(root / "reports/requirement-review.json", [review_entry()])
    result = report(
        root,
        analysis,
        runtime_checks(
            "test_FR_001_persistence (test_acceptance.InventoryTests.test_FR_001_persistence) ... ok\n"
        ),
        3,
    )
    assert result["release_ready"] is True
    assert result["status"] == "verified"
    tests = json.loads((root / "reports/requirement-tests.json").read_text())
    assert tests[0]["requirement_id"] == "FR-001"
    assert tests[0]["status"] == "passed"


@pytest.mark.parametrize("outcome", ["FAIL", "ERROR", "skipped 'dependency unavailable'"])
def test_failure_or_skip_cannot_be_overridden_by_a_positive_review(reviewed_project, outcome):
    root, analysis = reviewed_project
    write_json(root / "reports/requirement-review.json", [review_entry()])
    result = report(
        root,
        analysis,
        runtime_checks(
            "test_FR_001_persistence (test_acceptance.InventoryTests.test_FR_001_persistence) ... "
            + outcome
            + "\n"
        ),
        3,
    )
    assert result["release_ready"] is False
    trace = json.loads((root / "reports/traceability.json").read_text())
    assert trace[0]["status"] == ("unverified" if outcome.startswith("skipped") else "failed")


def test_one_successful_test_does_not_hide_a_failed_test_for_the_same_requirement(reviewed_project):
    root, analysis = reviewed_project
    write_json(root / "reports/requirement-review.json", [review_entry()])
    log = (
        "test_FR_001_write (test_acceptance.InventoryTests.test_FR_001_write) ... ok\n"
        "test_FR_001_restart (test_acceptance.InventoryTests.test_FR_001_restart) ... FAIL\n"
    )
    result = report(root, analysis, runtime_checks(log, "failed"), 3)
    assert result["status"] == "failed"
    assert result["release_ready"] is False
    trace = json.loads((root / "reports/traceability.json").read_text())
    assert trace[0]["status"] == "failed"


@pytest.mark.parametrize(
    "log",
    [
        "Ran 0 tests in 0.000s\n\nOK\n",
        "test_health (test_acceptance.HealthTests.test_health) ... ok\n",
        "test_FR_002_delete (test_acceptance.InventoryTests.test_FR_002_delete) ... ok\n",
    ],
)
def test_old_review_without_current_matching_test_results_cannot_prove_coverage(
    reviewed_project, log
):
    root, analysis = reviewed_project
    write_json(root / "reports/requirement-review.json", [review_entry()])
    result = report(root, analysis, runtime_checks(log), 3)
    assert result["release_ready"] is False
    trace = json.loads((root / "reports/traceability.json").read_text())
    assert trace[0]["status"] == "unverified"


@pytest.mark.parametrize("evidence", [[], ""])
def test_review_verdict_without_evidence_is_not_coverage(reviewed_project, evidence):
    root, analysis = reviewed_project
    write_json(root / "reports/requirement-review.json", [review_entry(evidence=evidence)])
    result = report(
        root,
        analysis,
        runtime_checks(
            "test_FR_001_persistence (test_acceptance.InventoryTests.test_FR_001_persistence) ... ok\n"
        ),
        3,
    )
    assert result["release_ready"] is False


@pytest.mark.parametrize(
    "entries",
    [[review_entry("FR-999")], [review_entry(), review_entry()]],
)
def test_unknown_and_duplicate_review_identifiers_are_rejected(reviewed_project, entries):
    root, analysis = reviewed_project
    write_json(root / "reports/requirement-review.json", entries)
    with pytest.raises(ValueError, match="duplicate or unknown"):
        report(root, analysis, runtime_checks(""), 3)


def test_positive_test_lines_do_not_override_an_unsuccessful_acceptance_process(reviewed_project):
    root, analysis = reviewed_project
    write_json(root / "reports/requirement-review.json", [review_entry()])
    result = report(
        root,
        analysis,
        runtime_checks(
            "test_FR_001_persistence (test_acceptance.InventoryTests.test_FR_001_persistence) ... ok\n",
            "failed",
        ),
        3,
    )
    assert result["release_ready"] is False
    trace = json.loads((root / "reports/traceability.json").read_text())
    assert trace[0]["status"] != "passed"


def test_independent_review_can_reject_inadequate_assertions_even_when_tests_pass(reviewed_project):
    root, analysis = reviewed_project
    write_json(root / "reports/requirement-review.json", [review_entry(status="failed")])
    result = report(
        root,
        analysis,
        runtime_checks(
            "test_FR_001_persistence (test_acceptance.InventoryTests.test_FR_001_persistence) ... ok\n"
        ),
        3,
    )
    assert result["release_ready"] is False
    trace = json.loads((root / "reports/traceability.json").read_text())
    assert trace[0]["status"] == "failed"


def test_requirement_proof_requires_a_trace_to_the_implementation(reviewed_project):
    root, analysis = reviewed_project
    write_json(root / ".pipeline/artifact-manifest.json", [])
    write_json(root / "reports/requirement-review.json", [review_entry()])
    result = report(
        root,
        analysis,
        runtime_checks(
            "test_FR_001_persistence (test_acceptance.InventoryTests.test_FR_001_persistence) ... ok\n"
        ),
        3,
    )
    assert result["release_ready"] is False


def test_sast_fallback_requires_and_records_a_reason(tmp_path, monkeypatch):
    from generator.verification import sast

    monkeypatch.setenv('SAST_ENGINE', 'dotnet')
    monkeypatch.delenv('SAST_FALLBACK_REASON', raising=False)
    with pytest.raises(ValueError, match='SAST_FALLBACK_REASON'):
        sast(tmp_path, False)
    monkeypatch.setenv('SAST_FALLBACK_REASON', 'VM cannot reach semgrep.dev')
    check = sast(tmp_path, False)
    assert check.status == 'not_run'
    assert check.command[-1] == 'sast-dotnet'
    context = json.loads((tmp_path / 'reports/sast-context.json').read_text())
    assert context == {'engine': 'dotnet', 'reason': 'VM cannot reach semgrep.dev'}


def test_sast_is_added_without_reordering_existing_checks(modular_project, monkeypatch):
    from generator.verification import verify

    monkeypatch.delenv('SAST_ENGINE', raising=False)
    checks = verify(modular_project, deploy=True)
    assert [check.name for check in checks] == [
        'structure', 'compose-config', 'dependency-lock', 'backend-dependency-lock',
        'build', 'unit', 'audit-source-build', 'dependency-audit', 'static-analysis', 'deployment', 'acceptance', 'openapi-lint', 'api-contract', 'ui-smoke',
    ]
    assert next(check for check in checks if check.name == 'static-analysis').status == 'not_run'


@pytest.mark.parametrize('deployed', [True, False])
def test_runtime_contract_checks_depend_on_deployment(modular_project, monkeypatch, deployed):
    import generator.verification as verification

    invocations = []

    def fake_run(root, name, command, execute, sudo_password=None):
        invocations.append((name, execute))
        status = 'passed' if execute else 'not_run'
        if name == 'deployment' and not deployed:
            status = 'failed'
        return Check(name=name, command=command, status=status,
                     exit_code=0 if status == 'passed' else None, duration_seconds=0, log='')

    monkeypatch.setattr(verification, 'run_check', fake_run)
    verification.verify(modular_project, execute=True, deploy=True)
    assert dict(invocations)['openapi-lint'] is deployed
    assert dict(invocations)['api-contract'] is deployed
    assert dict(invocations)['ui-smoke'] is deployed
