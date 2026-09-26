"""Web search adapters: Tavily when configured, DuckDuckGo as the free fallback."""

import logging

from ddgs import DDGS
from tavily import TavilyClient

from company_research_agent.config import Settings
from company_research_agent.core.errors import SearchError
from company_research_agent.core.nodes import SearchTool
from company_research_agent.core.state import SearchResult

logger = logging.getLogger(__name__)

TAVILY_MAX_QUERY_CHARS = 400


class TavilySearch:
    def __init__(self, client: TavilyClient, max_results: int) -> None:
        self.client = client
        self.max_results = max_results

    def __call__(self, query: str) -> list[SearchResult]:
        response = self.client.search(query[:TAVILY_MAX_QUERY_CHARS], max_results=self.max_results)
        return [
            {"title": r.get("title", ""), "url": r["url"], "snippet": r.get("content", "")}
            for r in response.get("results", [])
            if r.get("url")
        ]


class DuckDuckGoSearch:
    def __init__(self, max_results: int) -> None:
        self.max_results = max_results

    def __call__(self, query: str) -> list[SearchResult]:
        # A fresh client per call: researcher branches search concurrently from several threads.
        hits = DDGS().text(query, max_results=self.max_results)
        return [
            {"title": h.get("title", ""), "url": h["href"], "snippet": h.get("body", "")}
            for h in hits
            if h.get("href")
        ]


class FallbackSearch:
    """Tries providers in order until one returns results; fails only if every provider fails."""

    def __init__(self, providers: list[SearchTool]) -> None:
        self.providers = providers

    def __call__(self, query: str) -> list[SearchResult]:
        errors: list[Exception] = []
        for provider in self.providers:
            try:
                results = provider(query)
            except Exception as exc:
                logger.warning("search provider %s failed", type(provider).__name__, exc_info=True)
                errors.append(exc)
                continue
            if results:
                return results
        if errors and len(errors) == len(self.providers):
            raise SearchError(f"every search provider failed for {query!r}") from errors[-1]
        return []


def create_search(settings: Settings) -> SearchTool:
    providers: list[SearchTool] = []
    api_key = settings.tavily_api_key.get_secret_value()
    if api_key:
        providers.append(TavilySearch(TavilyClient(api_key=api_key), settings.search_max_results))
    providers.append(DuckDuckGoSearch(settings.search_max_results))
    return FallbackSearch(providers)
