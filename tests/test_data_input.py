import json
import sys

import pytest

import main
from generator.config import Settings
from generator.pipeline import MAX_DATA_FILE_BYTES, Pipeline, copy_data


def test_copies_only_top_level_json_preserving_bytes(tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    raw = b'{"records": [{"id": "original"}]}\n'
    (source / "spb.json").write_bytes(raw)
    (source / "notes.txt").write_text("not JSON")
    (source / "nested").mkdir()
    (source / "nested" / "extra.json").write_text("{}")
    output = tmp_path / "run"
    copy_data(source, output)
    assert (output / "backend/data/spb.json").read_bytes() == raw
    assert [p.name for p in (output / "backend/data").iterdir()] == ["spb.json"]


def test_invalid_json_rejects_entire_batch_before_copying(tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    (source / "a.json").write_text('{}')
    (source / "z.json").write_text('not JSON')
    output = tmp_path / "run"
    with pytest.raises(ValueError, match="valid UTF-8 JSON"):
        copy_data(source, output)
    assert not output.exists()


def test_large_data_file_is_rejected(tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    with (source / "large.json").open("wb") as stream:
        stream.truncate(MAX_DATA_FILE_BYTES + 1)
    with pytest.raises(ValueError, match="50 MiB"):
        copy_data(source, tmp_path / "run")
    assert not (tmp_path / "run").exists()


def test_total_data_limit_and_boundary(tmp_path, monkeypatch):
    source = tmp_path / "data"
    source.mkdir()
    for name in ["a.json", "b.json"]:
        (source / name).write_bytes(b'{}  ')
    monkeypatch.setattr("generator.pipeline.MAX_DATA_FILE_BYTES", 4)
    monkeypatch.setattr("generator.pipeline.MAX_DATA_TOTAL_BYTES", 8)
    copy_data(source, tmp_path / "allowed")
    assert len(list((tmp_path / "allowed/backend/data").iterdir())) == 2
    (source / "c.json").write_bytes(b'{}')
    with pytest.raises(ValueError, match="100 MiB"):
        copy_data(source, tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()


def test_data_symlinks_and_output_escape_are_rejected(tmp_path):
    source = tmp_path / "data"
    source.mkdir()
    external = tmp_path / "outside.json"
    external.write_text('{}')
    link = source / "linked.json"
    link.symlink_to(external)
    with pytest.raises(ValueError, match="symlinks"):
        copy_data(source, tmp_path / "run")
    link.unlink()
    (source / "spb.json").write_text('{}')
    output = tmp_path / "run"
    output.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (output / "backend").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        copy_data(source, output)
    assert list(outside.iterdir()) == []


def test_pipeline_rejects_bad_data_before_model_call(tmp_path, monkeypatch):
    source = tmp_path / "data"
    source.mkdir()
    (source / "spb.json").write_text('not JSON')
    pipeline = Pipeline(Settings("http://model/v1", "dummy-key"), tmp_path / "run", tmp_path / "db")

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid data reached the model")

    monkeypatch.setattr(pipeline.model, "generate", forbidden)
    with pytest.raises(ValueError, match="JSON"):
        pipeline.run("Build inventory", data=source)
    assert not (tmp_path / "run").exists()


def test_cli_passes_data_directory(tmp_path, monkeypatch, capsys):
    brief = tmp_path / "brief.md"
    brief.write_text("Build inventory")
    source = tmp_path / "data"
    output = tmp_path / "run"
    received = {}

    def run(self, requirements, answers, **kwargs):
        received.update(kwargs)
        return {"status": "needs_clarification"}

    monkeypatch.setattr(main.Settings, "from_env", lambda: Settings("http://model/v1", "dummy-key"))
    monkeypatch.setattr(main.Pipeline, "run", run)
    monkeypatch.setattr(sys, "argv", [
        "main.py", "generate", str(brief), "--output", str(output), "--data", str(source),
    ])
    main.main()
    assert received["data"] == source
    assert json.loads(capsys.readouterr().out)["status"] == "needs_clarification"
