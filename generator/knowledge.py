import hashlib
import io
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from pypdf import PdfReader


MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_BYTES = 200 * 1024
MAX_PDF_PAGES = 50
MAX_ZIP_ENTRIES = 1000
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_ZIP_RATIO = 100
MAX_DOCUMENT_XML_BYTES = 10 * 1024 * 1024
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class NoDocumentType(ET.TreeBuilder):
    def doctype(self, name, pubid, system):
        raise ValueError("DOCX XML must not contain DTD declarations")


def extract_docx(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise ValueError("DOCX ZIP exceeds 1000 entries")
            if sum(entry.file_size for entry in entries) > MAX_ZIP_BYTES:
                raise ValueError("DOCX ZIP exceeds 50 MiB uncompressed")
            names = [entry.filename for entry in entries]
            if len(set(names)) != len(names):
                raise ValueError("DOCX ZIP contains duplicate entry names")
            if not {"[Content_Types].xml", "word/document.xml"} <= set(names):
                raise ValueError("DOCX ZIP requires [Content_Types].xml and word/document.xml")
            document = archive.getinfo("word/document.xml")
            if document.file_size > MAX_DOCUMENT_XML_BYTES:
                raise ValueError("DOCX word/document.xml exceeds 10 MiB uncompressed")
            for entry in entries:
                if entry.file_size > MAX_ZIP_RATIO * entry.compress_size:
                    raise ValueError("DOCX ZIP entry compression ratio exceeds 100")
                if entry.flag_bits & 1:
                    raise ValueError("Encrypted DOCX ZIP entries are not supported")
            with archive.open(document) as stream:
                xml = stream.read(MAX_DOCUMENT_XML_BYTES + 1)
            if len(xml) > MAX_DOCUMENT_XML_BYTES:
                raise ValueError("DOCX word/document.xml exceeds 10 MiB uncompressed")
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError):
        raise ValueError("Unable to read DOCX ZIP input") from None
    try:
        root = ET.fromstring(xml, parser=ET.XMLParser(target=NoDocumentType()))
    except ET.ParseError:
        raise ValueError("Invalid DOCX document XML") from None
    if root.tag != WORD_NS + "document":
        raise ValueError("DOCX XML must have a Word document root")

    def paragraphs():
        for paragraph in root.iter(WORD_NS + "p"):
            parts = []
            for node in paragraph.iter():
                if node.tag == WORD_NS + "t":
                    parts.append(node.text or "")
                elif node.tag == WORD_NS + "tab":
                    parts.append("\t")
                elif node.tag == WORD_NS + "br":
                    parts.append("\n")
            yield "".join(parts)

    return limited_text(paragraphs())


def limited_text(parts) -> str:
    result = []
    size = 0
    for part in parts:
        size += len(part.encode("utf-8")) + (1 if result else 0)
        if size > MAX_TEXT_BYTES:
            raise ValueError("Input text exceeds 200 KiB")
        result.append(part)
    return "\n".join(result)


def extract(path: Path) -> str:
    if not path.is_file():
        raise ValueError("Input must be a regular file")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Input file exceeds 10 MiB")
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Input file exceeds 10 MiB")
    if zipfile.is_zipfile(io.BytesIO(raw)):
        return extract_docx(raw)
    if path.suffix.lower() == ".docx" or raw.startswith(b"PK\x03\x04"):
        raise ValueError("DOCX input must be a valid ZIP with word/document.xml")
    if raw.startswith(b"%PDF-"):
        try:
            reader = PdfReader(io.BytesIO(raw))
            if len(reader.pages) > MAX_PDF_PAGES:
                raise ValueError("PDF exceeds 50 pages")
            return limited_text(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            if isinstance(exc, ValueError) and str(exc) in {
                "PDF exceeds 50 pages", "Input text exceeds 200 KiB"
            }:
                raise
            raise ValueError("Unable to read PDF input") from None
    if path.suffix.lower() == ".pdf":
        raise ValueError("PDF input must have a %PDF- signature")
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise ValueError("Text input must be valid UTF-8") from None
    if "\x00" in text:
        raise ValueError("Unsupported binary input; expected UTF-8 text or PDF")
    return limited_text([text])


def build_index(sources: Path, database: Path) -> int:
    database.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE IF EXISTS chunks")
        connection.execute("CREATE VIRTUAL TABLE chunks USING fts5(source, sha256, body)")
        for path in sorted(sources.rglob("*")):
            if path.suffix.lower() not in {".pdf", ".md", ".txt", ".docx"}:
                continue
            text = extract(path)
            fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
            for start in range(0, len(text), 3500):
                connection.execute(
                    "INSERT INTO chunks VALUES (?, ?, ?)",
                    (str(path.relative_to(sources)), fingerprint, text[start : start + 4000]),
                )
                count += 1
    return count


def retrieve(database: Path, query: str, limit: int = 6) -> list[dict]:
    if not database.exists():
        return []
    terms = re.findall(r"[\w]{3,}", query, flags=re.UNICODE)
    expression = " OR ".join('"' + term + '"' for term in dict.fromkeys(terms[:80]))
    if not expression:
        return []
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            "SELECT source, sha256, body FROM chunks WHERE chunks MATCH ? ORDER BY bm25(chunks) LIMIT ?",
            (expression, limit),
        ).fetchall()
    return [{"source": row[0], "sha256": row[1], "text": row[2]} for row in rows]
