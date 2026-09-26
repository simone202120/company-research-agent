"""HTTP client for the research API, turning transport and HTTP errors into friendly messages."""

from typing import Any

import httpx


class ApiError(Exception):
    """A user-facing message describing why an API call failed."""


class ResearchApi:
    def __init__(self, base_url: str, timeout: float = 120) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = httpx.request(
                method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs
            )
        except httpx.HTTPError as exc:
            raise ApiError(
                f"Cannot reach the research API at {self.base_url}. Check that it is running."
            ) from exc
        if response.is_error:
            raise ApiError(error_message(response))
        body: dict[str, Any] = response.json()
        return body

    def healthy(self) -> bool:
        try:
            self._request("GET", "/health")
        except ApiError:
            return False
        return True

    def start(self, company: str) -> dict[str, Any]:
        return self._request("POST", "/research", json={"company": company})

    def approve(self, thread_id: str, plan: list[str]) -> dict[str, Any]:
        return self._request("POST", f"/research/{thread_id}/approve", json={"plan": plan})

    def get(self, thread_id: str) -> dict[str, Any]:
        return self._request("GET", f"/research/{thread_id}")


def error_message(response: httpx.Response) -> str:
    if response.status_code == 404:
        return "This research no longer exists. Start a new one."
    if response.status_code == 409:
        return "This research was already approved. Refresh to follow its progress."
    if response.status_code == 422:
        return "Some input is invalid: use 1 to 100 characters for the company, 1 to 6 questions."
    return f"The research API failed (HTTP {response.status_code}). Check the API logs and retry."
