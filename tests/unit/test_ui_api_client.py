from typing import Any

import httpx
import pytest

from company_research_agent.ui import api_client
from company_research_agent.ui.api_client import ApiError, ResearchApi


def respond(monkeypatch: pytest.MonkeyPatch, status: int, body: Any = None) -> list[tuple]:
    calls: list[tuple] = []

    def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
        calls.append((method, url, kwargs.get("json")))
        return httpx.Response(status, json=body or {}, request=httpx.Request(method, url))

    monkeypatch.setattr(api_client.httpx, "request", request)
    return calls


def test_start_posts_company(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = respond(monkeypatch, 201, {"thread_id": "t", "plan": ["q"]})
    assert ResearchApi("http://api").start("Acme") == {"thread_id": "t", "plan": ["q"]}
    assert calls == [("POST", "http://api/research", {"company": "Acme"})]


def test_approve_and_get_use_thread_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = respond(monkeypatch, 200, {"status": "running"})
    api = ResearchApi("http://api")
    api.approve("t", ["q"])
    api.get("t")
    assert calls == [
        ("POST", "http://api/research/t/approve", {"plan": ["q"]}),
        ("GET", "http://api/research/t", None),
    ]


@pytest.mark.parametrize(
    ("status", "message"),
    [(404, "no longer exists"), (409, "already approved"), (422, "invalid"), (500, "HTTP 500")],
)
def test_http_errors_become_friendly_messages(
    monkeypatch: pytest.MonkeyPatch, status: int, message: str
) -> None:
    respond(monkeypatch, status)
    with pytest.raises(ApiError, match=message):
        ResearchApi("http://api").get("t")


def test_unreachable_api_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def request(method: str, url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(api_client.httpx, "request", request)
    api = ResearchApi("http://api")
    assert api.healthy() is False
    with pytest.raises(ApiError, match="Cannot reach"):
        api.start("Acme")


def test_healthy_when_health_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    respond(monkeypatch, 200, {"status": "ok"})
    assert ResearchApi("http://api").healthy() is True
