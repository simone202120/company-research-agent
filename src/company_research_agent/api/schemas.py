"""Request and response bodies of the HTTP API, with input limits."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from company_research_agent.core.nodes import MAX_QUESTIONS
from company_research_agent.core.runner import ResearchStatus

CompanyName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class ResearchRequest(BaseModel):
    company: CompanyName


class ApproveRequest(BaseModel):
    plan: list[Question] | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_QUESTIONS,
        description="Edited research questions; omit to approve the proposed plan",
    )


class StartResponse(BaseModel):
    thread_id: str
    plan: list[str]


class ApproveResponse(BaseModel):
    thread_id: str
    status: ResearchStatus


class SourceOut(BaseModel):
    number: int
    title: str
    url: str


class UsageOut(BaseModel):
    llm_calls: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class ResearchResponse(BaseModel):
    thread_id: str
    company: str
    status: ResearchStatus
    current_node: str | None
    plan: list[str]
    report: str | None
    sources: list[SourceOut]
    error: str | None
    usage: UsageOut | None
    latency_seconds: float | None
    trace_url: str | None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
