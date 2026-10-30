import json

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from generator.knowledge import build_index
from generator.worker import RoleAgent


class Result(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str


class Model:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, stage, instruction, context, schema):
        self.calls.append({"stage": stage, "instruction": instruction, "context": context})
        return schema.model_validate(next(self.responses))


def agent(tmp_path, responses, **kwargs):
    return RoleAgent(
        Model(responses),
        tmp_path,
        tmp_path / "knowledge.sqlite",
        tmp_path / ".pipeline",
        {"contract.json", "../secret.txt", ".env"},
        **kwargs,
    )


def finish(content="complete"):
    return {"kind": "finish", "result": {"content": content}}


def request(tool):
    return {"kind": "request", "tools": [tool]}


def test_role_can_finish_without_tools(tmp_path):
    worker = agent(tmp_path, [finish()])
    result = worker.generate("architecture", "Design", "supplied contract", Result)
    assert result.content == "complete"
    assert len(worker.model.calls) == 1
    assert worker.model.calls[0]["stage"] == "architecture-turn-0"
    assert not (tmp_path / ".pipeline" / "agent-tools").exists()


def test_role_reads_allowlisted_artifact_and_persists_provenance(tmp_path):
    (tmp_path / "contract.json").write_text('{"field":"id"}', encoding="utf-8")
    worker = agent(
        tmp_path, [request({"name": "read_artifact", "path": "contract.json"}), finish()]
    )
    worker.generate("backend-models", "Use actual types", "base context", Result)
    supplied = json.loads(worker.model.calls[1]["context"].split("ROLE TOOL CONTEXT\n", 1)[1])
    assert supplied["latest_tool_results"][0]["result"]["text"] == '{"field":"id"}'
    events = [
        json.loads(row)
        for row in (tmp_path / ".pipeline" / "events.jsonl").read_text().splitlines()
    ]
    evidence = events[0]
    assert evidence["kind"] == "agent_tool_executed"
    assert evidence["path"] == "contract.json"
    stored = json.loads((tmp_path / ".pipeline" / evidence["reference"]).read_text())
    assert stored["result"]["text"] == '{"field":"id"}'


def test_role_searches_knowledge_with_source_fingerprint(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "rules.txt").write_text("HTTP API authorization contract", encoding="utf-8")
    build_index(sources, tmp_path / "knowledge.sqlite")
    worker = agent(
        tmp_path,
        [request({"name": "search_knowledge", "query": "authorization", "limit": 1}), finish()],
    )
    worker.generate("architect", "Design", "base", Result)
    assert "HTTP API authorization contract" in worker.model.calls[1]["context"]
    logged = json.loads((tmp_path / ".pipeline" / "events.jsonl").read_text().splitlines()[0])
    assert logged["sources"][0]["source"] == "rules.txt"
    assert len(logged["sources"][0]["sha256"]) == 64


@pytest.mark.parametrize("path", ["unlisted.json", "../secret.txt", ".env"])
def test_role_rejects_unlisted_and_protected_paths_before_reading(tmp_path, path):
    worker = agent(tmp_path, [request({"name": "read_artifact", "path": path})])
    with pytest.raises(ValueError):
        worker.generate("developer", "Implement", "base", Result)
    assert len(worker.model.calls) == 1


@pytest.mark.parametrize(
    "tool",
    [
        {"name": "run_shell", "command": "ls"},
        {"name": "search_knowledge", "query": "contract", "limit": 10},
        {"name": "read_artifact", "path": "contract.json", "command": "ls"},
    ],
)
def test_role_rejects_invalid_tools(tmp_path, tool):
    worker = agent(tmp_path, [request(tool)])
    with pytest.raises(ValidationError):
        worker.generate("developer", "Implement", "base", Result)


def test_role_exhaustion_terminates_without_extra_model_call(tmp_path):
    lookup = request({"name": "search_knowledge", "query": "contract"})
    worker = agent(tmp_path, [lookup, lookup], max_tool_rounds=1)
    with pytest.raises(ValueError, match="exhausted 1 tool rounds"):
        worker.generate("architect", "Design", "base", Result)
    assert len(worker.model.calls) == 2
    assert "must finish now" in worker.model.calls[-1]["instruction"]


def test_oversized_artifact_is_not_truncated(tmp_path):
    (tmp_path / "contract.json").write_text("x" * 2000, encoding="utf-8")
    worker = agent(
        tmp_path,
        [request({"name": "read_artifact", "path": "contract.json"})],
        max_read_context_chars=500,
    )
    with pytest.raises(ValueError, match="decompose the task"):
        worker.generate("developer", "Implement", "base", Result)
    assert len(worker.model.calls) == 1
    assert not (tmp_path / ".pipeline" / "agent-tools").exists()


def test_each_round_replaces_bodies_but_retains_lookup_references(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "rules.txt").write_text("authorization UNIQUE_FIRST_BODY", encoding="utf-8")
    build_index(sources, tmp_path / "knowledge.sqlite")
    (tmp_path / "contract.json").write_text("UNIQUE_SECOND_BODY", encoding="utf-8")
    worker = agent(
        tmp_path,
        [
            request({"name": "search_knowledge", "query": "authorization"}),
            request({"name": "read_artifact", "path": "contract.json"}),
            finish(),
        ],
    )
    worker.generate("developer", "Implement", "base", Result)
    final_context = worker.model.calls[-1]["context"]
    assert "UNIQUE_FIRST_BODY" not in final_context
    assert "UNIQUE_SECOND_BODY" in final_context
    assert '"query": "authorization"' in final_context
    assert '"lookup_references"' in final_context
