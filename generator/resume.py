import hashlib
import json
import re
from pathlib import Path

from generator.worker import csharp_members


METHOD_SIGNATURE = (
    r"(?P<signature>Task(?:<[^;{}=]+>)?\s+(?P<name>[A-Za-z_]\w*)\s*\([^;{}()]*\))"
)
TASK_METHOD = re.compile(
    r"^\s*public\s+(?:(?:async|virtual|override|sealed|new|static)\s+)*" + METHOD_SIGNATURE
)
INTERFACE_METHOD = re.compile(
    r"(?m)^\s*(?:public\s+)?" + METHOD_SIGNATURE + r"\s*;"
)


def recover_service_packages(output: Path, interface_source: str) -> list[dict]:
    contract = {
        re.sub(r"\s+", "", match["signature"])
        for match in INTERFACE_METHOD.finditer(interface_source)
    }
    checkpoints = output / ".pipeline" / "checkpoints"
    records = []
    assigned = set()
    candidates = []
    for path in (output / "backend").glob("DomainService.Part*.cs"):
        match = re.fullmatch(r"DomainService\.Part([0-9]+)\.cs", path.name)
        if match:
            candidates.append((int(match[1]), path))
    for number, path in sorted(candidates):
        raw = path.read_bytes()
        source = raw.decode("utf-8")
        methods = []
        unsupported = False
        for member in csharp_members(source):
            body = source[member["start"] : member["end"]]
            declaration = TASK_METHOD.match(body)
            if declaration:
                methods.append(declaration["name"])
                if re.sub(r"\s+", "", declaration["signature"]) not in contract:
                    unsupported = True
            elif re.match(r"\s*public\b[^;{}=]*\(", body):
                unsupported = True
        if unsupported or not methods:
            continue
        artifact = None
        relative = path.relative_to(output).as_posix()
        for checkpoint in sorted(checkpoints.glob("*.json")):
            match = re.fullmatch(r"backend-service-([0-9]+)-turn-.*\.json", checkpoint.name)
            repair = checkpoint.name.startswith(("backend-repair-", "application-repair-"))
            if not repair and (not match or int(match[1]) != number):
                continue
            try:
                saved = json.loads(checkpoint.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(saved, dict):
                continue
            if "kind" in saved and saved["kind"] != "finish":
                continue
            result = saved.get("result") if saved.get("kind") == "finish" else saved
            if not isinstance(result, dict) or not isinstance(result.get("files"), list):
                continue
            for item in result["files"]:
                if (
                    isinstance(item, dict)
                    and item.get("path") == relative
                    and isinstance(item.get("content"), str)
                    and item["content"].rstrip() + "\n" == source
                    and isinstance(item.get("requirement_ids"), list)
                    and all(isinstance(value, str) for value in item["requirement_ids"])
                ):
                    artifact = item
                    break
            if artifact is not None:
                break
        if artifact is None:
            continue
        duplicates = assigned.intersection(methods)
        if duplicates or len(methods) != len(set(methods)):
            raise ValueError(
                f"Recovered service methods are duplicated: {sorted(duplicates or set(methods))}"
            )
        assigned.update(methods)
        records.append(
            {
                "path": relative,
                "methods": methods,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "requirement_ids": artifact["requirement_ids"],
            }
        )
    return sorted(records, key=lambda entry: "Initialise" not in entry["methods"])
