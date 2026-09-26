from pathlib import Path

from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler

from company_research_agent.config import Settings
from company_research_agent.infra.checkpointer import sqlite_checkpointer
from company_research_agent.infra.tracing import tracing_callbacks
from company_research_agent.llm.factory import create_llm


def test_create_llm_targets_openrouter() -> None:
    settings = Settings(_env_file=None, openrouter_api_key="sk-test", llm_model="vendor/model")
    llm = create_llm(settings)
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "vendor/model"
    assert llm.openai_api_base == settings.openrouter_base_url


def test_tracing_disabled_without_keys() -> None:
    assert tracing_callbacks(Settings(_env_file=None, langfuse_public_key="")) == []


def test_tracing_enabled_returns_langfuse_handler() -> None:
    settings = Settings(
        _env_file=None,
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
        langfuse_host="http://localhost:1",
    )
    [handler] = tracing_callbacks(settings)
    assert isinstance(handler, CallbackHandler)


def test_sqlite_checkpointer_creates_parent_folder(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "checkpoints.sqlite"
    with sqlite_checkpointer(str(path)) as saver:
        assert list(saver.list(None)) == []
    assert path.exists()
