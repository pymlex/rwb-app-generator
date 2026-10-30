import hashlib

from generator.knowledge import build_index, retrieve


def test_retrieval_keeps_source_and_content_fingerprint(tmp_path):
    source = tmp_path / "sources"
    source.mkdir()
    document = source / "rules.md"
    document.write_text("Каждое требование имеет идентификатор. API содержит авторизацию.", encoding="utf-8")
    database = tmp_path / "index.sqlite"
    assert build_index(source, database) == 1
    result = retrieve(database, "авторизацию")
    assert len(result) == 1
    assert result[0]["source"] == "rules.md"
    assert result[0]["sha256"] == hashlib.sha256(document.read_bytes()).hexdigest()


def test_reindex_does_not_retain_deleted_regulations(tmp_path):
    source = tmp_path / "sources"
    source.mkdir()
    document = source / "rules.md"
    document.write_text("obsolete authentication", encoding="utf-8")
    database = tmp_path / "index.sqlite"
    build_index(source, database)
    document.unlink()
    build_index(source, database)
    assert retrieve(database, "obsolete") == []


def test_empty_or_absent_index_does_not_invent_context(tmp_path):
    assert retrieve(tmp_path / "missing.sqlite", "requirements") == []
