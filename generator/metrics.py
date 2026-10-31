"""Aggregate recorded pipeline events; never copy prompts, responses or credentials."""

import json
from datetime import datetime
from pathlib import Path

from generator.models import Check
from generator.reports import cell, load_json, overall
from generator.storage import digest, write_json


def stage_metrics(events: list[dict]) -> dict:
    completed = [item for item in events if item["kind"] == "model_completed"]
    attempts = [item for item in events if item["kind"] == "model_http_attempt"]
    reasoning = [
        (item.get("usage") or {}).get("completion_tokens_details") or {} for item in completed
    ]
    reasoning_values = [
        item["reasoning_tokens"] for item in reasoning if item.get("reasoning_tokens") is not None
    ]
    return {
        "model_calls": len(completed),
        "model_calls_started": sum(item["kind"] == "model_started" for item in events),
        "http_attempts": len(attempts)
        + sum(item["kind"] == "model_started" and not item.get("http_tracking") for item in events),
        "http_retries": sum(item.get("attempt", 1) > 1 for item in attempts),
        "http_failures": sum(item["kind"] == "model_http_failure" for item in events),
        "repairs": sum(item["kind"] == "repair_started" for item in events),
        "cache_hits": sum(item["kind"] == "cache_hit" for item in events),
        "artifact_reuses": sum(
            item["kind"] in {"artifact_reused", "analysis_reused"} for item in events
        ),
        "input_tokens": sum(
            (item.get("usage") or {}).get("prompt_tokens", 0) or 0 for item in completed
        ),
        "output_tokens": sum(
            (item.get("usage") or {}).get("completion_tokens", 0) or 0 for item in completed
        ),
        "total_tokens": sum(
            (item.get("usage") or {}).get("total_tokens", 0) or 0 for item in completed
        ),
        "reasoning_tokens": sum(reasoning_values) if reasoning_values else None,
        "reasoning_calls_reported": len(reasoning_values),
        "model_seconds": round(sum(item.get("duration_seconds", 0) or 0 for item in completed), 3),
        "wait_seconds": round(
            sum(
                item.get("seconds", 0) or 0
                for item in events
                if item["kind"] in {"rate_window_wait", "admission_window_wait"}
            ),
            3,
        ),
    }


def write_metrics(
    root: Path,
    checks: list[Check] | None = None,
    status: str | None = None,
    elapsed: float | None = None,
) -> dict:
    path = root / ".pipeline/events.jsonl"
    events = (
        [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if path.is_file()
        else []
    )
    starts = [item for item in events if item["kind"] == "run_started"]
    identity_path = root / ".pipeline/input.sha256"
    identity = (
        identity_path.read_text(encoding="utf-8").strip()
        if identity_path.is_file()
        else (starts[0].get("input_sha256") if starts else None)
    )
    run_id = digest(f"{identity}|{starts[0]['time']}") if starts else None
    stages = sorted({item["stage"] for item in events if item.get("stage")})
    entries = (
        [item.model_dump() for item in checks]
        if checks is not None
        else load_json(root, "checks.json", [])
    )
    check_statuses = {item["name"]: item["status"] for item in entries}
    summary = load_json(root, "summary.json", {})
    span = (
        (
            datetime.fromisoformat(events[-1]["time"]) - datetime.fromisoformat(events[0]["time"])
        ).total_seconds()
        if events
        else 0
    )
    result = {
        "schema_version": 1,
        "run_id": run_id,
        "input_sha256": identity,
        "invocations": len(starts),
        "status": status or summary.get("status", "in_progress" if events else "not_run"),
        "totals": stage_metrics(events),
        "stages": {
            stage: stage_metrics([item for item in events if item.get("stage") == stage])
            for stage in stages
        },
        "durations": {
            "reported_seconds": round(elapsed, 3)
            if elapsed is not None
            else summary.get("duration_seconds"),
            "observed_event_span_seconds": round(max(0, span), 3),
            "check_seconds": round(sum(item.get("duration_seconds", 0) for item in entries), 3),
        },
        "outcomes": {
            "build": check_statuses.get("build", "not_run"),
            "test": overall(
                [check_statuses.get(name, "not_run") for name in ["unit", "acceptance"]]
            ),
            "deploy": check_statuses.get("deployment", "not_run"),
        },
        "checks": dict(sorted(check_statuses.items())),
    }
    destination = root / "pipeline-metrics"
    write_json(destination / "summary.json", result)
    lines = [
        "# Pipeline metrics",
        "",
        f"Run ID: {run_id or 'unavailable'}",
        f"Status: {result['status']}",
        f"Invocations: {len(starts)}",
        "",
        "Counts cover all invocations in this output directory. Output tokens include reasoning tokens when reported; reasoning is not added twice. Missing reasoning usage is unavailable, not zero.",
        "",
        "## Totals",
        "",
    ]
    lines += [
        f"- {name}: {value if value is not None else 'unavailable'}"
        for name, value in result["totals"].items()
    ]
    lines += [
        "",
        "## Model stages",
        "",
        "| Stage | Calls | HTTP attempts | HTTP retries | Cache hits | Repairs | Input | Output | Reasoning | Model seconds |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for stage, metrics in result["stages"].items():
        values = [
            stage,
            *[
                metrics[key]
                for key in [
                    "model_calls",
                    "http_attempts",
                    "http_retries",
                    "cache_hits",
                    "repairs",
                    "input_tokens",
                    "output_tokens",
                    "reasoning_tokens",
                    "model_seconds",
                ]
            ],
        ]
        lines.append(
            "| "
            + " | ".join(cell(value) if value is not None else "unavailable" for value in values)
            + " |"
        )
    for title, values in [
        ("Durations", result["durations"]),
        ("Outcomes", result["outcomes"]),
        ("Checks", result["checks"]),
    ]:
        lines += ["", f"## {title}", ""]
        lines += [f"- {cell(key)}: {cell(value)}" for key, value in values.items()]
    (destination / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result
