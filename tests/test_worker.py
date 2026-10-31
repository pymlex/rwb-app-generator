import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from generator.knowledge import build_index
from generator.worker import RoleAgent, csharp_members, response_envelope


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
        [request({"name": "read_artifact", "path": "contract.json"}), finish()],
        max_read_context_chars=800,
    )
    worker.generate("developer", "Implement", "base", Result)
    assert len(worker.model.calls) == 2
    supplied = json.loads(worker.model.calls[1]["context"].split("ROLE TOOL CONTEXT\n", 1)[1])
    result = supplied["latest_tool_results"][0]["result"]
    assert result["error"] == "tool_context_budget_exceeded"
    assert result["actual_chars"] > 2000
    assert "text" not in result


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


CSHARP = '''public sealed partial class DomainService
{
    public async Task<string> LookupAsync(string id)
    {
        var sql = """
            SELECT '{"nested":{"key":"}"}}'::jsonb;
            """;
        var verbatim = @"{{ escaped ""quote"" }}";
        // } ignored
        if (id.Length > 0) { return sql; }
        return verbatim;
    }

    private int Count() => 3;

    public string Name { get; set; } = "demo";
}
'''


def test_csharp_member_is_complete_with_raw_strings_and_nested_braces():
    members = csharp_members(CSHARP)
    assert [member["name"] for member in members] == ["LookupAsync", "Count", "Name"]
    first = members[0]
    body = CSHARP[first["start"] : first["end"]]
    assert body.startswith("    public async Task<string> LookupAsync")
    assert body.endswith("return verbatim;\n    }")
    assert "private int Count" not in body
    assert "SELECT" in body
    prop = members[2]
    assert CSHARP[prop["start"] : prop["end"]].endswith('= "demo";')


def test_oversized_combined_reads_can_recover_by_symbol_in_next_round(tmp_path):
    (tmp_path / "part.cs").write_text(CSHARP + "\n" + " " * 14000, encoding="utf-8")
    worker = RoleAgent(
        Model(
            [
                {
                    "kind": "request",
                    "tools": [
                        {"name": "read_artifact", "path": "part.cs"},
                        {"name": "read_artifact", "path": "part.cs"},
                    ],
                },
                request({"name": "read_artifact", "path": "part.cs", "symbol": "LookupAsync"}),
                finish(),
            ]
        ),
        tmp_path,
        tmp_path / "missing.sqlite",
        tmp_path / ".pipeline",
        {"part.cs"},
        max_read_context_chars=6000,
    )
    result = worker.generate("backend-service-07", "Implement", "base", Result)
    assert result.content == "complete"
    second = json.loads(worker.model.calls[1]["context"].split("ROLE TOOL CONTEXT\n", 1)[1])
    assert all(
        row["result"]["error"] == "tool_context_budget_exceeded"
        for row in second["latest_tool_results"]
    )
    assert "LookupAsync" in second["latest_tool_results"][0]["result"]["available_symbols"]
    final = json.loads(worker.model.calls[2]["context"].split("ROLE TOOL CONTEXT\n", 1)[1])
    body = final["latest_tool_results"][0]["result"]["text"]
    assert body.endswith("return verbatim;\n    }")
    assert "private int Count" not in body
    assert len(worker.model.calls) == 3


def test_tool_budget_reserves_full_longest_prefix_output_cap(tmp_path):
    worker = agent(tmp_path, [finish()])
    worker.model.settings = SimpleNamespace(
        tpm_limit=30000,
        context_limit=32768,
        max_output_tokens=14000,
        token_margin=512,
    )
    schema = response_envelope(Result)
    budget = worker._tool_budget("backend-service-07", "instruction", "x" * 60000, schema)
    assert 0 < budget < 18000
    assert worker._tool_budget("backend-service-07", "instruction", "x" * 90000, schema) == 0


def test_missing_symbol_returns_catalogue_instead_of_unrelated_code(tmp_path):
    (tmp_path / "part.cs").write_text(CSHARP, encoding="utf-8")
    worker = RoleAgent(
        Model(
            [request({"name": "read_artifact", "path": "part.cs", "symbol": "Missing"}), finish()]
        ),
        tmp_path,
        tmp_path / "missing.sqlite",
        tmp_path / ".pipeline",
        {"part.cs"},
    )
    worker.generate("developer", "Implement", "base", Result)
    supplied = json.loads(worker.model.calls[1]["context"].split("ROLE TOOL CONTEXT\n", 1)[1])
    result = supplied["latest_tool_results"][0]["result"]
    assert result["error"] == "symbol_not_found_or_ambiguous"
    assert result["available_symbols"] == ["LookupAsync", "Count", "Name"]
    assert "text" not in result


def test_role_loads_skill_on_demand_and_records_provenance(tmp_path, monkeypatch):
    skill_root = tmp_path / "fixed-skills"
    skill_root.mkdir()
    (skill_root / "events.md").write_text(
        "UNIQUE_SKILL_BODY transactional outbox", encoding="utf-8"
    )
    monkeypatch.setattr("generator.worker.SKILL_ROOT", skill_root)
    worker = agent(tmp_path, [request({"name": "load_skill", "skill": "events"}), finish()])
    worker.generate("backend-service", "Implement", "base", Result)
    assert "UNIQUE_SKILL_BODY" not in worker.model.calls[0]["context"]
    assert "UNIQUE_SKILL_BODY" in worker.model.calls[1]["context"]
    logged = json.loads((tmp_path / ".pipeline" / "events.jsonl").read_text().splitlines()[0])
    assert logged["tool"] == "load_skill"
    assert logged["skill"] == "events"
    assert len(logged["sha256"]) == 64
    stored = json.loads((tmp_path / ".pipeline" / logged["reference"]).read_text())
    assert stored["result"]["text"] == "UNIQUE_SKILL_BODY transactional outbox"


@pytest.mark.parametrize("skill", ["unknown", "../secret", "C:/secret"])
def test_role_rejects_unknown_or_traversal_skill_names(tmp_path, skill):
    worker = agent(tmp_path, [request({"name": "load_skill", "skill": skill})])
    with pytest.raises(ValidationError):
        worker.generate("backend-service", "Implement", "base", Result)


def test_loaded_skill_survives_later_artifact_lookup(tmp_path, monkeypatch):
    skill_root = tmp_path / "fixed-skills"
    skill_root.mkdir()
    (skill_root / "events.md").write_text("PINNED_SKILL_BODY", encoding="utf-8")
    monkeypatch.setattr("generator.worker.SKILL_ROOT", skill_root)
    (tmp_path / "contract.json").write_text("LATEST_ARTIFACT_BODY", encoding="utf-8")
    worker = agent(tmp_path, [
        request({"name": "load_skill", "skill": "events"}),
        request({"name": "read_artifact", "path": "contract.json"}),
        finish(),
    ])
    worker.generate("backend-service", "Implement", "base", Result)
    final = json.loads(worker.model.calls[2]["context"].split("ROLE TOOL CONTEXT\n", 1)[1])
    assert len(final["loaded_skills"]) == 1
    assert final["loaded_skills"][0]["result"]["text"] == "PINNED_SKILL_BODY"
    assert final["latest_tool_results"][0]["result"]["text"] == "LATEST_ARTIFACT_BODY"


def test_pinned_skill_body_reduces_later_artifact_budget(tmp_path, monkeypatch):
    skill_root = tmp_path / "fixed-skills"
    skill_root.mkdir()
    (skill_root / "events.md").write_text("s" * 3000, encoding="utf-8")
    monkeypatch.setattr("generator.worker.SKILL_ROOT", skill_root)
    (tmp_path / "contract.json").write_text("a" * 5000, encoding="utf-8")
    worker = agent(tmp_path, [
        request({"name": "load_skill", "skill": "events"}),
        request({"name": "read_artifact", "path": "contract.json"}),
        finish(),
    ], max_read_context_chars=6500)
    worker.generate("backend-service", "Implement", "base", Result)
    final = json.loads(worker.model.calls[2]["context"].split("ROLE TOOL CONTEXT\n", 1)[1])
    assert len(final["loaded_skills"]) == 1
    assert final["latest_tool_results"][0]["result"]["error"] == "tool_context_budget_exceeded"


def test_reloading_same_skill_does_not_duplicate_pinned_body(tmp_path, monkeypatch):
    skill_root = tmp_path / "fixed-skills"
    skill_root.mkdir()
    (skill_root / "events.md").write_text("PINNED_ONCE", encoding="utf-8")
    monkeypatch.setattr("generator.worker.SKILL_ROOT", skill_root)
    lookup = request({"name": "load_skill", "skill": "events"})
    worker = agent(tmp_path, [lookup, lookup, finish()])
    worker.generate("backend-service", "Implement", "base", Result)
    final = json.loads(worker.model.calls[2]["context"].split("ROLE TOOL CONTEXT\n", 1)[1])
    assert len(final["loaded_skills"]) == 1
    assert worker.model.calls[2]["context"].count("PINNED_ONCE") == 1
