import pytest
from langgraph.checkpoint.memory import InMemorySaver

from company_research_agent.core.errors import (
    InvalidResearchStateError,
    ResearchNotFoundError,
)
from company_research_agent.core.graph import build_graph
from company_research_agent.core.nodes import MAX_QUESTIONS, ReviewVerdict
from company_research_agent.core.runner import ResearchRunner, ResearchStatus
from tests.fakes import FakeLLM, FakeSearch


def test_start_stops_at_approval_with_plan(runner: ResearchRunner, fake_llm: FakeLLM) -> None:
    view = runner.start("Acme")
    assert view.status is ResearchStatus.AWAITING_APPROVAL
    assert view.plan == fake_llm.plan
    assert view.current_node == "human_approval"
    assert view.report is None


def test_resume_with_edited_plan_researches_edited_questions(
    runner: ResearchRunner, fake_search: FakeSearch
) -> None:
    thread_id = runner.start("Acme").thread_id
    runner.approve(thread_id)
    runner.resume(thread_id, ["Acme revenue?", "  ", "Acme founders?"])
    view = runner.get(thread_id)
    assert view.status is ResearchStatus.DONE
    assert view.plan == ["Acme revenue?", "Acme founders?"]
    assert sorted(fake_search.queries) == ["Acme founders?", "Acme revenue?"]
    assert view.report is not None
    assert "## Sources" in view.report
    assert [s["number"] for s in view.sources] == [1, 2, 3]
    assert view.current_node is None


def test_resume_without_plan_keeps_generated_plan(
    runner: ResearchRunner, fake_llm: FakeLLM, fake_search: FakeSearch
) -> None:
    thread_id = runner.start("Acme").thread_id
    runner.approve(thread_id)
    runner.resume(thread_id, None)
    assert runner.get(thread_id).plan == fake_llm.plan
    assert len(fake_search.queries) == len(fake_llm.plan)


def test_approved_thread_reports_running_until_resumed(runner: ResearchRunner) -> None:
    thread_id = runner.start("Acme").thread_id
    runner.approve(thread_id)
    assert runner.get(thread_id).status is ResearchStatus.RUNNING
    with pytest.raises(InvalidResearchStateError):
        runner.approve(thread_id)


def test_approve_done_thread_is_rejected(runner: ResearchRunner) -> None:
    thread_id = runner.start("Acme").thread_id
    runner.approve(thread_id)
    runner.resume(thread_id, None)
    with pytest.raises(InvalidResearchStateError):
        runner.approve(thread_id)


def test_unknown_thread_raises_not_found(runner: ResearchRunner) -> None:
    with pytest.raises(ResearchNotFoundError):
        runner.get("missing")
    with pytest.raises(ResearchNotFoundError):
        runner.approve("missing")


@pytest.mark.parametrize("max_revisions", [0, 1, 2])
def test_revision_loop_stops_at_max_revisions(max_revisions: int) -> None:
    llm = FakeLLM(verdicts=[ReviewVerdict(verdict="revise", feedback="More.")] * 5)
    runner = ResearchRunner(build_graph(llm, FakeSearch(), InMemorySaver(), max_revisions))
    thread_id = runner.start("Acme").thread_id
    runner.approve(thread_id)
    runner.resume(thread_id, None)
    assert runner.get(thread_id).status is ResearchStatus.DONE
    assert len(llm.writer_prompts) == max_revisions + 1


def test_failed_node_marks_research_failed(fake_llm: FakeLLM) -> None:
    runner = ResearchRunner(build_graph(fake_llm, FakeSearch(fail=True), InMemorySaver(), 1))
    thread_id = runner.start("Acme").thread_id
    runner.approve(thread_id)
    with pytest.raises(RuntimeError, match="search is down"):
        runner.resume(thread_id, None)
    view = runner.get(thread_id)
    assert view.status is ResearchStatus.FAILED
    assert view.error is not None
    assert "search is down" in view.error
    assert view.current_node == "researcher"


def test_resume_caps_oversized_edited_plan(runner: ResearchRunner) -> None:
    thread_id = runner.start("Acme").thread_id
    runner.approve(thread_id)
    runner.resume(thread_id, [f"Acme question {i}?" for i in range(50)])
    assert len(runner.get(thread_id).plan) == MAX_QUESTIONS
