"""Deterministic Markdown views of verification evidence, without executing checks."""

import json
from pathlib import Path

from generator.models import Check


def cell(value: object) -> str:
    return (
        str(value)
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def load_json(root: Path, name: str, default):
    path = root / "reports" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def overall(statuses: list[str]) -> str:
    if "failed" in statuses:
        return "failed"
    return "passed" if statuses and all(item == "passed" for item in statuses) else "not_run"


def write_reports(root: Path, checks: list[Check] | None = None) -> None:
    entries = (
        [check.model_dump() for check in checks]
        if checks is not None
        else load_json(root, "checks.json", [])
    )
    entries = sorted(entries, key=lambda item: item["name"])
    summary = load_json(root, "summary.json", {})
    test_lines = [
        "# Test report",
        "",
        f"Check status: {overall([item['status'] for item in entries])}",
        f"Release status: {summary.get('status', 'unverified')}",
        "",
        "## Executed checks",
        "",
        "| Check | Command | Status | Exit | Seconds | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in entries:
        test_lines.append(
            "| "
            + " | ".join(
                cell(value)
                for value in [
                    item["name"],
                    " ".join(item.get("command", [])) or "structural inspection",
                    item["status"],
                    item.get("exit_code"),
                    item.get("duration_seconds", 0),
                    "reports/checks.json: " + item["name"],
                ]
            )
            + " |"
        )
    test_lines += ["", "## Defects and severity", ""]
    failures = [item for item in entries if item["status"] == "failed"]
    test_lines += [
        f"- HIGH: {cell(item['name'])} failed (exit {item.get('exit_code')}); see reports/checks.json and reports/{cell(item['name'])}.json."
        for item in failures
    ] or ["- No failed checks recorded. Missing execution is not evidence of success."]
    for name in ["requirement-tests.json", "traceability.json", "requirement-review.json"]:
        test_lines += ["", f"## {name}", ""]
        records = load_json(root, name, [])
        for item in sorted(
            records, key=lambda value: (value.get("requirement_id", ""), value.get("name", ""))
        ):
            test_lines.append(
                f"- {cell(item.get('requirement_id', ''))} {cell(item.get('name', ''))}: {cell(item.get('status', 'unverified'))}; evidence: reports/{name}."
            )
        if not records:
            test_lines.append("No evidence recorded; unverified.")

    findings = []
    scan_statuses = []
    scan_sources = []
    security = load_json(root, "security.json", None)
    if security is not None:
        scan_sources.append("reports/security.json (Trivy vulnerabilities and secrets)")
        if not isinstance(security, dict) or not isinstance(security.get("Results"), list):
            scan_statuses.append("not_run")
        else:
            scan_statuses.append("passed")
            for target in security["Results"]:
                for key in ["Vulnerabilities", "Secrets"]:
                    for finding in target.get(key) or []:
                        findings.append(
                            (
                                finding.get("Severity", "UNKNOWN").upper(),
                                finding.get("VulnerabilityID") or finding.get("RuleID", "unknown"),
                                target.get("Target", "unknown"),
                                "reports/security.json",
                            )
                        )
    sast = load_json(root, "sast.json", None)
    if sast is not None:
        scan_sources.append("reports/sast.json (SAST)")
        valid = isinstance(sast, dict) and isinstance(sast.get("results"), list)
        scan_statuses.append(
            "failed" if valid and sast.get("errors") else "passed" if valid else "not_run"
        )
        if valid:
            for finding in sast["results"]:
                findings.append(
                    (
                        finding.get("extra", {}).get("severity", "UNKNOWN").upper(),
                        finding.get("check_id", "unknown"),
                        finding.get("path", "unknown"),
                        "reports/sast.json",
                    )
                )
    security_checks = [
        item
        for item in entries
        if any(word in item["name"] for word in ("audit", "sast", "security"))
    ]
    statuses = scan_statuses + [item["status"] for item in security_checks]
    if security is None:
        statuses.append("not_run")
    if any(item[0] in {"HIGH", "CRITICAL", "ERROR"} for item in findings):
        statuses.append("failed")
    security_lines = [
        "# Security report",
        "",
        f"Overall status: {overall(statuses)}",
        "",
        "HIGH/CRITICAL Trivy findings and ERROR SAST findings block release.",
        "",
        "## Executed scans",
        "",
    ]
    security_lines += [f"- {source}" for source in scan_sources] or [
        "- No scanner JSON recorded; not_run."
    ]
    security_lines += [
        f"- {cell(item['name'])}: {item['status']}; evidence: reports/checks.json."
        for item in security_checks
    ]
    security_lines += [
        "",
        "## Defects and severity",
        "",
        "| Severity | Finding | Target | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    security_lines += ["| " + " | ".join(map(cell, finding)) + " |" for finding in sorted(findings)]
    if not findings:
        security_lines += ["", "No findings recorded. A missing scan is not a clean scan."]
    security_lines += ["", "## Severity totals", ""]
    security_lines += [
        f"- {severity}: {sum(item[0] == severity for item in findings)}"
        for severity in sorted({item[0] for item in findings})
    ]
    docs = root / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "test-report.md").write_text("\n".join(test_lines) + "\n", encoding="utf-8")
    (docs / "security-report.md").write_text("\n".join(security_lines) + "\n", encoding="utf-8")
