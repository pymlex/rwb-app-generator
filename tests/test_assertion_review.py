import json
from types import SimpleNamespace

from generator.models import RequirementReviews
from generator.pipeline import Pipeline


def test_assertion_review_records_grounded_test_evidence(tmp_path):
    pipeline = object.__new__(Pipeline)
    pipeline.output = tmp_path
    path = "tests/test_acceptance_00.py"
    pipeline.test_paths = [path]
    pipeline.analysis = SimpleNamespace(requirements=[SimpleNamespace(id="FR-001")])
    source = "def test_FR_001_create():\n    assert response.status == 201\n"
    (tmp_path / "tests").mkdir()
    (tmp_path / path).write_text(source)
    pipeline.context = lambda *args: "Assigned requirement and actual test source"
    pipeline.prompt = lambda name: "Review assertions"

    def ask(stage, instruction, context, schema):
        assert schema is RequirementReviews
        return schema.model_validate(
            {
                "requirements": [
                    {
                        "requirement_id": "FR-001",
                        "status": "passed",
                        "evidence": [
                            {
                                "path": path,
                                "test_name": "test_FR_001_create",
                                "source_quote": "assert response.status == 201",
                                "criterion": "Creation returns HTTP 201",
                            }
                        ],
                        "missing_criteria": [],
                    }
                ]
            }
        )

    pipeline.ask = ask
    pipeline.review_assertions()
    report = json.loads((tmp_path / "reports/requirement-review.json").read_text())
    assert report[0]["evidence"][0]["test_name"] == "test_FR_001_create"


def test_outside_assertion_evidence_retries_then_fails_coverage_without_crashing(tmp_path):
    pipeline = object.__new__(Pipeline)
    pipeline.output = tmp_path
    pipeline.run_dir = tmp_path / ".pipeline"
    path = "tests/test_acceptance_00.py"
    pipeline.test_paths = [path]
    pipeline.analysis = SimpleNamespace(requirements=[SimpleNamespace(id="FR-001")])
    (tmp_path / "tests").mkdir()
    (tmp_path / path).write_text("def test_FR_001_create():\n    assert response.status == 201\n")
    pipeline.context = lambda *args: "Actual test context"
    pipeline.prompt = lambda name: "Review assertions"
    calls = []

    def ask(stage, prompt, context, schema):
        calls.append((stage, prompt))
        return schema.model_validate({"requirements": [{
            "requirement_id": "FR-001", "status": "passed", "missing_criteria": [],
            "evidence": [{
                "path": evidence_path, "test_name": "test_FR_001_create",
                "source_quote": "assert response.status == 201", "criterion": "Creation status",
            } for evidence_path in (path, "outside.py")],
        }]})

    pipeline.ask = ask
    pipeline.review_assertions()
    assert len(calls) == 2
    assert path in calls[1][1]
    saved = json.loads((tmp_path / "reports/requirement-review.json").read_text())
    assert saved[0]["status"] == "failed"
    assert saved[0]["missing_criteria"]
    assert [proof["path"] for proof in saved[0]["evidence"]] == [path]
    events = [json.loads(row) for row in (pipeline.run_dir / "events.jsonl").read_text().splitlines()]
    assert events[-1]["kind"] == "review_out_of_context_ignored"
