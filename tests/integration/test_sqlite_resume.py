from pathlib import Path

import pytest

from company_research_agent.core.graph import build_graph
from company_research_agent.core.runner import ResearchRunner, ResearchStatus
from company_research_agent.infra.checkpointer import sqlite_checkpointer
from tests.fakes import FakeLLM, FakeSearch

pytestmark = pytest.mark.integration


def test_research_resumes_after_restart(tmp_path: Path) -> None:
    db = str(tmp_path / "checkpoints.sqlite")
    with sqlite_checkpointer(db) as saver:
        first = ResearchRunner(build_graph(FakeLLM(), FakeSearch(), saver, max_revisions=1))
        thread_id = first.start("Acme").thread_id

    with sqlite_checkpointer(db) as saver:
        search = FakeSearch()
        second = ResearchRunner(build_graph(FakeLLM(), search, saver, max_revisions=1))
        assert second.get(thread_id).status is ResearchStatus.AWAITING_APPROVAL
        second.approve(thread_id)
        second.resume(thread_id, ["Acme revenue?"])

    with sqlite_checkpointer(db) as saver:
        view = ResearchRunner(build_graph(FakeLLM(), FakeSearch(), saver, 1)).get(thread_id)
    assert view.status is ResearchStatus.DONE
    assert search.queries == ["Acme revenue?"]
    assert view.report is not None
    assert "## Sources" in view.report


def test_failed_research_is_reported_after_restart(tmp_path: Path) -> None:
    db = str(tmp_path / "checkpoints.sqlite")
    with sqlite_checkpointer(db) as saver:
        runner = ResearchRunner(build_graph(FakeLLM(), FakeSearch(fail=True), saver, 1))
        thread_id = runner.start("Acme").thread_id
        runner.approve(thread_id)
        with pytest.raises(RuntimeError):
            runner.resume(thread_id, None)

    with sqlite_checkpointer(db) as saver:
        view = ResearchRunner(build_graph(FakeLLM(), FakeSearch(), saver, 1)).get(thread_id)
    assert view.status is ResearchStatus.FAILED
    assert view.error is not None
