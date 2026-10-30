import httpx
import pytest

from generator.budget import Budget, plan_budget, retry_delay
from generator.config import Settings


def test_original_frontend_size_gets_an_admissible_stage_cap():
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"total_tokens": 21388, "count_source": "local_estimate"}
            )
        )
    ) as client:
        budget = plan_budget(
            client,
            Settings("http://model/v1", "test-key"),
            "frontend",
            [{"role": "user", "content": "x" * 80050}],
        )
    assert budget.output_cap == 8192
    assert budget.reservation + 512 <= 30000
    assert budget.context_estimate + 512 <= 32768


def test_request_too_large_for_a_complete_artifact_is_rejected_before_generation():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"total_tokens": 31000, "count_source": "local_estimate"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match="smaller context"):
            plan_budget(
                client,
                Settings("http://model/v1", "test-key"),
                "frontend",
                [{"role": "user", "content": "x" * 120000}],
            )
    assert calls == ["/utils/token_counter"]


@pytest.mark.parametrize("remaining", [30000, 29999])
def test_oversized_reservation_is_not_retried_after_a_reset(remaining):
    budget = Budget(20013, 21388, 14000, 34013, 35388, "local_estimate")
    response = httpx.Response(
        429,
        headers={"Retry-After": "60"},
        text=f"Limit type: tokens. Current limit: 30000, Remaining: {remaining}",
    )
    assert retry_delay(response, budget) is None


def test_full_window_rejection_requires_diagnosis_instead_of_sleep():
    budget = Budget(5000, 6000, 8000, 13000, 14000, "local_estimate")
    response = httpx.Response(
        429,
        headers={"Retry-After": "60"},
        text="Limit type: tokens. Current limit: 30000, Remaining: 30000",
    )
    assert retry_delay(response, budget) is None


def test_temporary_shortage_uses_server_reset_time_and_server_clock():
    budget = Budget(5000, 6000, 8000, 13000, 14000, "local_estimate")
    response = httpx.Response(
        429,
        headers={"Date": "Fri, 30 Oct 2026 18:39:40 GMT"},
        text="Limit type: tokens. Current limit: 30000, Remaining: 1000. Limit resets at: 2026-10-30 18:40:00 UTC",
    )
    assert retry_delay(response, budget) == 21


def test_unclassified_failure_is_not_blindly_retried():
    budget = Budget(5000, 6000, 8000, 13000, 14000, "local_estimate")
    assert retry_delay(httpx.Response(429, text="unknown limit"), budget) is None
    assert retry_delay(httpx.Response(503, text="backend unavailable"), budget) is None
