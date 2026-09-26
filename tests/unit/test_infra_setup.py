from pathlib import Path

import pytest
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler

from company_research_agent.config import ConfigurationError, Settings
from company_research_agent.infra.checkpointer import sqlite_checkpointer
from company_research_agent.infra.tracing import Tracing
from company_research_agent.llm.factory import create_llm


def test_create_llm_targets_openrouter() -> None:
    settings = Settings(_env_file=None, openrouter_api_key="sk-test", llm_model="vendor/model")
    llm = create_llm(settings)
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "vendor/model"
    assert llm.openai_api_base == settings.openrouter_base_url


def test_create_llm_without_key_fails_fast() -> None:
    with pytest.raises(ConfigurationError, match="OPENROUTER_API_KEY"):
        create_llm(Settings(_env_file=None, openrouter_api_key=""))


def enabled_tracing() -> Tracing:
    return Tracing(
        Settings(
            _env_file=None,
            langfuse_public_key="pk-test",
            langfuse_secret_key="sk-test",
            langfuse_host="http://localhost:1",
        )
    )


def test_tracing_disabled_without_keys() -> None:
    tracing = Tracing(Settings(_env_file=None, langfuse_public_key=""))
    assert tracing.callbacks("t1") == []
    assert tracing.trace_url("t1") is None


def test_tracing_uses_one_trace_per_thread() -> None:
    tracing = enabled_tracing()
    [handler] = tracing.callbacks("t1")
    assert isinstance(handler, CallbackHandler)
    assert Tracing.trace_id("t1") == Tracing.trace_id("t1") != Tracing.trace_id("t2")


def test_trace_url_points_to_the_thread_trace(monkeypatch: pytest.MonkeyPatch) -> None:
    tracing = enabled_tracing()
    assert tracing.client is not None
    monkeypatch.setattr(tracing.client, "_get_project_id", lambda: "proj")
    assert (
        tracing.trace_url("t1")
        == f"http://localhost:1/project/proj/traces/{Tracing.trace_id('t1')}"
    )


def test_trace_url_is_none_when_langfuse_is_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    tracing = enabled_tracing()

    def unreachable() -> str:
        raise ConnectionError("down")

    assert tracing.client is not None
    monkeypatch.setattr(tracing.client, "_get_project_id", unreachable)
    assert tracing.trace_url("t1") is None


def test_sqlite_checkpointer_creates_parent_folder(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "checkpoints.sqlite"
    with sqlite_checkpointer(str(path)) as saver:
        assert list(saver.list(None)) == []
    assert path.exists()
