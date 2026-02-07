"""Tests for the Slack channel implementation."""
from unittest.mock import patch, MagicMock

import httpx
import pytest

from anthill.channels.slack import SlackChannel


class TestSlackChannel:
    def _make_channel(self, **overrides):
        defaults: dict = {
            "workflow_name": "wf",
            "slack_token": "xoxb-test-token",
            "channel_id": "C123",
            "thread_ts": "1234567890.123456",
        }
        defaults.update(overrides)
        wf: str = defaults.pop("workflow_name")
        state: dict | None = defaults.pop("initial_state", None)
        return SlackChannel(wf, state, **defaults)

    def test_slack_channel_type(self):
        channel = self._make_channel()
        assert channel.type == "slack"

    @pytest.mark.parametrize("initial_state,expected", [
        ({"k": "v"}, {"k": "v"}),
        (None, {}),
    ])
    def test_slack_channel_initial_state(self, initial_state, expected):
        channel = self._make_channel(initial_state=initial_state)
        assert channel.initial_state == expected

    @patch("anthill.channels.slack.httpx.Client")
    def test_report_progress_posts_to_slack_thread(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        channel = self._make_channel()
        channel.report_progress("run1", "step done")

        mock_client.post.assert_called_once_with(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": "Bearer xoxb-test-token"},
            json={
                "channel": "C123",
                "thread_ts": "1234567890.123456",
                "text": "[wf, run1] step done",
            },
        )

    @patch("anthill.channels.slack.httpx.Client")
    def test_report_error_posts_error_formatted_message(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        channel = self._make_channel()
        channel.report_error("run1", "something broke")

        call_args = mock_client.post.call_args
        assert "[ERROR]" in call_args.kwargs["json"]["text"]

    @patch("anthill.channels.slack.httpx.Client")
    def test_report_progress_survives_http_failure(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.HTTPError("connection failed")
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

        channel = self._make_channel()
        channel.report_progress("run1", "step done")  # should not raise
