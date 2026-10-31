import io
import struct
import zipfile

import pytest

from generator.knowledge import MAX_TEXT_BYTES, build_index, extract, retrieve


NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def document(body):
    return f'<w:document xmlns:w="{NS}"><w:body>{body}</w:body></w:document>'.encode()


def archive_bytes(entries, compression=zipfile.ZIP_STORED):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=compression) as archive:
        for name, data in entries:
            archive.writestr(name, data)
    return stream.getvalue()


def docx_bytes(xml, extra=(), compression=zipfile.ZIP_STORED):
    return archive_bytes([
        ('[Content_Types].xml', b'<Types/>'), ('word/document.xml', xml), *extra,
    ], compression)


def test_docx_detected_by_contents_and_preserves_paragraphs_tables_and_whitespace(tmp_path):
    path = tmp_path / 'brief-without-extension'
    path.write_bytes(docx_bytes(document(
        '<w:p><w:r><w:t>First</w:t><w:tab/><w:t>value</w:t><w:br/>'
        '<w:t>next line</w:t></w:r></w:p>'
        '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Table cell</w:t></w:r></w:p>'
        '</w:tc></w:tr></w:tbl><w:p/><w:p><w:r><w:t>Последний</w:t></w:r></w:p>'
    )))
    assert extract(path) == 'First\tvalue\nnext line\nTable cell\n\nПоследний'
    assert [p.name for p in tmp_path.iterdir()] == [path.name]


def test_docx_can_be_indexed_and_retrieved(tmp_path):
    source = tmp_path / 'sources'
    source.mkdir()
    (source / 'rules.docx').write_bytes(docx_bytes(document(
        '<w:p><w:r><w:t>Authentication access rules</w:t></w:r></w:p>'
    )))
    database = tmp_path / 'index.sqlite'
    assert build_index(source, database) == 1
    result = retrieve(database, 'Authentication')
    assert result[0]['source'] == 'rules.docx'
    assert result[0]['text'] == 'Authentication access rules'


def test_docx_zip_bomb_is_rejected_before_xml_parse(tmp_path):
    path = tmp_path / 'bomb.docx'
    path.write_bytes(docx_bytes(b'not XML' * 100000, compression=zipfile.ZIP_DEFLATED))
    with pytest.raises(ValueError, match='compression ratio'):
        extract(path)


def test_docx_too_many_entries_rejected_before_reading_xml(tmp_path):
    path = tmp_path / 'many.docx'
    extra = [(f'unused/{index}', b'') for index in range(999)]
    path.write_bytes(docx_bytes(b'not XML', extra))
    with pytest.raises(ValueError, match='1000 entries'):
        extract(path)


@pytest.mark.parametrize('missing', ['word/document.xml', '[Content_Types].xml'])
def test_docx_requires_both_identifying_entries(tmp_path, missing):
    path = tmp_path / 'missing.docx'
    entries = [('[Content_Types].xml', b'<Types/>'), ('word/document.xml', document(''))]
    path.write_bytes(archive_bytes([(name, data) for name, data in entries if name != missing]))
    with pytest.raises(ValueError, match=r'requires .*word/document.xml'):
        extract(path)


@pytest.mark.parametrize('content', [b'This is text', b'\xff\xd8\xff', b'PK\x03\x04broken'])
def test_docx_extension_cannot_disguise_other_content(tmp_path, content):
    path = tmp_path / 'fake.docx'
    path.write_bytes(content)
    with pytest.raises(ValueError, match='valid ZIP'):
        extract(path)


@pytest.mark.parametrize(
    ('declared_size', 'message'),
    [(10 * 1024 * 1024 + 1, '10 MiB uncompressed'),
     (50 * 1024 * 1024 + 1, '50 MiB uncompressed')],
)
def test_docx_uncompressed_limits_checked_from_metadata_before_reading(tmp_path, declared_size, message):
    raw = bytearray(docx_bytes(b'not XML'))
    first = raw.index(b'PK\x01\x02')
    document_entry = raw.index(b'PK\x01\x02', first + 4)
    struct.pack_into('<I', raw, document_entry + 24, declared_size)
    path = tmp_path / 'oversized.docx'
    path.write_bytes(raw)
    with pytest.raises(ValueError, match=message):
        extract(path)


def test_docx_reads_only_document_xml_and_never_extracts_other_entries(tmp_path):
    raw = bytearray(docx_bytes(
        document('<w:p><w:r><w:t>Safe text</w:t></w:r></w:p>'),
        [('word/embeddings/payload.bin', b'PAYLOAD'), ('../../outside.txt', b'ESCAPE')],
    ))
    # Invalid CRCs on unused entries make any attempt to read them fail.
    raw[raw.index(b'<Types/>')] = ord('!')
    raw[raw.index(b'PAYLOAD')] = ord('!')
    path = tmp_path / 'with-attachments.docx'
    path.write_bytes(raw)
    assert extract(path) == 'Safe text'
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize('encoding', ['utf-8', 'utf-16'])
def test_docx_rejects_dtd_and_entities_without_resolving_them(tmp_path, encoding):
    xml = ('<!DOCTYPE document [<!ENTITY payload SYSTEM "file:///does-not-exist">]>'
           f'<w:document xmlns:w="{NS}"><w:body><w:p><w:r><w:t>&payload;</w:t>'
           '</w:r></w:p></w:body></w:document>').encode(encoding)
    path = tmp_path / 'entities.docx'
    path.write_bytes(docx_bytes(xml))
    with pytest.raises(ValueError, match='DTD'):
        extract(path)


def test_docx_text_limit_is_shared_with_other_brief_formats(tmp_path):
    path = tmp_path / 'large-text.docx'
    path.write_bytes(docx_bytes(document(
        '<w:p><w:r><w:t>' + 'x' * (MAX_TEXT_BYTES + 1) + '</w:t></w:r></w:p>'
    )))
    with pytest.raises(ValueError, match='200 KiB'):
        extract(path)


@pytest.mark.parametrize('xml', [b'not XML', b'<html/>'])
def test_docx_invalid_document_xml_is_rejected(tmp_path, xml):
    path = tmp_path / 'invalid.docx'
    path.write_bytes(docx_bytes(xml))
    with pytest.raises(ValueError, match='DOCX.*XML|DOCX XML'):
        extract(path)
