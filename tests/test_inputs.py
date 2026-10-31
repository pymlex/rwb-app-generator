import json
import sys

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

import main
from generator.knowledge import MAX_FILE_BYTES, MAX_TEXT_BYTES, extract


def test_extract_rejects_large_file_before_reading(tmp_path):
    path = tmp_path / "brief.txt"
    with path.open("wb") as stream:
        stream.truncate(MAX_FILE_BYTES + 1)
    with pytest.raises(ValueError, match="10 MiB"):
        extract(path)


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("brief.pdf", b"plain text", "signature"),
        ("brief.txt", b"\xff", "UTF-8"),
        ("brief.txt", b"PK\x00\x00", "binary"),
        ("brief.txt", "я".encode() * (MAX_TEXT_BYTES // 2 + 1), "200 KiB"),
    ],
)
def test_extract_rejects_invalid_inputs(tmp_path, name, content, message):
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(ValueError, match=message):
        extract(path)


def test_extract_accepts_strict_utf8_with_bom_at_text_limit(tmp_path):
    path = tmp_path / "brief.md"
    text = "я" * (MAX_TEXT_BYTES // 2)
    path.write_bytes(b"\xef\xbb\xbf" + text.encode())
    assert extract(path) == text


@pytest.mark.parametrize("pages", [50, 51])
def test_pdf_content_detection_and_page_limit(tmp_path, pages):
    path = tmp_path / "pdf-with-text-extension.txt"
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=10, height=10)
    writer.write(path)
    if pages == 51:
        with pytest.raises(ValueError, match="50 pages"):
            extract(path)
    else:
        assert extract(path) == "\n" * 49


def test_pdf_extracted_text_limit(tmp_path):
    path = tmp_path / "brief.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=10, height=10)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): DictionaryObject({
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }),
        }),
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf (" + b"x" * (MAX_TEXT_BYTES + 1) + b") Tj ET")
    page[NameObject("/Contents")] = stream
    writer.write(path)
    with pytest.raises(ValueError, match="200 KiB"):
        extract(path)


@pytest.mark.parametrize(
    "content",
    [
        '[]', '{"extra":"value"}', '{"Q-1":"value"}', '{"Q-001":1}',
        '{"Q-001":""}', '{"Q-001":"one","Q-001":"two"}',
        json.dumps({"Q-001": "я" * 2049}), '{invalid',
    ],
)
def test_invalid_answers_stop_before_model_configuration(tmp_path, monkeypatch, capsys, content):
    brief = tmp_path / "brief.md"
    brief.write_text("Build inventory", encoding="utf-8")
    answers = tmp_path / "answers.json"
    answers.write_text(content, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "main.py", "generate", str(brief), "--answers", str(answers),
        "--output", str(tmp_path / "run"),
    ])

    def forbidden():
        pytest.fail("Invalid input reached model configuration")

    monkeypatch.setattr(main.Settings, "from_env", forbidden)
    with pytest.raises(SystemExit) as exc:
        main.main()
    assert exc.value.code == 2
    assert "error:" in capsys.readouterr().err
    assert not (tmp_path / "run").exists()


def test_answers_accept_json_object_and_four_kib_value(tmp_path):
    path = tmp_path / "answers.json"
    data = {"Q-001": "я" * 2048, "Q-023": "A decision"}
    path.write_text(json.dumps(data), encoding="utf-8")
    assert json.loads(main.read_answers(path)) == data
