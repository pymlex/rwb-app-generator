import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

from generator.config import Settings


STAGE_OUTPUT_CAPS = {
    "analysis": 6000,
    "architecture": 6000,
    "backend": 14000,
    "frontend": 8192,
    "backend-models": 8000,
    "backend-service": 10000,
    "backend-routes": 6000,
    "backend-review": 4000,
    "frontend-logic": 8000,
    "frontend-view": 9000,
    "tests": 6000,
    "documentation-system": 12000,
    "documentation-handover": 8000,
}


@dataclass(frozen=True)
class Budget:
    proxy_input_estimate: int
    tokenizer_input_estimate: int
    output_cap: int
    reservation: int
    context_estimate: int
    counter_source: str


def plan_budget(
    client: httpx.Client,
    settings: Settings,
    stage: str,
    messages: list[dict[str, str]],
) -> Budget:
    proxy_input = (sum(len(message["content"]) for message in messages) + 3) // 4 + 1
    counter_url = settings.base_url.removesuffix("/v1") + "/utils/token_counter"
    counted = client.post(
        counter_url,
        headers={"Authorization": f"Bearer {settings.api_key}"},
        json={"model": settings.model, "messages": messages},
    )
    counted.raise_for_status()
    result = counted.json()
    if result.get("error"):
        raise ValueError(f"Token counter rejected the request: {result.get('error_message')}")
    tokenizer_input = result["total_tokens"]
    matching = [name for name in STAGE_OUTPUT_CAPS if stage == name or stage.startswith(name + "-")]
    cap = STAGE_OUTPUT_CAPS[max(matching, key=len)] if matching else 9000
    desired = min(settings.max_output_tokens, cap)
    available = min(
        settings.tpm_limit - proxy_input - settings.token_margin,
        settings.context_limit - tokenizer_input - settings.token_margin,
    )
    minimum = (
        4096 if stage.startswith("documentation") or stage in {"backend", "frontend"} else 2048
    )
    if available < minimum:
        raise ValueError(
            f"Stage {stage} needs a smaller context or smaller artifact batch: "
            f"proxy_input={proxy_input}, tokenizer_input={tokenizer_input}, "
            f"available_output={available}, minimum_output={minimum}"
        )
    output = min(desired, available)
    return Budget(
        proxy_input_estimate=proxy_input,
        tokenizer_input_estimate=tokenizer_input,
        output_cap=output,
        reservation=proxy_input + output,
        context_estimate=tokenizer_input + output,
        counter_source=result.get("count_source") or "unspecified",
    )


def retry_delay(response: httpx.Response, budget: Budget) -> float | None:
    if response.status_code not in {429, 502, 503}:
        return None
    text = response.text
    limits = re.search(r"Limit type: tokens\. Current limit: (\d+), Remaining: (\d+)", text)
    if limits:
        limit, remaining = map(int, limits.groups())
        if budget.reservation > limit or remaining >= limit:
            return None
    header = response.headers.get("Retry-After", "")
    if header.isdecimal():
        return min(60, int(header) + 1)
    if header:
        reset = parsedate_to_datetime(header)
    else:
        match = re.search(r"Limit resets at: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) UTC", text)
        if not limits or match is None:
            return None
        reset = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    date = response.headers.get("Date")
    now = parsedate_to_datetime(date) if date else datetime.now(UTC)
    return min(60, max(1, (reset - now).total_seconds() + 1))
