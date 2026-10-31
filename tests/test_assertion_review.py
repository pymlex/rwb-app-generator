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
