"""Graph nodes (planner, approval, researcher, writer, reviewer) and their routing functions."""

import logging
from collections.abc import Callable
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.types import Send, interrupt
from pydantic import BaseModel, Field

from company_research_agent.core.errors import InvalidLLMOutputError
from company_research_agent.core.report import (
    global_numbers,
    invalid_citations,
    number_sources,
    remap_citations,
    render_report,
)
from company_research_agent.core.state import (
    Finding,
    QuestionTask,
    ResearchState,
    SearchResult,
    Source,
)
from company_research_agent.llm import prompts

logger = logging.getLogger(__name__)

MAX_QUESTIONS = 6
SNIPPET_MAX_CHARS = 1000


type SearchTool = Callable[[str], list[SearchResult]]


class ResearchPlan(BaseModel):
    questions: list[str] = Field(description="4 to 6 self-contained research questions")


class ReviewVerdict(BaseModel):
    verdict: Literal["ok", "revise"]
    feedback: str = Field(default="", description="Actionable feedback when verdict is revise")


def clean_plan(questions: list[str]) -> list[str]:
    """Drops blank questions and caps the plan, whether it comes from the LLM or a human edit."""
    return [q.strip() for q in questions if q.strip()][:MAX_QUESTIONS]


def search_query(company: str, question: str) -> str:
    """Edited questions may drop the company name; the search needs it to stay on topic."""
    return question if company.lower() in question.lower() else f"{company}: {question}"


def format_results(results: list[SearchResult]) -> str:
    return "\n\n".join(
        f"[{i}] {r['title']}\n{r['url']}\n{r['snippet'][:SNIPPET_MAX_CHARS]}"
        for i, r in enumerate(results, start=1)
    )


def format_notes(findings: list[Finding], sources: list[Source]) -> str:
    return "\n\n".join(
        f"### {f['question']}\n{remap_citations(f['summary'], global_numbers(f, sources))}"
        for f in findings
    )


class ResearchNodes:
    def __init__(self, llm: BaseChatModel, search: SearchTool, max_revisions: int) -> None:
        self.llm = llm
        self.search = search
        self.max_revisions = max_revisions

    def _structured[T: BaseModel](self, schema: type[T], messages: list[BaseMessage]) -> T:
        output = self.llm.with_structured_output(schema).invoke(messages)
        if not isinstance(output, schema):
            raise InvalidLLMOutputError(f"expected {schema.__name__}, got {type(output).__name__}")
        return output

    def _text(self, messages: list[BaseMessage]) -> str:
        return self.llm.invoke(messages).text.strip()

    def planner(self, state: ResearchState) -> ResearchState:
        plan = self._structured(
            ResearchPlan,
            [
                SystemMessage(prompts.PLANNER_SYSTEM),
                HumanMessage(prompts.PLANNER_USER.format(company=state["company"])),
            ],
        )
        questions = clean_plan(plan.questions)
        if not questions:
            raise InvalidLLMOutputError("the planner returned no research questions")
        return {"plan": questions, "approved": False, "revision_count": 0}

    def human_approval(self, state: ResearchState) -> ResearchState:
        decision = interrupt({"plan": state["plan"]})
        plan = clean_plan(decision.get("plan") or []) or state["plan"]
        return {"plan": plan, "approved": True}

    def researcher(self, state: QuestionTask) -> ResearchState:
        results = self.search(search_query(state["company"], state["question"]))
        logger.info("question %r: %d search results", state["question"], len(results))
        summary = ""
        if results:
            summary = self._text(
                [
                    SystemMessage(prompts.RESEARCHER_SYSTEM),
                    HumanMessage(
                        prompts.RESEARCHER_USER.format(
                            question=state["question"], results=format_results(results)
                        )
                    ),
                ]
            )
        finding: Finding = {"question": state["question"], "summary": summary, "results": results}
        return {"findings": [finding]}

    def writer(self, state: ResearchState) -> ResearchState:
        sources = number_sources(state["findings"])
        user = prompts.WRITER_USER.format(
            company=state["company"],
            sources="\n".join(f"[{s['number']}] {s['title']} - {s['url']}" for s in sources),
            notes=format_notes(state["findings"], sources),
        )
        revision_count = state.get("revision_count", 0)
        if state.get("review_feedback"):
            user += prompts.WRITER_REVISION.format(
                draft=state["draft_report"], feedback=state["review_feedback"]
            )
            revision_count += 1
        draft = self._text([SystemMessage(prompts.WRITER_SYSTEM), HumanMessage(user)])
        return {"sources": sources, "draft_report": draft, "revision_count": revision_count}

    def reviewer(self, state: ResearchState) -> ResearchState:
        draft, sources = state["draft_report"], state["sources"]
        verdict = self._structured(
            ReviewVerdict,
            [
                SystemMessage(prompts.REVIEWER_SYSTEM),
                HumanMessage(
                    prompts.REVIEWER_USER.format(
                        questions="\n".join(f"- {q}" for q in state["plan"]),
                        notes=format_notes(state["findings"], sources),
                        report=draft,
                    )
                ),
            ],
        )
        feedback = (
            [verdict.feedback or "Improve the report."] if verdict.verdict == "revise" else []
        )
        invalid = invalid_citations(draft, len(sources))
        if invalid:
            feedback.append(
                f"Citations {invalid} do not match any source; use only 1 to {len(sources)}."
            )
        review_feedback = "\n".join(feedback)
        if review_feedback and state.get("revision_count", 0) < self.max_revisions:
            return {"review_feedback": review_feedback}
        return {"review_feedback": review_feedback, "final_report": render_report(draft, sources)}


def route_to_researchers(state: ResearchState) -> list[Send]:
    return [
        Send("researcher", QuestionTask(company=state["company"], question=q))
        for q in state["plan"]
    ]


def route_after_review(state: ResearchState) -> Literal["writer", "__end__"]:
    return "__end__" if state.get("final_report") else "writer"
