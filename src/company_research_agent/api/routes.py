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
)
from company_research_agent.core.runner import ResearchRunner, ResearchStatus

router = APIRouter()

ThreadId = Annotated[str, Path(pattern=r"^[0-9a-f]{32}$")]


def get_runner(request: Request) -> ResearchRunner:
    runner: ResearchRunner = request.app.state.runner
    return runner


Runner = Annotated[ResearchRunner, Depends(get_runner)]


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
def get_research(thread_id: ThreadId, runner: Runner) -> ResearchResponse:
    return ResearchResponse.model_validate(asdict(runner.get(thread_id)))
