"""Optional Langfuse tracing: one trace per research thread, disabled when keys are missing."""

import logging

from langchain_core.callbacks import BaseCallbackHandler
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler
from langfuse.types import TraceContext

from company_research_agent.config import Settings

logger = logging.getLogger(__name__)


class Tracing:
    def __init__(self, settings: Settings) -> None:
        self.public_key = settings.langfuse_public_key
        self.client = (
            Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key.get_secret_value(),
                host=settings.langfuse_host,
            )
            if settings.tracing_enabled
            else None
        )

    @staticmethod
    def trace_id(thread_id: str) -> str:
        # Seeded by the thread id, so the planning run and the resumed run share one trace.
        return Langfuse.create_trace_id(seed=thread_id)

    def callbacks(self, thread_id: str) -> list[BaseCallbackHandler]:
        if self.client is None:
            return []
        context = TraceContext(trace_id=self.trace_id(thread_id))
        return [CallbackHandler(public_key=self.public_key, trace_context=context)]

    def trace_url(self, thread_id: str) -> str | None:
        if self.client is None:
            return None
        try:
            return self.client.get_trace_url(trace_id=self.trace_id(thread_id))
        except Exception:
            # The link needs a Langfuse API call; an outage must not break the status endpoint.
            logger.warning("could not build the Langfuse trace url", exc_info=True)
            return None
