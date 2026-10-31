import json
import shutil
from pathlib import Path

import pytest

from generator.models import Check
from generator.reports import write_reports
from generator.verification import verify


@pytest.fixture
def report_run(tmp_path):
    shutil.copytree(Path(__file__).parent / "fixtures/report-run", tmp_path, dirs_exist_ok=True)
    return tmp_path


def test_reports_match_json_and_are_deterministic(report_run):
    write_reports(report_run)
    docs = report_run / "docs"
    first = {path.name: path.read_bytes() for path in docs.glob("*-report.md")}
    tests = first["test-report.md"].decode()
    security = first["security-report.md"].decode()
    for check in json.loads((report_run / "reports/checks.json").read_text()):
        assert check["name"] in tests
        assert check["status"] in tests
    assert "Check status: failed" in tests
    assert "test_FR_001_save: failed" in tests
    for finding in ["CVE-FIXTURE", "fixture-rule", "fixture.injection"]:
        assert finding in security
    for severity in ["CRITICAL", "HIGH", "ERROR"]:
        assert f"- {severity}: 1" in security
    assert "Overall status: failed" in security
    assert "DO-NOT-COPY" not in security
    write_reports(report_run)
    assert first == {path.name: path.read_bytes() for path in docs.glob("*-report.md")}


def test_missing_evidence_does_not_pass(tmp_path):
    write_reports(tmp_path)
    assert "Check status: not_run" in (tmp_path / "docs/test-report.md").read_text()
    assert "Overall status: not_run" in (tmp_path / "docs/security-report.md").read_text()


def test_empty_completed_scan_passes_but_failed_scanner_does_not(report_run):
    (report_run / "reports/security.json").write_text('{"Results": []}')
    (report_run / "reports/sast.json").unlink()
    check = Check(
        name="dependency-audit",
        status="passed",
        command=[],
        exit_code=0,
        duration_seconds=1,
        log="",
    )
    write_reports(report_run, [check])
    assert "Overall status: passed" in (report_run / "docs/security-report.md").read_text()
    write_reports(report_run, [check.model_copy(update={"status": "failed"})])
    assert "Overall status: failed" in (report_run / "docs/security-report.md").read_text()


def test_verify_writes_reports_without_execution(tmp_path):
    verify(tmp_path)
    text = (tmp_path / "docs/test-report.md").read_text()
    assert "compose-config" in text
    assert "not_run" in text
    assert (tmp_path / "docs/security-report.md").is_file()
