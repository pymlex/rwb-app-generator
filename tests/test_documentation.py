import json
from types import SimpleNamespace

from generator.agents import AgentState
from generator.config import Settings
from generator.pipeline import Pipeline


def test_documenter_context_keeps_contracts_and_requirements_without_large_implementation(tmp_path):
    backend = tmp_path / "backend"
    frontend = tmp_path / "frontend" / "src"
    backend.mkdir()
    frontend.mkdir(parents=True)
    (backend / "DomainModels.cs").write_text("ACTUAL_TYPED_CONTRACT", encoding="utf-8")
    (backend / "Domain.cs").write_text("ROUTE_IMPLEMENTATION" * 20000, encoding="utf-8")
    (frontend / "app.ts").write_text("UI_IMPLEMENTATION" * 20000, encoding="utf-8")
    pipeline = Pipeline(
        Settings("http://model/v1", "test-key"), tmp_path, tmp_path / "absent.sqlite"
    )
    requirement = SimpleNamespace(
        model_dump=lambda **kwargs: {
            "id": "FR-099",
            "statement": "COMPLETE_REQUIREMENT",
            "acceptance": ["REQUIRED_CRITERION"],
        }
    )
    pipeline.analysis = SimpleNamespace(
        model_dump=lambda **kwargs: {"requirements": []},
        requirements=[requirement],
    )
    pipeline.blueprint = SimpleNamespace(
        model_dump=lambda: {"endpoints": [{"path": "/api/v1/items"}]}
    )
    pipeline.reference_data = {}
    generated = []
    pipeline.generate_files = lambda stage, prompt, context, paths: generated.append(context)
    pipeline.documenter(AgentState())
    assert len(generated) == 7
    for context in generated:
        assert len(context) < 65000
        assert "COMPLETE_REQUIREMENT" in context
        assert "REQUIRED_CRITERION" in context
        assert "ACTUAL_TYPED_CONTRACT" in context
        assert "ROUTE_IMPLEMENTATION" not in context
        assert "UI_IMPLEMENTATION" not in context
        task = json.loads(context.split("\n", 1)[1])["task"]
        references = {item["path"] for item in json.loads(task)["implementation_evidence"]}
        assert {"backend/Domain.cs", "frontend/src/app.ts"} <= references
