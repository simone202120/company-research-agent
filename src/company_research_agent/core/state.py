"""Typed graph state and the plain-data records stored in it (plain dicts, safe to checkpoint)."""

import operator
from typing import Annotated, TypedDict


class SearchResult(TypedDict):
    title: str
    url: str
    snippet: str


class Finding(TypedDict):
    question: str
    summary: str
    results: list[SearchResult]


class Source(TypedDict):
    number: int
    title: str
    url: str


class Usage(TypedDict):
    llm_calls: int
    input_tokens: int
    output_tokens: int


def add_usage(left: Usage, right: Usage) -> Usage:
    """State reducer summing the usage reported by each node; the channel starts as `{}`."""
    return Usage(
        llm_calls=left.get("llm_calls", 0) + right.get("llm_calls", 0),
        input_tokens=left.get("input_tokens", 0) + right.get("input_tokens", 0),
        output_tokens=left.get("output_tokens", 0) + right.get("output_tokens", 0),
    )


class ResearchState(TypedDict, total=False):
    company: str
    plan: list[str]
    approved: bool
    findings: Annotated[list[Finding], operator.add]
    sources: list[Source]
    draft_report: str
    review_feedback: str
    revision_count: int
    final_report: str
    usage: Annotated[Usage, add_usage]
    planning_seconds: float
    approved_at: float
    finished_at: float


class QuestionTask(TypedDict):
    """Input of one researcher branch, sent through the Send API."""

    company: str
    question: str
