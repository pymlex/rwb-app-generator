import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from generator.models import ArtifactBatch


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def source_span(source: str, quote: str) -> str:
    pattern = r"\s+".join(re.escape(word) for word in quote.split())
    match = re.search(pattern, source) if pattern else None
    if match is None:
        raise ValueError("Source quotation cannot be found verbatim")
    return match.group(0)


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def event(root: Path, kind: str, **data):
    root.mkdir(parents=True, exist_ok=True)
    with (root / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps({"time": datetime.now(UTC).isoformat(), "kind": kind, **data}) + "\n"
        )


def artifact_path(root: Path, name: str) -> Path:
    path = PurePosixPath(name)
    if "\\" in name or ":" in name or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe artifact path: {name}")
    if any(
        part.lower() in {".git", ".ssh", "node_modules"} or part.lower().startswith(".env")
        for part in path.parts
    ):
        raise ValueError(f"Protected artifact path: {name}")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Artifact escapes output directory: {name}")
    return target


def save_batch(root: Path, batch: ArtifactBatch, allowed: set[str] | None = None):
    paths = [item.path for item in batch.files]
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate artifact paths")
    if allowed is not None and set(paths) != allowed:
        raise ValueError(f"Expected artifacts {sorted(allowed)}, received {sorted(paths)}")
    targets = [(artifact_path(root, item.path), item.content) for item in batch.files]
    for target, content in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.rstrip() + "\n", encoding="utf-8")
