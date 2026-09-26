"""Deterministic stand-ins for the LLM and the search tool, shared by unit and integration tests."""

from typing import Any

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, Field

from company_research_agent.core.nodes import ResearchPlan, ReviewVerdict
from company_research_agent.core.state import SearchResult
from company_research_agent.llm import prompts

PLAN = [
    "What does Acme do?",
    "What products does Acme sell?",
    "What technology does Acme use?",
    "What are Acme's recent news?",
]
REPORT = "# Acme\n\n## Overview\n\nAcme builds rockets [1].\n\n## Products\n\nAnvils [2]."


class FakeLLM(BaseChatModel):
    """Answers each node by its system prompt; review verdicts are consumed in order, then ok."""

    plan: list[str] = Field(default_factory=lambda: list(PLAN))
    summary: str = "Acme builds rockets [1] and anvils [2]."
    report: str = REPORT
    verdicts: list[ReviewVerdict] = Field(default_factory=list)
    writer_prompts: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(
        self, messages: list[BaseMessage], stop: list[str] | None = None, **kwargs: Any
    ) -> ChatResult:
        if messages[0].content == prompts.WRITER_SYSTEM:
            self.writer_prompts.append(str(messages[1].content))
            text = self.report
        else:
            text = self.summary
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    def with_structured_output(
        self, schema: dict[str, Any] | type, **kwargs: Any
    ) -> Runnable[LanguageModelInput, dict[str, Any] | BaseModel]:
        def answer(_: LanguageModelInput) -> BaseModel:
            if schema is ResearchPlan:
                return ResearchPlan(questions=self.plan)
            return self.verdicts.pop(0) if self.verdicts else ReviewVerdict(verdict="ok")

        return RunnableLambda(answer)


class FakeSearch:
    """Returns two results per query (one shared by every query) and records the queries."""

    def __init__(self, fail: bool = False) -> None:
        self.queries: list[str] = []
        self.fail = fail

    def __call__(self, query: str) -> list[SearchResult]:
        self.queries.append(query)
        if self.fail:
            raise RuntimeError("search is down")
        return [
            {"title": "Acme home", "url": "https://acme.test", "snippet": "Acme builds rockets."},
            {"title": query, "url": f"https://news.test/{len(query)}", "snippet": "Anvils."},
        ]
