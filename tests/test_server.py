"""Tests for the FastAPI webhook server.

Tests server initialization, webhook endpoint functionality, error handling,
and request validation.
"""

import os
import tempfile
import textwrap

import pytest
from fastapi.testclient import TestClient

from antkeeper.server import create_app


@pytest.fixture()
def client():
    """Create a test client with a temporary agents file."""
    log_dir = tempfile.mkdtemp()
    agents_code = textwrap.dedent(f"""\
        from antkeeper.core.app import App, run_workflow
        from antkeeper.core.domain import State

        app = App(log_dir="{log_dir}")

        @app.handler
        def add_1(runner, state: State) -> State:
            return {{**state, "result": int(state.get("result", 0)) + 1}}
    """)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(agents_code)
        f.flush()
        agents_path = f.name

    try:
        api = create_app(agents_path)
        yield TestClient(api)
    finally:
        os.unlink(agents_path)


class TestWebhookEndpoint:
    """Test suite for webhook endpoint functionality."""

    def test_webhook_returns_run_id(self, client):
        """Test that webhook successfully executes workflow and returns run ID."""
        response = client.post("/webhook", json={"workflow_name": "add_1", "initial_state": {"result": "10"}})
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert len(data["run_id"]) == 8

    def test_webhook_unknown_workflow_returns_404(self, client):
        """Test that requesting nonexistent workflow returns 404 error."""
        response = client.post("/webhook", json={"workflow_name": "nonexistent"})
        assert response.status_code == 404
        assert "Unknown workflow" in response.json()["detail"]

    def test_webhook_invalid_body_returns_422(self, client):
        """Test that invalid request body returns 422 validation error."""
        response = client.post("/webhook", json={})
        assert response.status_code == 422
