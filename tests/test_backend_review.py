import json
from types import SimpleNamespace

import pytest

from generator.agents import AgentState
from generator.pipeline import BACKEND_CONTRACT, Pipeline


def review(issues):
    return {
        "passes_static_review": not any(item["severity"] in {"high", "critical"} for item in issues),
        "issues": issues,
    }


def issue(path="backend/Domain.cs", severity="high", **changes):
    return {
        "path": path, "severity": severity, "source_quote": "return wrong;",
        "requirement_ids": ["FR-001"], "defect": "Wrong result", "correction": "Fix result",
        **changes,
    }


def pipeline_fixture(tmp_path, responses):
    pipeline = object.__new__(Pipeline)
    pipeline.output = tmp_path
    pipeline.run_dir = tmp_path / ".pipeline"
    pipeline.analysis = SimpleNamespace(requirements=[SimpleNamespace(id="FR-001")])
    pipeline.blueprint = SimpleNamespace(model_dump=lambda: {"endpoints": []})
    pipeline.service_paths = []
    pipeline.work_packages = {}
    pipeline.context = lambda *args: "Actual context"
    pipeline.prompt = lambda name: "Review actual code"
    for path in [*BACKEND_CONTRACT, "backend/Domain.cs"]:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("return wrong;\n")
    calls = []
    responses = iter(responses)

    def ask(stage, prompt, context, schema):
        calls.append((stage, prompt))
        return schema.model_validate(next(responses))

    pipeline.ask = ask
    return pipeline, calls


def test_scope_retry_discards_only_outside_findings_and_keeps_first_valid_defect(tmp_path):
    outside = issue("../outside.cs", requirement_ids=["UNKNOWN"])
    pipeline, calls = pipeline_fixture(
        tmp_path,
        [review([outside, issue()]), review([outside, issue(severity="medium")])],
    )
    state = pipeline.backend_review(AgentState())
    assert len(calls) == 2
    assert calls[1][0] == "backend-review-00-scope-retry"
    assert "ALLOWED REVIEW FILES" in calls[1][1]
    assert all(path in calls[1][1] for path in [*BACKEND_CONTRACT, "backend/Domain.cs"])
    assert state["review_passed"] is False
    assert [item["severity"] for item in state["feedback"]] == ["high"]
    saved = json.loads((tmp_path / "reports/backend-review.json").read_text())
    assert [item["severity"] for item in saved] == ["high", "medium"]
    assert all(item["path"] == "backend/Domain.cs" for item in saved)
    events = [json.loads(row) for row in (pipeline.run_dir / "events.jsonl").read_text().splitlines()]
    assert [row["kind"] for row in events] == ["review_scope_retry", "review_out_of_context_ignored"]


def test_scope_retry_can_return_a_clean_review(tmp_path):
    pipeline, calls = pipeline_fixture(tmp_path, [review([issue("missing.cs")]), review([])])
    assert pipeline.backend_review(AgentState())["review_passed"] is True
    assert len(calls) == 2


@pytest.mark.parametrize(
    "finding,error",
    [
        (issue(requirement_ids=["FR-999"]), "unknown requirement"),
        (issue(source_quote="not in source"), "Source quotation"),
    ],
)
def test_in_scope_findings_still_require_valid_requirements_and_quotes(tmp_path, finding, error):
    pipeline, calls = pipeline_fixture(tmp_path, [review([finding])])
    with pytest.raises(ValueError, match=error):
        pipeline.backend_review(AgentState())
    assert len(calls) == 1
