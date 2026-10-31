import hashlib
import json
import re
from collections import Counter
from pathlib import Path


MAX_FIELDS = 48
MAX_COLLECTIONS = 12
MAX_TOP_KEYS = 32
MAX_EXAMPLES = 2
MAX_EXAMPLE_CHARS = 160
WKT = re.compile(
    r"^\s*(?:SRID=\d+;\s*)?(GEOMETRYCOLLECTION|MULTILINESTRING|MULTIPOLYGON|MULTIPOINT|LINESTRING|POLYGON|POINT)\s*(?:ZM|Z|M)?\s*(?:\(|EMPTY\b)",
    re.IGNORECASE,
)


def value_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    return "object"


def member_path(parent: str, key: str) -> str:
    return parent + "[" + json.dumps(key, ensure_ascii=False) + "]"


def _profile_file(path: Path, folder: Path) -> dict:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    fields = {}
    collection_counts = Counter()
    geometry_counts = Counter()
    provider_ids = set()

    def visit(value: object, location: str, field: str | None = None) -> None:
        if location not in fields:
            fields[location] = {"path": location, "types": set(), "examples": []}
        entry = fields[location]
        entry["types"].add(value_type(value))
        if field and re.fullmatch(r"external.*id", re.sub(r"[_\-\s]", "", field), re.I):
            provider_ids.add(location)
        if isinstance(value, dict):
            for key in sorted(value):
                visit(value[key], member_path(location, key), key)
        elif isinstance(value, list):
            collection_counts[location] += len(value)
            for item in value:
                visit(item, location + "[]")
        else:
            match = WKT.match(value) if isinstance(value, str) else None
            if match:
                kind = match.group(1).upper()
                geometry_counts[kind] += 1
                example = {"value": f"<WKT {kind}>", "geometry_redacted": True}
            elif isinstance(value, str):
                example = {
                    "value": value[:MAX_EXAMPLE_CHARS],
                    "truncated": len(value) > MAX_EXAMPLE_CHARS,
                }
            else:
                example = {"value": value}
            if len(entry["examples"]) < MAX_EXAMPLES and example not in entry["examples"]:
                entry["examples"].append(example)

    visit(data, "$")
    ordered_fields = sorted(fields)
    ordered_collections = sorted(collection_counts)
    top_keys = sorted(data) if isinstance(data, dict) else []
    selected = []
    for location in ordered_fields[:MAX_FIELDS]:
        entry = fields[location]
        selected.append({**entry, "types": sorted(entry["types"])})
    return {
        "file": path.relative_to(folder).as_posix(),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "root_type": value_type(data),
        "top_keys": top_keys[:MAX_TOP_KEYS],
        "omitted_top_keys": max(0, len(top_keys) - MAX_TOP_KEYS),
        "collections": [
            {"path": location, "count": collection_counts[location]}
            for location in ordered_collections[:MAX_COLLECTIONS]
        ],
        "omitted_collections": max(0, len(ordered_collections) - MAX_COLLECTIONS),
        "fields": selected,
        "omitted_fields": max(0, len(ordered_fields) - MAX_FIELDS),
        "external_id_fields": sorted(provider_ids)[:MAX_FIELDS],
        "omitted_external_id_fields": max(0, len(provider_ids) - MAX_FIELDS),
        "geometry_counts": dict(sorted(geometry_counts.items())),
        "limits": {
            "fields": MAX_FIELDS,
            "collections": MAX_COLLECTIONS,
            "examples_per_field": MAX_EXAMPLES,
            "example_string_chars": MAX_EXAMPLE_CHARS,
        },
    }


def profile_data(folder: Path) -> list[dict]:
    return [_profile_file(path, folder) for path in sorted(folder.rglob("*.json"))]


def validate_contract(profile: list, models: str, sql: str) -> list[str]:
    defects = []
    code = re.sub(
        r'"""[\s\S]*?"""|@"(?:""|[^"])*"|"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27|//[^\n]*|/\*[\s\S]*?\*/',
        " ",
        models,
    )
    if re.search(r"\bnamespace\s+[A-Za-z_][\w.]*(?:\s*[;{])", code):
        defects.append(
            "Models declare a namespace, but the fixed backend platform requires global types."
        )
    geometries = {
        kind.upper()
        for item in profile
        for kind, count in item.get("geometry_counts", {}).items()
        if count > 0
    }
    statements = re.sub(r"--[^\n]*|/\*[\s\S]*?\*/", " ", sql)
    if (
        geometries
        and geometries <= {"LINESTRING", "MULTILINESTRING"}
        and re.search(
            r'\b(?:geometry|geography)\s*\(\s*"?(?:multi)?polygon(?:zm|z|m)?"?\s*[,)]',
            statements,
            re.IGNORECASE,
        )
    ):
        defects.append(
            "Reference data contains only linear WKT geometries, but SQL constrains geometry to polygons. Preserve source geometry instead of inventing polygon boundaries."
        )
    return defects
