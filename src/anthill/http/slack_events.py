"""Slack event handling: event routing, pending message store, debounce timers.

Receives Slack Events API payloads, accumulates edits and thread replies
with a debounce timer, then dispatches to workflow handlers.
"""
import asyncio
import logging
import os
import re
from dataclasses import dataclass, field

import httpx
from fastapi import FastAPI, Request

from anthill.channels.slack import SlackChannel
from anthill.core.app import App
from anthill.core.runner import Runner

logger = logging.getLogger("anthill.http.slack_events")


def is_bot_message(event: dict) -> bool:
    """Check if a Slack event is from a bot.

    Args:
        event: Slack event dictionary.

    Returns:
        True if the event contains a bot_id field, False otherwise.
    """
    return bool(event.get("bot_id"))


def is_bot_mention(text: str, bot_user_id: str) -> bool:
    """Check if text contains a mention of the bot user.

    Args:
        text: Message text to check.
        bot_user_id: Slack user ID of the bot.

    Returns:
        True if the text contains a mention of the bot user ID, False otherwise.
    """
    return f"<@{bot_user_id}>" in text


def strip_mention(text: str) -> str:
    """Remove bot mention from the beginning of text.

    Args:
        text: Message text potentially containing a bot mention.

    Returns:
        Text with leading bot mention and surrounding whitespace removed.
    """
    return re.sub(r"^\s*<@U[A-Z0-9]+>\s*", "", text)


@dataclass
class PendingMessage:
    """Represents a Slack message waiting for debounce timer.

    Accumulates edits and thread replies while a cooldown timer is active.
    Once the timer fires, dispatches the accumulated message to a workflow.

    Attributes:
        channel_id: Slack channel ID where the message was posted.
        ts: Slack timestamp identifier for the message.
        user: Slack user ID who sent the message.
        text: Accumulated message text (updated on edits and thread replies).
        files: List of file attachments from the message and thread replies.
        workflow_name: Name of the workflow handler to dispatch to.
        timer_task: Active asyncio timer task, or None if not running.
    """
    channel_id: str
    ts: str
    user: str
    text: str
    files: list[dict]
    workflow_name: str
    timer_task: asyncio.Task | None = field(default=None, repr=False)


async def slack_api(token: str, method: str, payload: dict) -> dict:
    """Call a Slack API method with the given payload.

    Args:
        token: Slack bot token for authorization.
        method: Slack API method name (e.g., "chat.postMessage").
        payload: JSON payload to send in the request body.

    Returns:
        JSON response from the Slack API as a dictionary.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://slack.com/api/{method}",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        return resp.json()


def setup_slack_routes(api: FastAPI, anthill_app: App) -> None:
    """Register Slack event handling endpoint on the FastAPI application.

    Creates a POST /slack_event endpoint that handles Slack Events API callbacks.
    Implements debounced message processing with support for message edits,
    thread replies, and deletions.

    Args:
        api: FastAPI application instance to register routes on.
        anthill_app: Anthill App instance containing registered workflow handlers.

    Environment Variables:
        SLACK_BOT_TOKEN: Slack bot OAuth token for API calls.
        SLACK_BOT_USER_ID: Slack user ID of the bot for mention detection.
        SLACK_COOLDOWN_SECONDS: Debounce timer duration in seconds (default: 30).
    """
    from anthill.server import _run_workflow

    pending: dict[tuple[str, str], PendingMessage] = {}

    async def _on_timer_fire(key: tuple[str, str], token: str, cooldown: float) -> None:
        await asyncio.sleep(cooldown)
        entry = pending.pop(key, None)
        if entry is None:
            return

        await slack_api(token, "chat.postMessage", {
            "channel": entry.channel_id,
            "thread_ts": entry.ts,
            "text": "Processing your request...",
        })

        try:
            anthill_app.get_handler(entry.workflow_name)
        except ValueError:
            await slack_api(token, "chat.postMessage", {
                "channel": entry.channel_id,
                "thread_ts": entry.ts,
                "text": f"Unknown workflow: {entry.workflow_name}",
            })
            return

        initial_state: dict = {"prompt": entry.text, "slack_user": entry.user}
        if entry.files:
            initial_state["files"] = entry.files

        channel = SlackChannel(
            workflow_name=entry.workflow_name,
            initial_state=initial_state,
            slack_token=token,
            channel_id=entry.channel_id,
            thread_ts=entry.ts,
        )
        runner = Runner(anthill_app, channel)
        await asyncio.to_thread(_run_workflow, runner)

    @api.post("/slack_event")
    async def slack_event(request: Request):
        body = await request.json()

        # 1. URL verification
        if body.get("type") == "url_verification":
            return {"challenge": body["challenge"]}

        # 2. Extract event
        event = body.get("event", {})
        if not event:
            return {"ok": True}

        # 3. Bot self-filter
        if is_bot_message(event):
            return {"ok": True}

        token = os.environ.get("SLACK_BOT_TOKEN", "")
        bot_user_id = os.environ.get("SLACK_BOT_USER_ID", "")
        cooldown = float(os.environ.get("SLACK_COOLDOWN_SECONDS", "30"))

        channel_id = event.get("channel", "")
        event_ts = event.get("ts", "")

        # 5. Thread reply (checked BEFORE mention)
        if event.get("thread_ts") and event["ts"] != event["thread_ts"]:
            key = (channel_id, event["thread_ts"])
            if key in pending:
                entry = pending[key]
                if entry.timer_task:
                    entry.timer_task.cancel()
                entry.text += "\n" + event.get("text", "")
                entry.files.extend(event.get("files", []))
                entry.timer_task = asyncio.create_task(
                    _on_timer_fire(key, token, cooldown)
                )
                await slack_api(token, "reactions.add", {
                    "channel": channel_id,
                    "timestamp": event_ts,
                    "name": "thumbsup",
                })
            return {"ok": True}

        # 6. Message edit
        if event.get("subtype") == "message_changed":
            nested = event.get("message", {})
            key = (channel_id, nested.get("ts", ""))
            if key in pending:
                entry = pending[key]
                if entry.timer_task:
                    entry.timer_task.cancel()
                entry.text = strip_mention(nested.get("text", ""))
                entry.timer_task = asyncio.create_task(
                    _on_timer_fire(key, token, cooldown)
                )
            return {"ok": True}

        # 7. Message delete
        if event.get("subtype") == "message_deleted":
            key = (channel_id, event.get("deleted_ts", ""))
            if key in pending:
                entry = pending[key]
                if entry.timer_task:
                    entry.timer_task.cancel()
                del pending[key]
            return {"ok": True}

        # 8. Bot mention (new message)
        event_type = event.get("type", "")
        subtype = event.get("subtype")
        if event_type in ("app_mention", "message") and subtype in (None, "file_share"):
            text = event.get("text", "")
            if is_bot_mention(text, bot_user_id):
                clean_text = strip_mention(text)
                parts = clean_text.split()
                workflow_name = parts[0] if parts else ""

                key = (channel_id, event_ts)
                if key in pending:
                    return {"ok": True}

                entry = PendingMessage(
                    channel_id=channel_id,
                    ts=event_ts,
                    user=event.get("user", ""),
                    text=clean_text,
                    files=event.get("files", []),
                    workflow_name=workflow_name,
                )
                pending[key] = entry

                await slack_api(token, "reactions.add", {
                    "channel": channel_id,
                    "timestamp": event_ts,
                    "name": "thumbsup",
                })

                entry.timer_task = asyncio.create_task(
                    _on_timer_fire(key, token, cooldown)
                )

                return {"ok": True}

        # 9. All other events
        return {"ok": True}
