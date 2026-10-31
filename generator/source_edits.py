from pathlib import Path

from pydantic import Field

from generator.models import Artifact, ArtifactBatch, StrictModel
from generator.storage import artifact_path


class SourceEdit(StrictModel):
    path: str
    old: str = Field(min_length=1)
    new: str


class SourceEdits(StrictModel):
    edits: list[SourceEdit] = Field(min_length=1, max_length=30)


def prepare_source_edits(
    root: Path, edits: SourceEdits, allowed: set[str], requirement_ids: list[str]
) -> ArtifactBatch:
    paths = {edit.path for edit in edits.edits}
    if len(paths) != 1 or not paths <= allowed:
        raise ValueError("Compiler edits must target exactly one allowed file")
    name = next(iter(paths))
    path = artifact_path(root, name)
    source = path.read_text(encoding="utf-8")
    replacements = []
    for edit in edits.edits:
        if edit.old == edit.new or source.count(edit.old) != 1:
            raise ValueError("Every compiler edit must match exactly one unchanged source span")
        start = source.index(edit.old)
        end = start + len(edit.old)
        if any(
            start < previous_end and previous_start < end
            for previous_start, previous_end, _ in replacements
        ):
            raise ValueError("Compiler source edits must not overlap")
        replacements.append((start, end, edit.new))
    for start, end, replacement in sorted(replacements, reverse=True):
        source = source[:start] + replacement + source[end:]
    return ArtifactBatch(
        files=[Artifact(path=name, content=source, requirement_ids=requirement_ids)]
    )
