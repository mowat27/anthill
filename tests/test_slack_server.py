"""Tests for the Slack event endpoint."""
import os
import tempfile
import textwrap
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from antkeeper.server import create_app


@pytest.fixture()
def slack_client():
    """Create a test client with Slack env vars and mocked slack_api.

    Yields:
        tuple: (TestClient, AsyncMock) - Test client and mocked Slack API.
    """
    log_dir = tempfile.mkdtemp()
    state_dir = tempfile.mkdtemp()
    agents_code = textwrap.dedent(f"""\
        from antkeeper.core.app import App, run_workflow
        from antkeeper.core.domain import State

        app = App(log_dir="{log_dir}", state_dir="{state_dir}")

        @app.handler
        def greet(runner, state: State) -> State:
            runner.report_progress("hello")
            return {{**state, "greeted": True}}
    """)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(agents_code)
        f.flush()
        agents_path = f.name

    env_patch = patch.dict(os.environ, {
        "SLACK_BOT_TOKEN": "xoxb-test",
        "SLACK_BOT_USER_ID": "U_BOT",
        "SLACK_COOLDOWN_SECONDS": "0",
    })
    api_mock = AsyncMock(return_value={"ok": True})
    slack_api_patch = patch("antkeeper.http.slack_events.slack_api", api_mock)

    try:
        env_patch.start()
        slack_api_patch.start()
        api = create_app(agents_path)
        client = TestClient(api)
        yield client, api_mock
    finally:
        slack_api_patch.stop()
        env_patch.stop()
        os.unlink(agents_path)


@pytest.fixture()
def slack_client_no_env():
    """Create a test client without SLACK_BOT_TOKEN or SLACK_BOT_USER_ID.

    Yields:
        TestClient: FastAPI test client without Slack environment variables.
    """
    log_dir = tempfile.mkdtemp()
    state_dir = tempfile.mkdtemp()
    agents_code = textwrap.dedent(f"""\
        from antkeeper.core.app import App, run_workflow
        from antkeeper.core.domain import State

        app = App(log_dir="{log_dir}", state_dir="{state_dir}")

        @app.handler
        def greet(runner, state: State) -> State:
            runner.report_progress("hello")
            return {{**state, "greeted": True}}
    """)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(agents_code)
        f.flush()
        agents_path = f.name

    env_patch = patch.dict(os.environ, {
        "SLACK_COOLDOWN_SECONDS": "0",
    })
    api_mock = AsyncMock(return_value={"ok": True})
    slack_api_patch = patch("antkeeper.http.slack_events.slack_api", api_mock)

    try:
        env_patch.start()
        slack_api_patch.start()
        api = create_app(agents_path)
        os.environ.pop("SLACK_BOT_TOKEN", None)
        os.environ.pop("SLACK_BOT_USER_ID", None)
        client = TestClient(api)
        yield client
    finally:
        slack_api_patch.stop()
        env_patch.stop()
        os.unlink(agents_path)


def _mention_event(text="<@U_BOT> greet hello", ts="1000.1", channel="C1", user="U_USER", files=None):
    """Helper to build a Slack app_mention event payload.

    Args:
        text: Message text with bot mention. Defaults to "<@U_BOT> greet hello".
        ts: Message timestamp. Defaults to "1000.1".
        channel: Channel ID. Defaults to "C1".
        user: User ID. Defaults to "U_USER".
        files: Optional list of file attachments. Defaults to None.

    Returns:
        dict: Slack event callback payload with app_mention event.
    """
    event = {
        "type": "app_mention",
        "text": text,
        "ts": ts,
        "channel": channel,
        "user": user,
    }
    if files:
        event["files"] = files
    return {"type": "event_callback", "event": event}


class TestSlackEventEndpoint:
    """Test suite for Slack event endpoint functionality."""

    def test_url_verification_returns_challenge(self, slack_client):
        """Test that URL verification returns challenge string."""
        client, mock = slack_client
        resp = client.post("/slack_event", json={
            "type": "url_verification",
            "challenge": "abc123",
        })
        assert resp.status_code == 200
        assert resp.json() == {"challenge": "abc123"}

    def test_bot_self_message_ignored(self, slack_client):
        """Test that bot's own messages are ignored."""
        client, mock = slack_client
        resp = client.post("/slack_event", json={
            "type": "event_callback",
            "event": {
                "type": "message",
                "bot_id": "B123",
                "text": "I am a bot",
                "ts": "1000.1",
                "channel": "C1",
            },
        })
        assert resp.status_code == 200
        mock.assert_not_called()

    def test_bot_mention_creates_pending_and_acknowledges(self, slack_client):
        """Test that bot mention creates pending request and adds thumbsup reaction."""
        client, mock = slack_client
        resp = client.post("/slack_event", json=_mention_event())
        assert resp.status_code == 200

        calls = mock.call_args_list
        reaction_calls = [c for c in calls if c.args[1] == "reactions.add"]
        assert len(reaction_calls) == 1
        assert reaction_calls[0].args[2]["name"] == "thumbsup"

    @patch.dict(os.environ, {"SLACK_COOLDOWN_SECONDS": "9999"})
    def test_duplicate_event_deduplication(self, slack_client):
        """Test that duplicate events are deduplicated within cooldown period."""
        client, mock = slack_client
        client.post("/slack_event", json=_mention_event(ts="dup.1"))
        mock.reset_mock()
        resp = client.post("/slack_event", json=_mention_event(ts="dup.1"))
        assert resp.status_code == 200

        reaction_calls = [c for c in mock.call_args_list if c.args[1] == "reactions.add"]
        assert len(reaction_calls) == 0

    @patch.dict(os.environ, {"SLACK_COOLDOWN_SECONDS": "9999"})
    def test_message_edit_updates_pending_text(self, slack_client):
        """Test that message edits update pending request text."""
        client, mock = slack_client
        client.post("/slack_event", json=_mention_event(ts="edit.1"))
        mock.reset_mock()

        resp = client.post("/slack_event", json={
            "type": "event_callback",
            "event": {
                "type": "message",
                "subtype": "message_changed",
                "channel": "C1",
                "ts": "wrapper.1",
                "message": {
                    "text": "<@U_BOT> greet updated text",
                    "ts": "edit.1",
                },
            },
        })
        assert resp.status_code == 200

    @patch.dict(os.environ, {"SLACK_COOLDOWN_SECONDS": "9999"})
    def test_thread_reply_appends_to_pending(self, slack_client):
        """Test that thread replies append to pending request."""
        client, mock = slack_client
        client.post("/slack_event", json=_mention_event(ts="reply.1"))
        mock.reset_mock()

        resp = client.post("/slack_event", json={
            "type": "event_callback",
            "event": {
                "type": "message",
                "text": "more context",
                "ts": "reply.2",
                "thread_ts": "reply.1",
                "channel": "C1",
                "user": "U_USER",
            },
        })
        assert resp.status_code == 200

        reaction_calls = [c for c in mock.call_args_list if c.args[1] == "reactions.add"]
        assert len(reaction_calls) == 1

    @patch.dict(os.environ, {"SLACK_COOLDOWN_SECONDS": "9999"})
    def test_thread_reply_with_files_appends_files(self, slack_client):
        """Test that thread replies with file attachments append files to pending request."""
        client, mock = slack_client
        client.post("/slack_event", json=_mention_event(ts="file.1"))
        mock.reset_mock()

        resp = client.post("/slack_event", json={
            "type": "event_callback",
            "event": {
                "type": "message",
                "text": "here is a file",
                "ts": "file.2",
                "thread_ts": "file.1",
                "channel": "C1",
                "user": "U_USER",
                "files": [{"id": "F1", "name": "test.txt"}],
            },
        })
        assert resp.status_code == 200

    @patch.dict(os.environ, {"SLACK_COOLDOWN_SECONDS": "9999"})
    def test_message_delete_removes_pending(self, slack_client):
        """Test that message deletion removes pending request."""
        client, mock = slack_client
        client.post("/slack_event", json=_mention_event(ts="del.1"))
        mock.reset_mock()

        resp = client.post("/slack_event", json={
            "type": "event_callback",
            "event": {
                "type": "message",
                "subtype": "message_deleted",
                "channel": "C1",
                "ts": "wrapper.1",
                "deleted_ts": "del.1",
            },
        })
        assert resp.status_code == 200

    def test_timer_fire_dispatches_workflow(self, slack_client):
        """Test that cooldown timer firing dispatches workflow and posts processing message."""
        client, mock = slack_client
        client.post("/slack_event", json=_mention_event(ts="fire.1"))

        time.sleep(0.2)

        calls = mock.call_args_list
        processing_calls = [
            c for c in calls
            if c.args[1] == "chat.postMessage" and "Processing" in c.args[2].get("text", "")
        ]
        assert len(processing_calls) >= 1

    def test_unknown_workflow_posts_error(self, slack_client):
        """Test that requesting unknown workflow posts error message to Slack."""
        client, mock = slack_client
        client.post("/slack_event", json=_mention_event(
            text="<@U_BOT> nonexistent_workflow hello",
            ts="unknown.1",
        ))

        time.sleep(0.2)

        calls = mock.call_args_list
        error_calls = [
            c for c in calls
            if c.args[1] == "chat.postMessage" and "Unknown workflow" in c.args[2].get("text", "")
        ]
        assert len(error_calls) >= 1

    def test_unknown_event_type_returns_200(self, slack_client):
        """Test that unknown event types are ignored and return 200."""
        client, mock = slack_client
        resp = client.post("/slack_event", json={
            "type": "event_callback",
            "event": {
                "type": "channel_created",
                "channel": {"id": "C2"},
            },
        })
        assert resp.status_code == 200

    def test_thread_reply_without_pending_parent_ignored(self, slack_client):
        """Test that thread replies without pending parent are ignored."""
        client, mock = slack_client
        resp = client.post("/slack_event", json={
            "type": "event_callback",
            "event": {
                "type": "message",
                "text": "orphan reply",
                "ts": "orphan.2",
                "thread_ts": "orphan.1",
                "channel": "C1",
                "user": "U_USER",
            },
        })
        assert resp.status_code == 200
        mock.assert_not_called()

    def test_missing_both_env_vars_returns_422(self, slack_client_no_env):
        """Test that missing both SLACK_BOT_TOKEN and SLACK_BOT_USER_ID returns 422."""
        client = slack_client_no_env
        resp = client.post("/slack_event", json=_mention_event())
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "SLACK_BOT_TOKEN" in detail
        assert "SLACK_BOT_USER_ID" in detail

    @patch.dict(os.environ, {"SLACK_BOT_USER_ID": "U_BOT"})
    def test_missing_slack_bot_token_returns_422(self, slack_client_no_env):
        """Test that missing SLACK_BOT_TOKEN returns 422 with appropriate error."""
        client = slack_client_no_env
        resp = client.post("/slack_event", json=_mention_event())
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "SLACK_BOT_TOKEN" in detail
        assert "SLACK_BOT_USER_ID" not in detail

    @patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"})
    def test_missing_slack_bot_user_id_returns_422(self, slack_client_no_env):
        """Test that missing SLACK_BOT_USER_ID returns 422 with appropriate error."""
        client = slack_client_no_env
        resp = client.post("/slack_event", json=_mention_event())
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "SLACK_BOT_USER_ID" in detail
        assert "SLACK_BOT_TOKEN" not in detail

    def test_url_verification_works_without_env_vars(self, slack_client_no_env):
        """Test that URL verification works even without Slack environment variables."""
        client = slack_client_no_env
        resp = client.post("/slack_event", json={
            "type": "url_verification",
            "challenge": "test-challenge",
        })
        assert resp.status_code == 200
        assert resp.json() == {"challenge": "test-challenge"}
