"""Slack channel implementation for Antkeeper workflows.

Posts handler progress and error messages to the originating Slack thread
via synchronous httpx.Client calls.
"""
import logging
from typing import Any

import httpx

from antkeeper.core.domain import State

logger = logging.getLogger("antkeeper.channels.slack")


class SlackChannel:
    """Channel implementation for Slack thread-based workflow execution.

    Posts progress and error messages to a specific Slack thread using
    the Slack Web API. Uses synchronous httpx because handler code runs
    in a threadpool via asyncio.to_thread.

    Attributes:
        type: Channel type identifier ("slack").
        workflow_name: Name of the workflow to execute.
        initial_state: Initial state dictionary for the workflow.
    """

    def __init__(
        self,
        workflow_name: str,
        initial_state: State | None = None,
        *,
        slack_token: str,
        channel_id: str,
        thread_ts: str,
    ) -> None:
        """Initialize a SlackChannel instance.

        Args:
            workflow_name (str): Name of the workflow to execute.
            initial_state (State | None): Optional initial state dictionary.
                Defaults to empty dict.
            slack_token (str): Slack bot token for API authentication.
            channel_id (str): Slack channel ID where the workflow was triggered.
            thread_ts (str): Timestamp of the thread to post messages to.
        """
        self.type = "slack"
        self.workflow_name = workflow_name
        self.initial_state: State = {**(initial_state or {})}
        self._slack_token = slack_token
        self._channel_id = channel_id
        self._thread_ts = thread_ts
        logger.debug(f"SlackChannel initialized: channel={channel_id}, thread_ts={thread_ts}")

    def _post_to_thread(self, text: str) -> None:
        """Post a message to the Slack thread.

        Uses synchronous httpx.Client to post messages to Slack via the
        chat.postMessage API endpoint. Logs errors but does not raise exceptions.

        Args:
            text (str): Message text to post to the thread.
        """
        try:
            with httpx.Client() as client:
                client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {self._slack_token}"},
                    json={
                        "channel": self._channel_id,
                        "thread_ts": self._thread_ts,
                        "text": text,
                    },
                )
        except httpx.HTTPError as exc:
            logger.error(f"Failed to post to Slack thread: {exc}")

    def report_progress(self, run_id: str, message: str, **opts: Any) -> None:
        """Report workflow progress to the Slack thread.

        Args:
            run_id (str): Unique identifier for the workflow run.
            message (str): Progress message to post.
            **opts (Any): Additional options (unused, for protocol compatibility).
        """
        self._post_to_thread(f"[{self.workflow_name}, {run_id}] {message}")

    def report_error(self, run_id: str, message: str) -> None:
        """Report a workflow error to the Slack thread.

        Posts an error message with [ERROR] prefix to the thread.

        Args:
            run_id (str): Unique identifier for the workflow run.
            message (str): Error message to post.
        """
        self._post_to_thread(f"[{self.workflow_name}, {run_id}] [ERROR] {message}")
