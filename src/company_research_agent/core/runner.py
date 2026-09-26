"""Runs research threads: start until the approval interrupt, resume, and report status."""

import logging
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import StrEnum

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from company_research_agent.core.errors import (
    InvalidResearchStateError,
    ResearchNotFoundError,
)
from company_research_agent.core.graph import ResearchGraph
from company_research_agent.core.state import Source

logger = logging.getLogger(__name__)


class ResearchStatus(StrEnum):
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class ResearchView:
    thread_id: str
    company: str
    status: ResearchStatus
    current_node: str | None = None
    plan: list[str] = field(default_factory=list)
    report: str | None = None
    sources: list[Source] = field(default_factory=list)
    error: str | None = None


class ResearchRunner:
    """Status is derived from the checkpoint, plus an in-process registry of active runs.

    The registry covers the gap between an API call and the first checkpoint written by the run,
    and prevents two concurrent resumes of the same thread.
    """

    def __init__(
        self, graph: ResearchGraph, callbacks: list[BaseCallbackHandler] | None = None
    ) -> None:
        self.graph = graph
        self.callbacks = callbacks or []
        self._active: set[str] = set()
        self._lock = threading.Lock()

    def _config(self, thread_id: str) -> RunnableConfig:
        return {
            "configurable": {"thread_id": thread_id},
            "callbacks": self.callbacks,
            "metadata": {"langfuse_session_id": thread_id},
            "run_name": "company-research",
        }

    @contextmanager
    def _running(self, thread_id: str) -> Iterator[None]:
        try:
            yield
        finally:
            with self._lock:
                self._active.discard(thread_id)

    def start(self, company: str) -> ResearchView:
        thread_id = uuid.uuid4().hex
        with self._lock:
            self._active.add(thread_id)
        logger.info("research %s started for %r", thread_id, company)
        with self._running(thread_id):
            self.graph.invoke({"company": company}, self._config(thread_id))
        return self.get(thread_id)

    def approve(self, thread_id: str) -> None:
        """Claims an awaiting thread so that only one caller can resume it."""
        with self._lock:
            status = self.get(thread_id).status
            if status is not ResearchStatus.AWAITING_APPROVAL:
                raise InvalidResearchStateError(f"research {thread_id} is {status}")
            self._active.add(thread_id)

    def resume(self, thread_id: str, plan: list[str] | None) -> None:
        """Runs a claimed thread to completion; call `approve` first."""
        logger.info("research %s approved", thread_id)
        with self._running(thread_id):
            self.graph.invoke(Command(resume={"plan": plan}), self._config(thread_id))
        logger.info("research %s finished", thread_id)

    def get(self, thread_id: str) -> ResearchView:
        snapshot = self.graph.get_state({"configurable": {"thread_id": thread_id}})
        values = snapshot.values
        if not values:
            raise ResearchNotFoundError(thread_id)
        error = next((repr(task.error) for task in snapshot.tasks if task.error), None)
        report = values.get("final_report")
        if thread_id in self._active:
            status = ResearchStatus.RUNNING
        elif error:
            status = ResearchStatus.FAILED
        elif snapshot.interrupts:
            status = ResearchStatus.AWAITING_APPROVAL
        elif report:
            status = ResearchStatus.DONE
        else:
            status, error = ResearchStatus.FAILED, "the run stopped before completion"
        return ResearchView(
            thread_id=thread_id,
            company=values["company"],
            status=status,
            current_node=snapshot.next[0] if snapshot.next else None,
            plan=values.get("plan", []),
            report=report,
            sources=values.get("sources", []) if report else [],
            error=error,
        )
