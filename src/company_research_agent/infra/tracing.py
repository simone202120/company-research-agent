"""Optional Langfuse tracing: a LangChain callback handler when keys are set, nothing otherwise."""

from langchain_core.callbacks import BaseCallbackHandler
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from company_research_agent.config import Settings


def tracing_callbacks(settings: Settings) -> list[BaseCallbackHandler]:
    if not settings.tracing_enabled:
        return []
    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        host=settings.langfuse_host,
    )
    return [CallbackHandler(public_key=settings.langfuse_public_key)]
