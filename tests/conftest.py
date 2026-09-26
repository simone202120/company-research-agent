"""Shared fixtures: fake LLM, fake search and a runner over an in-memory checkpointer."""

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from company_research_agent.core.graph import build_graph
from company_research_agent.core.runner import ResearchRunner
from tests.fakes import FakeLLM, FakeSearch


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def fake_search() -> FakeSearch:
    return FakeSearch()


@pytest.fixture
def runner(fake_llm: FakeLLM, fake_search: FakeSearch) -> ResearchRunner:
    return ResearchRunner(build_graph(fake_llm, fake_search, InMemorySaver(), max_revisions=1))
