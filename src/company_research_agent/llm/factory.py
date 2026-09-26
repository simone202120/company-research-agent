"""The single place where the chat model is created: OpenRouter via its OpenAI-compatible API."""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from company_research_agent.config import Settings


def create_llm(settings: Settings) -> BaseChatModel:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=0.2,
        timeout=settings.llm_timeout_seconds,
        max_retries=2,
    )
