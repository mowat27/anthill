"""Slack channel implementation for Anthill workflows.

Posts handler progress and error messages to the originating Slack thread
via synchronous httpx.Client calls.
"""
import logging
from typing import Any

import httpx

from anthill.core.domain import State

logger = logging.getLogger("anthill.channels.slack")


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
        self.type = "slack"
        self.workflow_name = workflow_name
        self.initial_state: State = {**(initial_state or {})}
        self._slack_token = slack_token
        self._channel_id = channel_id
        self._thread_ts = thread_ts
        logger.debug(f"SlackChannel initialized: channel={channel_id}, thread_ts={thread_ts}")

    def _post_to_thread(self, text: str) -> None:
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
        self._post_to_thread(f"[{self.workflow_name}, {run_id}] {message}")

    def report_error(self, run_id: str, message: str) -> None:
        self._post_to_thread(f"[{self.workflow_name}, {run_id}] [ERROR] {message}")
