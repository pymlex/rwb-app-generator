import json

import httpx
import pytest

from generator.config import Settings
from generator.llm import Qwen
from generator.models import ArtifactBatch


def install_transport(monkeypatch, handler):
    client_type = httpx.Client

    def dispatch(request):
        if request.url.path == "/utils/token_counter":
            messages = json.loads(request.content)["messages"]
            return httpx.Response(
                200,
                json={
                    "total_tokens": sum(len(item["content"]) for item in messages) // 4 + 20,
                    "error": False,
                    "count_source": "local_estimate",
                },
            )
        return handler(request)

    transport = httpx.MockTransport(dispatch)
    monkeypatch.setattr(
        "generator.llm.httpx.Client", lambda **kwargs: client_type(transport=transport, **kwargs)
    )


def test_environment_proxy_and_redirects_are_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:3128")
    monkeypatch.setenv("ALL_PROXY", "http://proxy.invalid:3128")
    monkeypatch.setenv("NO_PROXY", "")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://redirect.invalid/"})

    client_type = httpx.Client
    clients = []

    def make_client(**kwargs):
        client = client_type(transport=httpx.MockTransport(handler), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr("generator.llm.httpx.Client", make_client)
    with pytest.raises(httpx.HTTPStatusError):
        Qwen(Settings("https://model.invalid/v1", "dummy-key"), tmp_path).generate(
            "docs", "Write", "input", ArtifactBatch
        )
    assert clients
    assert clients[0]._mounts == {}
    assert clients[0].follow_redirects is False
    assert requests
    assert all(request.url.host == "model.invalid" for request in requests)


def test_resume_does_not_pay_for_an_identical_completed_stage(tmp_path, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request)
        payload = {
            "files": [{"path": "docs/api.md", "content": "Contract", "requirement_ids": ["FR-001"]}]
        }
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 12, "total_tokens": 23},
            },
        )

    install_transport(monkeypatch, handler)
    client = Qwen(Settings("http://model/v1", "test-sensitive-key"), tmp_path)
    first = client.generate("docs", "Write contract", "requirements", ArtifactBatch)
    second = client.generate("docs", "Write contract", "requirements", ArtifactBatch)
    assert first == second
    assert len(calls) == 1
    assert calls[0].url.path == "/v1/chat/completions"
    events = (tmp_path / "events.jsonl").read_text()
    assert "test-sensitive-key" not in events
    assert sum(json.loads(line)["kind"] == "model_completed" for line in events.splitlines()) == 1


def test_truncated_generation_keeps_evidence_but_cannot_be_cached_as_complete(
    tmp_path, monkeypatch
):
    install_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{broken"}, "finish_reason": "length"}],
                "usage": {"total_tokens": 100},
            },
        ),
    )
    client = Qwen(Settings("http://model/v1", "test-sensitive-key"), tmp_path)
    with pytest.raises(ValueError, match="token budget"):
        client.generate("backend", "Generate", "requirements", ArtifactBatch)
    assert len(list((tmp_path / "responses").glob("*.json"))) == 1
    assert not (tmp_path / "checkpoints").exists()


def test_rate_limited_request_waits_and_preserves_attempt_counts(tmp_path, monkeypatch):
    calls = []
    waits = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "3"}, json={"error": "busy"})
        payload = {"files": [{"path": "docs/api.md", "content": "Contract", "requirement_ids": []}]}
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(payload)}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 40},
            },
        )

    install_transport(monkeypatch, handler)
    monkeypatch.setattr("generator.llm.time.sleep", waits.append)
    Qwen(Settings("http://model/v1", "test-sensitive-key"), tmp_path).generate(
        "docs", "Write", "input", ArtifactBatch
    )
    assert len(calls) == 2
    assert waits == [4]
    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert sum(entry["kind"] == "model_http_attempt" for entry in events) == 2
    assert sum(entry["kind"] == "model_completed" for entry in events) == 1
