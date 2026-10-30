import json

import pytest

from generator.agents import AgentState, RoleGraph, SkillLoader
from generator.knowledge import build_index


def callbacks(calls, replacements=None):
    nodes = {}
    replacements = replacements or {}
    for stage in RoleGraph.stages:

        def run(state, name=stage):
            calls.append(name)
            if name in replacements:
                return replacements[name](state)
            gates = {
                "backend_build": "build_passed",
                "backend_review": "review_passed",
                "verification": "verification_passed",
            }
            if name in gates:
                return {gates[name]: True}
            return {"artifacts": {name: f"{name}.json"}}

        nodes[stage] = run
    return nodes


def test_build_failure_repairs_before_review_and_preserves_feedback():
    calls = []
    received = []

    def build(state):
        return {
            "build_passed": state.get("backend_repairs", 0) > 0,
            "feedback": [{"defect": "CS8852"}],
        }

    def repair(state):
        received.extend(state["feedback"])
        return {}

    graph = RoleGraph(callbacks(calls, {"backend_build": build, "backend_repair": repair}))
    result = graph.invoke(AgentState())
    first = calls.index("backend_build")
    assert calls[first : first + 4] == [
        "backend_build",
        "backend_repair",
        "backend_build",
        "backend_review",
    ]
    assert received == [{"defect": "CS8852"}]
    assert result["backend_repairs"] == 1
    assert result["status"] == "completed"
    assert "analyst" in result["artifacts"]
    assert result["messages"][first + 1]["sender"] == "backend_build"


def test_review_failure_has_bounded_repairs_and_never_starts_frontend():
    calls = []
    nodes = callbacks(calls, {"backend_review": lambda state: {"review_passed": False}})
    result = RoleGraph(nodes, max_repairs=2).invoke(AgentState())
    assert result["status"] == "failed"
    assert result["backend_repairs"] == 2
    assert calls.count("backend_review") == 3
    assert "frontend_logic" not in calls


def test_infrastructure_failure_does_not_trigger_code_repair():
    calls = []
    nodes = callbacks(
        calls,
        {"backend_build": lambda state: {"build_passed": False, "repairable": False}},
    )
    result = RoleGraph(nodes).invoke(AgentState())
    assert result["status"] == "failed"
    assert "backend_repair" not in calls


def test_clarification_stops_before_architecture():
    calls = []
    nodes = callbacks(calls, {"analyst": lambda state: {"status": "needs_clarification"}})
    result = RoleGraph(nodes).invoke(AgentState())
    assert result["status"] == "needs_clarification"
    assert calls == ["analyst"]


def test_application_gate_has_independent_repair_budget():
    calls = []
    nodes = callbacks(
        calls,
        {
            "verification": lambda state: {
                "verification_passed": state.get("application_repairs", 0) == 1
            }
        },
    )
    result = RoleGraph(nodes, max_repairs=1).invoke(AgentState())
    assert result["status"] == "completed"
    assert result["application_repairs"] == 1
    assert result["backend_repairs"] == 0
    assert calls[-3:] == ["verification", "application_repair", "verification"]


def test_gate_cannot_reuse_stale_success():
    nodes = callbacks([], {"backend_build": lambda state: {}})
    with pytest.raises(ValueError, match="explicitly report build_passed"):
        RoleGraph(nodes).invoke(AgentState(build_passed=True))


def test_skill_loads_only_requested_files_and_records_provenance(tmp_path):
    sources = tmp_path / "knowledge"
    sources.mkdir()
    (sources / "api.txt").write_text("API контракт HTTP ошибки авторизация", encoding="utf-8")
    database = tmp_path / "index.sqlite"
    build_index(sources, database)
    output = tmp_path / "app"
    output.mkdir()
    (output / "contract.json").write_text('{"method":"POST"}', encoding="utf-8")
    (output / "unrelated.txt").write_text("not in context", encoding="utf-8")
    loader = SkillLoader(
        output, database, output / ".pipeline", {"backend_routes": {"contract.json"}}
    )
    result = loader.load("backend_routes", "HTTP API", ["contract.json"])
    payload = json.loads(result.text)
    assert [item["path"] for item in payload["files"]] == ["contract.json"]
    assert "not in context" not in result.text
    assert result.audit["sources"][0]["source"] == "api.txt"
    assert len(result.audit["files"][0]["sha256"]) == 64
    logged = json.loads((output / ".pipeline" / "events.jsonl").read_text())
    assert logged["kind"] == "skill_loaded"
    assert "text" not in logged


def test_skill_does_not_silently_truncate_artifact_or_task(tmp_path):
    (tmp_path / "contract.json").write_text("x" * 500, encoding="utf-8")
    loader = SkillLoader(
        tmp_path,
        tmp_path / "missing.sqlite",
        tmp_path / ".pipeline",
        {"backend_routes": {"contract.json"}},
        max_context_chars=200,
    )
    with pytest.raises(ValueError, match="split the task"):
        loader.load("backend_routes", "HTTP", ["contract.json"])
    with pytest.raises(ValueError, match="allowlist"):
        loader.load("backend_routes", "HTTP", ["unrelated.txt"])
    with pytest.raises(ValueError, match="Unknown role"):
        loader.load("unknown", "HTTP")


def test_skill_rejects_allowlisted_traversal(tmp_path):
    loader = SkillLoader(
        tmp_path,
        tmp_path / "missing.sqlite",
        tmp_path / ".pipeline",
        {"backend_routes": {"../secret.txt"}},
    )
    with pytest.raises(ValueError, match="Unsafe artifact"):
        loader.load("backend_routes", "HTTP", ["../secret.txt"])
