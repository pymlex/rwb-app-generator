from types import SimpleNamespace

import pytest

from generator.agents import AgentState
from generator.config import Settings
from generator.pipeline import Pipeline
from generator.resume import recover_service_packages
from generator.source_edits import SourceEdit, SourceEdits, prepare_source_edits


def edit(path, old, new):
    return SourceEdit(path=path, old=old, new=new)


def test_exact_source_edits_preserve_every_unrelated_character(tmp_path):
    path = "Domain.cs"
    original = "var count = 1;\nvar other = 2;\n"
    (tmp_path / path).write_text(original, encoding="utf-8")
    batch = prepare_source_edits(
        tmp_path,
        SourceEdits(
            edits=[
                edit(path, "var count = 1;", "int? count = null;"),
                edit(path, "var other = 2;", "var other = 3;"),
            ]
        ),
        {path},
        ["FR-001"],
    )
    assert batch.files[0].content == "int? count = null;\nvar other = 3;\n"
    assert batch.files[0].requirement_ids == ["FR-001"]
    assert (tmp_path / path).read_text() == original


@pytest.mark.parametrize("old", ["missing", "repeat"])
def test_edit_requires_one_exact_original_occurrence(tmp_path, old):
    (tmp_path / "Domain.cs").write_text("repeat repeat", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly one"):
        prepare_source_edits(
            tmp_path, SourceEdits(edits=[edit("Domain.cs", old, "fixed")]), {"Domain.cs"}, []
        )


def test_edits_reject_paths_outside_allowed_file(tmp_path):
    with pytest.raises(ValueError, match="allowed file"):
        prepare_source_edits(
            tmp_path, SourceEdits(edits=[edit("../outside.cs", "x", "y")]), {"Domain.cs"}, []
        )
    with pytest.raises(ValueError, match="Unsafe artifact"):
        prepare_source_edits(
            tmp_path, SourceEdits(edits=[edit("../outside.cs", "x", "y")]), {"../outside.cs"}, []
        )


def test_overlapping_edits_are_rejected_as_one_invalid_batch(tmp_path):
    (tmp_path / "Domain.cs").write_text("abcde", encoding="utf-8")
    with pytest.raises(ValueError, match="overlap"):
        prepare_source_edits(
            tmp_path,
            SourceEdits(edits=[edit("Domain.cs", "abc", "a"), edit("Domain.cs", "bcd", "b")]),
            {"Domain.cs"},
            [],
        )


SOURCE = """public sealed partial class DomainService
{
    public Task<int> Get()
    {
        return Task.FromResult(broken);
    }
}
"""


def compiler_pipeline(tmp_path, changes):
    name = "backend/DomainService.Part01.cs"
    (tmp_path / "backend").mkdir()
    (tmp_path / name).write_text(SOURCE, encoding="utf-8")
    pipeline = Pipeline(
        Settings("http://model/v1", "test-key"), tmp_path, tmp_path / "missing.sqlite"
    )
    pipeline.service_paths = [name]
    pipeline.generated = {name: {"path": name, "requirement_ids": ["FR-001"]}}
    pipeline.analysis = SimpleNamespace(requirements=[SimpleNamespace(id="FR-001")])
    calls = []

    def ask(stage, instruction, context, schema):
        calls.append((stage, context))
        return SourceEdits(edits=changes)

    pipeline.ask = ask
    state = AgentState(
        backend_repairs=1,
        feedback=[
            {
                "log": "/src/DomainService.Part01.cs(5,32): error CS0103: broken does not exist\n"
                "/src/Unrelated.cs(9,1): error CS0103: unrelated defect\nDocker unrelated build log",
            }
        ],
    )
    return pipeline, state, calls, name


def test_applied_compiler_repair_has_resume_recognized_full_artifact_checkpoint(tmp_path):
    name = "backend/DomainService.Part01.cs"
    pipeline, state, calls, _ = compiler_pipeline(
        tmp_path, [edit(name, "Task.FromResult(broken)", "Task.FromResult(1)")]
    )
    pipeline.backend_repair(state)
    assert calls[0][0].startswith("backend-compiler-repair-")
    assert "Docker unrelated build log" not in calls[0][1]
    assert "Unrelated.cs" not in calls[0][1]
    assert (tmp_path / name).read_text() == SOURCE.replace("broken", "1")
    assert (
        len(list((tmp_path / ".pipeline/checkpoints").glob("backend-repair-*-applied-*.json"))) == 1
    )
    recovered = recover_service_packages(
        tmp_path, "public interface IDomainService\n{\nTask<int> Get();\n}"
    )
    assert recovered[0]["path"] == name
    assert recovered[0]["methods"] == ["Get"]
    assert recovered[0]["requirement_ids"] == ["FR-001"]


def test_invalid_second_edit_does_not_apply_first_or_save_checkpoint(tmp_path):
    name = "backend/DomainService.Part01.cs"
    pipeline, state, _, _ = compiler_pipeline(
        tmp_path,
        [
            edit(name, "Task.FromResult(broken)", "Task.FromResult(1)"),
            edit(name, "not present", "fixed"),
        ],
    )
    with pytest.raises(ValueError, match="exactly one"):
        pipeline.backend_repair(state)
    assert (tmp_path / name).read_text() == SOURCE
    assert not (tmp_path / ".pipeline/checkpoints").exists()
