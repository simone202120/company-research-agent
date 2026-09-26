import pytest
from langgraph.checkpoint.memory import InMemorySaver

from company_research_agent.config import Settings
from company_research_agent.core.graph import build_graph
from company_research_agent.core.report import invalid_citations
from company_research_agent.core.runner import ResearchRunner, ResearchStatus
from company_research_agent.infra.search import create_search
from company_research_agent.llm.factory import create_llm

pytestmark = pytest.mark.llm


def test_real_research_produces_sourced_report() -> None:
    settings = Settings()
    graph = build_graph(
        create_llm(settings), create_search(settings), InMemorySaver(), settings.max_revisions
    )
    runner = ResearchRunner(graph)
    view = runner.start("Hugging Face")
    assert 4 <= len(view.plan) <= 6
    runner.approve(view.thread_id)
    runner.resume(view.thread_id, None)

    view = runner.get(view.thread_id)
    assert view.status is ResearchStatus.DONE
    assert view.report is not None
    assert view.report.count("\n## ") >= 3
    assert "## Sources" in view.report
    assert len(view.sources) >= 5
    assert invalid_citations(view.report, len(view.sources)) == []
