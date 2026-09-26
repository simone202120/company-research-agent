"""FastAPI application: wires settings, LLM, search, checkpointer and tracing into the runner."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from company_research_agent.api.routes import router
from company_research_agent.config import get_settings
from company_research_agent.core.errors import (
    InvalidResearchStateError,
    ResearchNotFoundError,
)
from company_research_agent.core.graph import build_graph
from company_research_agent.core.runner import ResearchRunner
from company_research_agent.infra.checkpointer import sqlite_checkpointer
from company_research_agent.infra.search import create_search
from company_research_agent.infra.tracing import Tracing
from company_research_agent.llm.factory import create_llm


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    with sqlite_checkpointer(settings.checkpoint_db) as saver:
        graph = build_graph(
            create_llm(settings), create_search(settings), saver, settings.max_revisions
        )
        app.state.tracing = Tracing(settings)
        app.state.runner = ResearchRunner(graph, app.state.tracing.callbacks)
        yield


async def not_found(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": f"research {exc} not found"}, status.HTTP_404_NOT_FOUND)


async def conflict(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status.HTTP_409_CONFLICT)


def create_app() -> FastAPI:
    app = FastAPI(title="Company Research Agent", lifespan=lifespan)
    app.include_router(router)
    app.add_exception_handler(ResearchNotFoundError, not_found)
    app.add_exception_handler(InvalidResearchStateError, conflict)
    return app


app = create_app()
