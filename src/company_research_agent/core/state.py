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


class QuestionTask(TypedDict):
    """Input of one researcher branch, sent through the Send API."""

    company: str
    question: str
