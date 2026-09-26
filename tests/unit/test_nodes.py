import pytest

from company_research_agent.core.errors import InvalidLLMOutputError
from company_research_agent.core.nodes import (
    MAX_QUESTIONS,
    ResearchNodes,
    ReviewVerdict,
    route_after_review,
    route_to_researchers,
    search_query,
)
from company_research_agent.core.state import Finding, ResearchState
from tests.fakes import REPORT, FakeLLM, FakeSearch


def nodes(llm: FakeLLM, search: FakeSearch | None = None, max_revisions: int = 1) -> ResearchNodes:
    return ResearchNodes(llm, search or FakeSearch(), max_revisions)


def written_state(llm: FakeLLM, revision_count: int = 0) -> ResearchState:
    n = nodes(llm)
    findings = n.researcher({"company": "Acme", "question": "What does Acme do?"})["findings"]
    state: ResearchState = {
        "company": "Acme",
        "plan": ["What does Acme do?"],
        "findings": findings,
        "revision_count": revision_count,
    }
    return {**state, **n.writer(state)}


def test_planner_returns_plan_and_resets_flags(fake_llm: FakeLLM) -> None:
    update = nodes(fake_llm).planner({"company": "Acme"})
    assert update == {"plan": fake_llm.plan, "approved": False, "revision_count": 0}


def test_planner_trims_blank_and_extra_questions() -> None:
    llm = FakeLLM(plan=[" ", *[f"q{i} " for i in range(10)]])
    assert nodes(llm).planner({"company": "Acme"})["plan"] == [
        f"q{i}" for i in range(MAX_QUESTIONS)
    ]


def test_planner_without_questions_raises() -> None:
    with pytest.raises(InvalidLLMOutputError):
        nodes(FakeLLM(plan=["  "])).planner({"company": "Acme"})


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("What does acme sell?", "What does acme sell?"),
        ("Who are the CEOs?", "Acme: Who are the CEOs?"),
    ],
)
def test_search_query_adds_company_only_when_missing(question: str, expected: str) -> None:
    assert search_query("Acme", question) == expected


def test_researcher_summarizes_search_results(fake_llm: FakeLLM, fake_search: FakeSearch) -> None:
    update = nodes(fake_llm, fake_search).researcher({"company": "Acme", "question": "Who?"})
    [finding] = update["findings"]
    assert fake_search.queries == ["Acme: Who?"]
    assert finding["summary"] == fake_llm.summary
    assert len(finding["results"]) == 2


def test_researcher_without_results_skips_summary(fake_llm: FakeLLM) -> None:
    class EmptySearch(FakeSearch):
        def __call__(self, query: str) -> list:  # type: ignore[type-arg]
            return []

    update = nodes(fake_llm, EmptySearch()).researcher({"company": "Acme", "question": "Who?"})
    assert update["findings"] == [{"question": "Who?", "summary": "", "results": []}]


def test_writer_numbers_sources_and_remaps_summary_citations(fake_llm: FakeLLM) -> None:
    n = nodes(fake_llm)
    findings: list[Finding] = [
        *n.researcher({"company": "Acme", "question": "What does Acme do?"})["findings"],
        *n.researcher({"company": "Acme", "question": "Acme news?"})["findings"],
    ]
    update = n.writer({"company": "Acme", "plan": [], "findings": findings})
    assert [s["number"] for s in update["sources"]] == [1, 2, 3]
    assert update["draft_report"] == REPORT
    assert update["revision_count"] == 0
    # The second finding's local [1][2] map to the shared source 1 and its own source 3.
    assert "Acme builds rockets [1] and anvils [3]." in fake_llm.writer_prompts[0]


def test_writer_revision_includes_feedback_and_counts(fake_llm: FakeLLM) -> None:
    state = written_state(fake_llm)
    state["review_feedback"] = "Add competitors."
    update = nodes(fake_llm).writer(state)
    assert update["revision_count"] == 1
    assert "Add competitors." in fake_llm.writer_prompts[-1]
    assert "<previous_draft>" in fake_llm.writer_prompts[-1]


def test_reviewer_ok_finalizes_report(fake_llm: FakeLLM) -> None:
    update = nodes(fake_llm).reviewer(written_state(fake_llm))
    assert update["review_feedback"] == ""
    assert "## Sources" in update["final_report"]


def test_reviewer_revise_requests_revision_below_max() -> None:
    llm = FakeLLM(verdicts=[ReviewVerdict(verdict="revise", feedback="Too short.")])
    update = nodes(llm).reviewer(written_state(llm))
    assert update == {"review_feedback": "Too short."}


def test_reviewer_revise_at_max_revisions_finalizes() -> None:
    llm = FakeLLM(verdicts=[ReviewVerdict(verdict="revise", feedback="Too short.")])
    update = nodes(llm).reviewer(written_state(llm, revision_count=1))
    assert "final_report" in update


def test_reviewer_forces_revision_on_invalid_citations() -> None:
    llm = FakeLLM(report="# Acme\n\nFact [7].")
    update = nodes(llm).reviewer(written_state(llm))
    assert "[7]" in update["review_feedback"]
    assert "final_report" not in update


def test_reviewer_strips_invalid_citations_when_out_of_revisions() -> None:
    llm = FakeLLM(report="# Acme\n\nFact [7].")
    update = nodes(llm, max_revisions=0).reviewer(written_state(llm))
    assert "[7]" not in update["final_report"]


def test_route_to_researchers_sends_one_task_per_question() -> None:
    sends = route_to_researchers({"company": "Acme", "plan": ["a", "b"]})
    assert [(s.node, s.arg) for s in sends] == [
        ("researcher", {"company": "Acme", "question": "a"}),
        ("researcher", {"company": "Acme", "question": "b"}),
    ]


def test_route_after_review() -> None:
    assert route_after_review({"final_report": "x"}) == "__end__"
    assert route_after_review({"review_feedback": "fix"}) == "writer"
