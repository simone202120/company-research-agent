from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from company_research_agent.api.app import create_app
from company_research_agent.config import get_settings

pytestmark = pytest.mark.integration


def test_app_starts_with_sqlite_checkpointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "data" / "checkpoints.sqlite"
    monkeypatch.setenv("CHECKPOINT_DB", str(db))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    for key in ("LANGFUSE_PUBLIC_KEY", "TAVILY_API_KEY"):
        monkeypatch.setenv(key, "")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            assert client.get("/health").status_code == 200
            assert client.get(f"/research/{'0' * 32}").status_code == 404
    finally:
        get_settings.cache_clear()
    assert db.exists()
