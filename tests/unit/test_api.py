import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from company_research_agent.api.app import create_app
from company_research_agent.api.routes import get_runner
from company_research_agent.core.graph import build_graph
from company_research_agent.core.runner import ResearchRunner
from tests.fakes import FakeLLM, FakeSearch

MISSING_ID = "0" * 32


@pytest.fixture
def client(runner: ResearchRunner) -> TestClient:
    return client_for(runner)


def client_for(runner: ResearchRunner) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_runner] = lambda: runner
    return TestClient(app, raise_server_exceptions=False)


def start(client: TestClient) -> str:
    response = client.post("/research", json={"company": "  Acme  "})
    assert response.status_code == 201
    thread_id: str = response.json()["thread_id"]
    return thread_id


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_start_returns_thread_and_plan(client: TestClient, fake_llm: FakeLLM) -> None:
    response = client.post("/research", json={"company": "Acme"})
    assert response.status_code == 201
    assert response.json()["plan"] == fake_llm.plan


@pytest.mark.parametrize("company", ["", "   ", "x" * 101])
def test_start_rejects_invalid_company(client: TestClient, company: str) -> None:
    assert client.post("/research", json={"company": company}).status_code == 422


def test_status_awaiting_approval_after_start(client: TestClient) -> None:
    thread_id = start(client)
    body = client.get(f"/research/{thread_id}").json()
    assert body["status"] == "awaiting_approval"
    assert body["company"] == "Acme"
    assert body["current_node"] == "human_approval"
    assert body["report"] is None


def test_approve_with_edited_plan_runs_to_done(client: TestClient, fake_search: FakeSearch) -> None:
    thread_id = start(client)
    response = client.post(f"/research/{thread_id}/approve", json={"plan": ["Acme revenue?"]})
    assert response.status_code == 202
    assert response.json() == {"thread_id": thread_id, "status": "running"}
    body = client.get(f"/research/{thread_id}").json()
    assert body["status"] == "done"
    assert body["plan"] == ["Acme revenue?"]
    assert fake_search.queries == ["Acme revenue?"]
    assert "## Sources" in body["report"]
    assert body["sources"][0] == {"number": 1, "title": "Acme home", "url": "https://acme.test"}


def test_approve_without_body_plan_keeps_plan(client: TestClient, fake_llm: FakeLLM) -> None:
    thread_id = start(client)
    assert client.post(f"/research/{thread_id}/approve", json={}).status_code == 202
    assert client.get(f"/research/{thread_id}").json()["plan"] == fake_llm.plan


@pytest.mark.parametrize("plan", [[], [""], ["q"] * 7, ["x" * 301]])
def test_approve_rejects_invalid_plan(client: TestClient, plan: list[str]) -> None:
    thread_id = start(client)
    response = client.post(f"/research/{thread_id}/approve", json={"plan": plan})
    assert response.status_code == 422


def test_approve_twice_conflicts(client: TestClient) -> None:
    thread_id = start(client)
    client.post(f"/research/{thread_id}/approve", json={})
    assert client.post(f"/research/{thread_id}/approve", json={}).status_code == 409


def test_unknown_thread_is_not_found(client: TestClient) -> None:
    assert client.get(f"/research/{MISSING_ID}").status_code == 404
    assert client.post(f"/research/{MISSING_ID}/approve", json={}).status_code == 404


def test_malformed_thread_id_is_rejected(client: TestClient) -> None:
    assert client.get("/research/not-a-thread").status_code == 422


def test_failed_run_reports_failed_status(fake_llm: FakeLLM) -> None:
    runner = ResearchRunner(build_graph(fake_llm, FakeSearch(fail=True), InMemorySaver(), 1))
    client = client_for(runner)
    thread_id = start(client)
    client.post(f"/research/{thread_id}/approve", json={})
    body = client.get(f"/research/{thread_id}").json()
    assert body["status"] == "failed"
    assert "search is down" in body["error"]
