import hashlib
import re
import sqlite3
from pathlib import Path

from pypdf import PdfReader


def extract(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8-sig")


def build_index(sources: Path, database: Path) -> int:
    database.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TABLE IF EXISTS chunks")
        connection.execute("CREATE VIRTUAL TABLE chunks USING fts5(source, sha256, body)")
        for path in sorted(sources.rglob("*")):
            if path.suffix.lower() not in {".pdf", ".md", ".txt"}:
                continue
            text = extract(path)
            fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
            for start in range(0, len(text), 3500):
                connection.execute(
                    "INSERT INTO chunks VALUES (?, ?, ?)",
                    (str(path.relative_to(sources)), fingerprint, text[start:start + 4000]),
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
