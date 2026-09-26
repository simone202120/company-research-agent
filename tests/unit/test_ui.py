from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from company_research_agent.ui import components
from company_research_agent.ui.api_client import ApiError, ResearchApi
from company_research_agent.ui.components import EXAMPLES, edited_plan, report_body, timeline

APP = str(Path(components.__file__).with_name("app.py"))
THREAD = "a" * 32
PLAN = ["What does Acme do?", "Who competes with Acme?"]
DONE: dict[str, Any] = {
    "thread_id": THREAD,
    "company": "Acme",
    "status": "done",
    "current_node": None,
    "plan": PLAN,
    "report": "# Acme\n\nAcme builds rockets [1].",
    "sources": [{"number": 1, "title": "Acme home", "url": "https://acme.test"}],
    "error": None,
    "usage": {
        "llm_calls": 5,
        "input_tokens": 1000,
        "output_tokens": 200,
        "estimated_cost_usd": 0.01,
    },
    "latency_seconds": 12.3,
    "trace_url": "https://langfuse.test/trace",
}


class FakeApi:
    """Replaces ResearchApi methods; `research` is what GET returns."""

    def __init__(self, research: dict[str, Any] | None = None, fail: bool = False) -> None:
        self.research = research
        self.fail = fail
        self.started: list[str] = []
        self.approved: list[list[str]] = []

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake = self

        def healthy(_: ResearchApi) -> bool:
            return not fake.fail

        def start(_: ResearchApi, company: str) -> dict[str, Any]:
            fake.started.append(company)
            fake.research = {
                **DONE,
                "company": company,
                "status": "awaiting_approval",
                "current_node": "human_approval",
                "report": None,
                "sources": [],
                "usage": None,
                "latency_seconds": None,
                "trace_url": None,
            }
            return {"thread_id": THREAD, "plan": PLAN}

        def approve(_: ResearchApi, thread_id: str, plan: list[str]) -> dict[str, Any]:
            fake.approved.append(plan)
            assert fake.research is not None
            fake.research = {**fake.research, "status": "running", "current_node": "researcher"}
            return {"thread_id": thread_id, "status": "running"}

        def get(_: ResearchApi, thread_id: str) -> dict[str, Any]:
            if fake.fail:
                raise ApiError("Cannot reach the research API")
            assert fake.research is not None
            return fake.research

        for name, method in [
            ("healthy", healthy),
            ("start", start),
            ("approve", approve),
            ("get", get),
        ]:
            monkeypatch.setattr(ResearchApi, name, method)


def app_with(monkeypatch: pytest.MonkeyPatch, fake: FakeApi, thread: bool = True) -> AppTest:
    fake.install(monkeypatch)
    at = AppTest.from_file(APP, default_timeout=10)
    if thread:
        at.session_state["thread_id"] = THREAD
    return at.run()


def test_empty_state_offers_examples(monkeypatch: pytest.MonkeyPatch) -> None:
    at = app_with(monkeypatch, FakeApi(), thread=False)
    labels = [b.label for b in at.button]
    assert all(example in labels for example in EXAMPLES)
    assert not at.exception


def test_example_starts_research_and_shows_editable_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeApi()
    at = app_with(monkeypatch, fake, thread=False)
    next(b for b in at.button if b.label == EXAMPLES[0]).click().run()
    assert fake.started == [EXAMPLES[0]]
    assert "Research plan for Hugging Face" in at.subheader[0].value
    assert any(b.label == "Approve plan" for b in at.button)


def test_approve_sends_plan_and_shows_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeApi()
    at = app_with(monkeypatch, fake, thread=False)
    next(b for b in at.button if b.label == EXAMPLES[1]).click().run()
    next(b for b in at.button if b.label == "Approve plan").click().run()
    assert fake.approved == [PLAN]
    assert "Researching Mistral AI" in at.subheader[0].value
    assert not at.exception


def test_done_shows_metrics_report_and_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    at = app_with(monkeypatch, FakeApi(DONE))
    assert "Report on Acme" in at.subheader[0].value
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Sources"] == "1"
    assert metrics["Tokens"] == "1,200"
    assert metrics["Est. cost"] == "$0.0100"
    assert metrics["Latency"] == "12.3 s"
    assert any("Acme builds rockets" in m.value for m in at.markdown)
    assert not at.exception


def test_failed_research_shows_friendly_error(monkeypatch: pytest.MonkeyPatch) -> None:
    failed = {**DONE, "status": "failed", "current_node": "researcher", "error": "SearchError"}
    at = app_with(monkeypatch, FakeApi(failed))
    assert "The research failed" in at.error[0].value


def test_unreachable_api_shows_error(monkeypatch: pytest.MonkeyPatch) -> None:
    at = app_with(monkeypatch, FakeApi(fail=True))
    assert "Cannot reach" in at.error[0].value
    assert not at.exception


@pytest.mark.parametrize(
    ("status", "node", "expected"),
    [
        (
            "awaiting_approval",
            "human_approval",
            ["done", "active", "pending", "pending", "pending"],
        ),
        ("running", "researcher", ["done", "done", "active", "pending", "pending"]),
        ("running", "writer", ["done", "done", "done", "active", "pending"]),
        ("failed", "researcher", ["done", "done", "failed", "pending", "pending"]),
        ("done", None, ["done"] * 5),
    ],
)
def test_timeline_states(status: str, node: str | None, expected: list[str]) -> None:
    steps = timeline({"status": status, "current_node": node, "plan": PLAN})
    assert [state for _, state in steps] == expected
    assert "2 questions in parallel" in steps[2][0]


def test_report_body_drops_title_and_sources_and_demotes_sections() -> None:
    report = "# Acme\n\n## Overview\n\nFact [1].\n\n## Sources\n\n1. [a](https://a.test)\n"
    assert report_body(report) == "#### Overview\n\nFact [1]."


def test_report_body_escapes_dollars_so_amounts_are_not_rendered_as_latex() -> None:
    report = "# Acme\n\n## Overview\n\nRaised $24 billion, then $13.7 billion [1]."
    assert report_body(report) == "#### Overview\n\nRaised \\$24 billion, then \\$13.7 billion [1]."


def test_edited_plan_drops_blank_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [{"question": " Real one "}, {"question": "   "}, {"question": None}]
    monkeypatch.setattr(components.st, "data_editor", lambda *a, **k: rows)
    assert edited_plan(["Real one"]) == ["Real one"]
