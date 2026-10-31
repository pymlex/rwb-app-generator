import hashlib
import json

import pytest

from generator.resume import recover_service_packages


CONTRACT = """
public interface IDomainService
{
    Task Initialise();
    Task<OperationResult<string>> Create(Actor actor, CreateRequest request);
    Task<OperationResult<List<string>>> List(Actor actor);
}
"""


def checkpointed_part(root, number, methods, *, envelope=True, suffix="", requirement_ids=None):
    path = f"backend/DomainService.Part{number:02}{suffix}.cs"
    declarations = []
    for name in methods:
        declarations.append(f"    public async Task {name}() {{ await Task.CompletedTask; }}")
    source = (
        "public partial class DomainService\n{\n"
        + "\n".join(declarations)
        + "\n    private Task Helper() => Task.CompletedTask;\n}\n"
    )
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.encode())
    result = {
        "files": [
            {
                "path": path,
                "content": source.rstrip(),
                "requirement_ids": requirement_ids or ["FR-001"],
            }
        ]
    }
    saved = {"kind": "finish", "result": result} if envelope else result
    checkpoint = (
        root
        / ".pipeline/checkpoints"
        / f"backend-service-{number:02}-turn-0-fingerprint{suffix}.json"
    )
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(json.dumps(saved), encoding="utf-8")
    return target, checkpoint


def test_recovers_actual_methods_and_original_requirement_links_without_old_assignments(tmp_path):
    first, _ = checkpointed_part(tmp_path, 1, ["List"], requirement_ids=["FR-003"])
    checkpointed_part(tmp_path, 7, ["Initialise"])
    checkpointed_part(tmp_path, 3, ["Create"], envelope=False)
    recovered = recover_service_packages(tmp_path, CONTRACT)
    assert [entry["methods"] for entry in recovered] == [["Initialise"], ["List"], ["Create"]]
    assert recovered[1]["path"] == "backend/DomainService.Part01.cs"
    assert recovered[1]["requirement_ids"] == ["FR-003"]
    assert recovered[1]["sha256"] == hashlib.sha256(first.read_bytes()).hexdigest()


def test_edited_generated_source_is_not_recovered(tmp_path):
    path, _ = checkpointed_part(tmp_path, 1, ["Initialise"])
    path.write_bytes(path.read_bytes().replace(b"await Task.CompletedTask", b"await Task.Delay(1)"))
    assert recover_service_packages(tmp_path, CONTRACT) == []


def test_file_without_saved_finish_artifact_is_not_recovered(tmp_path):
    _, saved = checkpointed_part(tmp_path, 1, ["Initialise"])
    saved.write_text(json.dumps({"kind": "request", "tools": []}), encoding="utf-8")
    assert recover_service_packages(tmp_path, CONTRACT) == []


def test_unknown_current_contract_method_is_not_recovered(tmp_path):
    checkpointed_part(tmp_path, 1, ["Create", "RemovedLegacyMethod"])
    assert recover_service_packages(tmp_path, CONTRACT) == []


def test_duplicate_public_methods_in_different_provenance_valid_parts_are_rejected(tmp_path):
    checkpointed_part(tmp_path, 1, ["Create"])
    checkpointed_part(tmp_path, 2, ["Create"])
    with pytest.raises(ValueError, match="duplicated"):
        recover_service_packages(tmp_path, CONTRACT)


def test_child_work_packages_and_unproven_sources_are_excluded(tmp_path):
    checkpointed_part(tmp_path, 1, ["Create"], suffix="A")
    checkpointed_part(tmp_path, 2, ["List"], suffix="B")
    path, saved = checkpointed_part(tmp_path, 3, ["Initialise"])
    saved.unlink()
    assert path.exists()
    assert recover_service_packages(tmp_path, CONTRACT) == []


def test_checkpoint_must_prove_the_exact_artifact_path_and_content(tmp_path):
    _, saved = checkpointed_part(tmp_path, 1, ["Initialise"])
    envelope = json.loads(saved.read_text(encoding="utf-8"))
    envelope["result"]["files"][0]["path"] = "backend/DomainService.Part02.cs"
    saved.write_text(json.dumps(envelope), encoding="utf-8")
    assert recover_service_packages(tmp_path, CONTRACT) == []


@pytest.mark.parametrize("stage", ["backend-repair-01-turn-0-hash", "application-repair-02-turn-0-hash"])
def test_generated_repair_is_preserved_on_restart(tmp_path, stage):
    path, original_checkpoint = checkpointed_part(tmp_path, 1, ["Create"])
    source = path.read_text(encoding="utf-8").replace("await Task.CompletedTask", "await Task.Delay(1)")
    path.write_bytes(source.encode())
    repaired = {
        "kind": "finish",
        "result": {
            "files": [{"path": "backend/DomainService.Part01.cs", "content": source, "requirement_ids": ["FR-002"]}]
        },
    }
    (original_checkpoint.parent / f"{stage}.json").write_text(json.dumps(repaired), encoding="utf-8")
    recovered = recover_service_packages(tmp_path, CONTRACT)
    assert len(recovered) == 1
    assert recovered[0]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert recovered[0]["requirement_ids"] == ["FR-002"]


@pytest.mark.parametrize("stage", ["analysis-turn-0-hash", "documentation-turn-0-hash"])
def test_unrelated_stage_cannot_prove_a_changed_service_file(tmp_path, stage):
    path, original_checkpoint = checkpointed_part(tmp_path, 1, ["Create"])
    source = path.read_text(encoding="utf-8").replace("await Task.CompletedTask", "await Task.Delay(1)")
    path.write_bytes(source.encode())
    unrelated = {
        "kind": "finish",
        "result": {
            "files": [{"path": "backend/DomainService.Part01.cs", "content": source, "requirement_ids": ["FR-002"]}]
        },
    }
    (original_checkpoint.parent / f"{stage}.json").write_text(json.dumps(unrelated), encoding="utf-8")
    assert recover_service_packages(tmp_path, CONTRACT) == []
