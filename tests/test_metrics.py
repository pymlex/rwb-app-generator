import json
import shutil
from pathlib import Path

from generator.metrics import stage_metrics, write_metrics
from generator.models import Check
from generator.storage import event


FIXTURE = Path(__file__).parent / "fixtures/report-run"


def test_metrics_agree_with_recorded_events_and_checks(tmp_path):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    result = write_metrics(tmp_path)
    assert result["run_id"]
    assert result["invocations"] == 2
    totals = result["totals"]
    assert totals["model_calls"] == 2
    assert totals["model_calls_started"] == 2
    assert totals["http_attempts"] == 3
    assert totals["http_retries"] == 1
    assert totals["http_failures"] == 1
    assert totals["repairs"] == 1
    assert totals["cache_hits"] == 1
    assert totals["artifact_reuses"] == 2
    assert totals["input_tokens"] == 40
    assert totals["output_tokens"] == 60
    assert totals["total_tokens"] == 100
    assert totals["reasoning_tokens"] == 5
    assert totals["reasoning_calls_reported"] == 1
    assert totals["model_seconds"] == 8
    assert totals["wait_seconds"] == 2
    assert result["stages"]["analysis"]["http_retries"] == 1
    assert result["stages"]["backend"]["reasoning_tokens"] is None
    assert result["durations"]["observed_event_span_seconds"] == 62
    assert result["outcomes"] == {"build": "passed", "test": "failed", "deploy": "not_run"}
    files = list((tmp_path / "pipeline-metrics").glob("summary.*"))
    before = [path.read_bytes() for path in files]
    assert "DO-NOT-COPY" not in "".join(path.read_text() for path in files)
    assert json.loads((tmp_path / "pipeline-metrics/summary.json").read_text()) == result
    write_metrics(tmp_path)
    assert before == [path.read_bytes() for path in files]
    event(tmp_path / ".pipeline", "cache_hit", stage="analysis")
    assert write_metrics(tmp_path)["run_id"] == result["run_id"]


def test_missing_usage_and_legacy_attempt_tracking():
    result = stage_metrics(
        [
            {"kind": "model_started"},
            {"kind": "model_completed", "usage": None},
            {
                "kind": "model_completed",
                "usage": {"completion_tokens_details": {"reasoning_tokens": 0}},
            },
        ]
    )
    assert result["http_attempts"] == 1
    assert result["input_tokens"] == 0
    assert result["reasoning_tokens"] == 0
    assert result["reasoning_calls_reported"] == 1


def test_empty_metrics_never_claim_execution(tmp_path):
    result = write_metrics(tmp_path)
    assert result["status"] == "not_run"
    assert result["run_id"] is None
    assert set(result["outcomes"].values()) == {"not_run"}
    assert result["totals"]["reasoning_tokens"] is None


def test_current_checks_override_old_reports_on_resumed_runs(tmp_path):
    shutil.copytree(FIXTURE, tmp_path, dirs_exist_ok=True)
    result = write_metrics(tmp_path, [], "needs_clarification", 2)
    assert result["status"] == "needs_clarification"
    assert result["durations"]["reported_seconds"] == 2
    assert set(result["outcomes"].values()) == {"not_run"}
    checks = [
        Check(name=name, status="passed", command=[], exit_code=0, duration_seconds=1, log="")
        for name in ["build", "unit", "acceptance", "deployment"]
    ]
    result = write_metrics(tmp_path, checks, "verified", 4)
    assert set(result["outcomes"].values()) == {"passed"}
