from typing import Any

import pytest

from company_research_agent.config import Settings
from company_research_agent.core.errors import SearchError
from company_research_agent.core.state import SearchResult
from company_research_agent.infra import search
from company_research_agent.infra.search import (
    TAVILY_MAX_QUERY_CHARS,
    DuckDuckGoSearch,
    FallbackSearch,
    TavilySearch,
    create_search,
)

RESULT: SearchResult = {"title": "t", "url": "https://a.test", "snippet": "s"}


class FakeTavilyClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, max_results: int) -> dict[str, Any]:
        self.calls.append((query, max_results))
        return {
            "results": [
                {"title": "Acme", "url": "https://acme.test", "content": "About Acme"},
                {"title": "No url", "url": "", "content": "dropped"},
            ]
        }


def provider(results: list[SearchResult] | None = None, fail: bool = False) -> Any:
    def call(query: str) -> list[SearchResult]:
        if fail:
            raise RuntimeError("down")
        return results or []

    return call


def test_tavily_maps_results_and_truncates_query() -> None:
    client = FakeTavilyClient()
    results = TavilySearch(client, max_results=3)("q" * 1000)  # type: ignore[arg-type]
    assert results == [{"title": "Acme", "url": "https://acme.test", "snippet": "About Acme"}]
    assert client.calls == [("q" * TAVILY_MAX_QUERY_CHARS, 3)]


def test_duckduckgo_maps_results(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeDDGS:
        def text(self, query: str, max_results: int) -> list[dict[str, str]]:
            return [{"title": "Acme", "href": "https://acme.test", "body": "About"}, {"title": "x"}]

    monkeypatch.setattr(search, "DDGS", FakeDDGS)
    assert DuckDuckGoSearch(max_results=5)("acme") == [
        {"title": "Acme", "url": "https://acme.test", "snippet": "About"}
    ]


def test_fallback_uses_first_provider_with_results() -> None:
    assert FallbackSearch([provider([RESULT]), provider(fail=True)])("q") == [RESULT]


def test_fallback_moves_on_after_failure_or_empty_results() -> None:
    assert FallbackSearch([provider(fail=True), provider([]), provider([RESULT])])("q") == [RESULT]


def test_fallback_returns_empty_when_a_provider_answered_empty() -> None:
    assert FallbackSearch([provider(fail=True), provider([])])("q") == []


def test_fallback_raises_when_every_provider_fails() -> None:
    with pytest.raises(SearchError):
        FallbackSearch([provider(fail=True), provider(fail=True)])("q")


def test_fallback_without_providers_returns_empty() -> None:
    assert FallbackSearch([])("q") == []


def test_create_search_uses_tavily_only_with_key() -> None:
    with_key = create_search(Settings(_env_file=None, tavily_api_key="tvly-test"))
    without_key = create_search(Settings(_env_file=None, tavily_api_key=""))
    assert isinstance(with_key, FallbackSearch)
    assert isinstance(without_key, FallbackSearch)
    assert [type(p) for p in with_key.providers] == [TavilySearch, DuckDuckGoSearch]
    assert [type(p) for p in without_key.providers] == [DuckDuckGoSearch]
