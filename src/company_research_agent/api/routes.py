"""Research endpoints: start (until plan approval), approve (resume in background), status."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Path, Request, status

from company_research_agent.api.schemas import (
    ApproveRequest,
    ApproveResponse,
    HealthResponse,
    ResearchRequest,
    ResearchResponse,
    StartResponse,
    UsageOut,
)
from company_research_agent.config import Settings, get_settings
from company_research_agent.core.runner import ResearchRunner, ResearchStatus
from company_research_agent.core.state import Usage
from company_research_agent.infra.tracing import Tracing

router = APIRouter()

ThreadId = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]


def get_runner(request: Request) -> ResearchRunner:
    runner: ResearchRunner = request.app.state.runner
    return runner


def get_tracing(request: Request) -> Tracing:
    tracing: Tracing = request.app.state.tracing
    return tracing


Runner = Annotated[ResearchRunner, Depends(get_runner)]


def usage_out(usage: Usage, settings: Settings) -> UsageOut:
    cost = (
        usage["input_tokens"] * settings.llm_input_price_per_mtok
        + usage["output_tokens"] * settings.llm_output_price_per_mtok
    ) / 1_000_000
    return UsageOut(**usage, estimated_cost_usd=round(cost, 6))


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse()


@router.post("/research", status_code=status.HTTP_201_CREATED)
def start_research(body: ResearchRequest, runner: Runner) -> StartResponse:
    view = runner.start(body.company)
    return StartResponse(thread_id=view.thread_id, plan=view.plan)


@router.post("/research/{thread_id}/approve", status_code=status.HTTP_202_ACCEPTED)
def approve_research(
    thread_id: ThreadId, body: ApproveRequest, runner: Runner, tasks: BackgroundTasks
) -> ApproveResponse:
    runner.approve(thread_id)
    tasks.add_task(runner.resume, thread_id, body.plan)
    return ApproveResponse(thread_id=thread_id, status=ResearchStatus.RUNNING)


@router.get("/research/{thread_id}")
def get_research(
    thread_id: ThreadId,
    runner: Runner,
    tracing: Annotated[Tracing, Depends(get_tracing)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResearchResponse:
    view = runner.get(thread_id)
    return ResearchResponse.model_validate(
        {
            **asdict(view),
            "usage": usage_out(view.usage, settings) if view.usage else None,
            # Only finished runs link their trace: building the link may call Langfuse.
            "trace_url": tracing.trace_url(thread_id)
            if view.status is ResearchStatus.DONE
            else None,
        }
    )
