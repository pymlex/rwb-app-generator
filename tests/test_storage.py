import json

import pytest

from generator.models import Artifact, ArtifactBatch
from generator.storage import artifact_path, save_batch, write_json


@pytest.mark.parametrize("name", ["../outside", "/absolute", "C:/absolute", "folder/../../outside", "folder\\outside", ".git/config", ".env", ".env.local", "folder/.ssh/key"])
def test_generated_paths_cannot_escape_or_overwrite_credentials(tmp_path, name):
    with pytest.raises(ValueError):
        artifact_path(tmp_path, name)


def test_wrong_stage_files_are_rejected_before_any_writes(tmp_path):
    batch = ArtifactBatch(files=[Artifact(path="backend/Domain.cs", content="valid", requirement_ids=[]), Artifact(path="main.py", content="invalid", requirement_ids=[])])
    with pytest.raises(ValueError):
        save_batch(tmp_path, batch, {"backend/Domain.cs"})
    assert not (tmp_path / "backend").exists()


def test_duplicate_artifacts_are_rejected(tmp_path):
    artifact = Artifact(path="docs/api.md", content="contract", requirement_ids=["FR-001"])
    with pytest.raises(ValueError):
        save_batch(tmp_path, ArtifactBatch(files=[artifact, artifact]))


def test_artifact_manifest_preserves_unicode_and_requirement_links(tmp_path):
    batch = ArtifactBatch(files=[Artifact(path="docs/api.md", content="Требования", requirement_ids=["FR-001"])])
    save_batch(tmp_path, batch, {"docs/api.md"})
    assert (tmp_path / "docs" / "api.md").read_text(encoding="utf-8") == "Требования\n"
    write_json(tmp_path / "manifest.json", batch.model_dump())
    assert json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))["files"][0]["requirement_ids"] == ["FR-001"]
