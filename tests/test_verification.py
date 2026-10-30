import json
import sys

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
    check = run_check(tmp_path, "redaction", [sys.executable, "-c", "import os; print(os.environ['QWEN_API_KEY'])"], True)
    assert "test-sensitive-value" not in check.log
    assert "[REDACTED]" in check.log


def test_missing_project_is_not_structurally_complete(tmp_path):
    assert structural(tmp_path).status == "failed"


def test_artifacts_and_build_do_not_prove_acceptance(tmp_path):
    analysis = Analysis(title="Inventory", purpose="Track stock", scope="Stock", roles=["admin"], requirements=[Requirement(id="FR-001", statement="Persist stock", source_quote="Persist stock", acceptance=["Read back stock"], priority="must")], nonfunctional=[], assumptions=[], questions=[], entities=["stock"], scenarios=[], integrations=[], risks=[])
    write_json(tmp_path / ".pipeline" / "artifact-manifest.json", [{"path": "backend/Domain.cs", "requirement_ids": ["FR-001"]}])
    event(tmp_path / ".pipeline", "model_completed", usage={"prompt_tokens": 20, "completion_tokens": 30, "total_tokens": 50})
    check = Check(name="build", command=[], status="passed", exit_code=0, duration_seconds=1, log="compiled")
    result = report(tmp_path, analysis, [check], 2)
    assert result["status"] == "generated_unverified"
    evidence = json.loads((tmp_path / "reports" / "traceability.json").read_text())
    assert evidence[0]["status"] == "unverified"
    assert result["usage"]["total_tokens"] == 50
