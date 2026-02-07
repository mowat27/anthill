"""Slack debounce webhook spike.

Receives real Slack Events API events, maintains a pending dict with
cooldown timers, and prints state after each event to observe debounce
behaviour.

Usage:
    # Terminal 1: ngrok
    ngrok http 9000

    # Terminal 2: spike server
    COOLDOWN_SECONDS=5 SLACK_BOT_TOKEN=xoxb-... uv run uvicorn spike:app --reload --port 9000

Then configure your Slack app's Event Subscription URL to:
    https://<ngrok-id>.ngrok-free.app/event
"""

from __future__ import annotations

import asyncio
import json
import os
import re

from dotenv import load_dotenv

load_dotenv()
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

COOLDOWN_SECONDS = int(os.environ.get("COOLDOWN_SECONDS", "30"))
BOT_USER_ID = os.environ.get("BOT_USER_ID", "")
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")

app = FastAPI()

# ── Pending message store ────────────────────────────────────────────


@dataclass
class PendingMessage:
    text: str
    user: str
    files: list[dict] = field(default_factory=list)
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    fires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    timer: asyncio.Task | None = None


pending: dict[tuple[str, str], PendingMessage] = {}

# ── Helpers ──────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_bot_message(event: dict) -> bool:
    """Check if this event was sent by our bot."""
    if event.get("bot_id"):
        return True
    if BOT_USER_ID and event.get("user") == BOT_USER_ID:
        return True
    return False


def _is_bot_mention(text: str) -> bool:
    """Check if the message text mentions our bot."""
    if BOT_USER_ID:
        return f"<@{BOT_USER_ID}>" in text
    # Fallback: any user mention at the start
    return bool(re.match(r"^\s*<@U[A-Z0-9]+>", text))


def _strip_mention(text: str) -> str:
    """Remove leading <@U...> bot mention from text."""
    return re.sub(r"^\s*<@U[A-Z0-9]+>\s*", "", text)


def _pending_snapshot() -> list[dict]:
    """Return a JSON-serialisable snapshot of the pending dict."""
    items = []
    for (channel, ts), msg in pending.items():
        items.append(
            {
                "key": f"({channel}, {ts})",
                "text": msg.text,
                "user": msg.user,
                "files": [f.get("name") for f in msg.files],
                "received_at": msg.received_at.isoformat(),
                "updated_at": msg.updated_at.isoformat(),
                "fires_at": msg.fires_at.isoformat(),
            }
        )
    return items


def _print_state(header: str) -> None:
    """Pretty-print the pending dict with a header."""
    now = _now()
    print()
    print("═" * 60)
    print(f"  {header}")
    print(f"  time: {now.isoformat()}")
    print(f"  pending: {len(pending)} item(s)")
    if pending:
        print(json.dumps(_pending_snapshot(), indent=2))
    print("═" * 60)
    print(flush=True)


async def _slack_api(method: str, payload: dict) -> dict:
    """Call a Slack API method. Returns the response JSON."""
    if not SLACK_BOT_TOKEN:
        print(f"  [warn] SLACK_BOT_TOKEN not set, skipping {method}", flush=True)
        return {"ok": False, "error": "no_token"}
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://slack.com/api/{method}",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json=payload,
        )
        data = resp.json()
        if not data.get("ok"):
            print(f"  [error] {method} failed: {json.dumps(data, indent=2)}", flush=True)
        return data


async def _slack_react(channel: str, ts: str, emoji: str) -> None:
    """Add an emoji reaction to a message."""
    await _slack_api("reactions.add", {"channel": channel, "timestamp": ts, "name": emoji})


async def _slack_reply(channel: str, thread_ts: str, text: str) -> None:
    """Post a threaded reply to Slack."""
    await _slack_api("chat.postMessage", {"channel": channel, "thread_ts": thread_ts, "text": text})


def _schedule_fire(channel: str, ts: str) -> asyncio.Task:
    """Schedule a timer fire for a pending message."""
    return asyncio.create_task(_on_timer_fire(channel, ts))


async def _on_timer_fire(channel: str, ts: str) -> None:
    """Called when a message's cooldown timer elapses."""
    await asyncio.sleep(COOLDOWN_SECONDS)
    key = (channel, ts)
    msg = pending.pop(key, None)
    if msg is None:
        return
    print(flush=True)
    print("🔔 " * 20, flush=True)
    print(f"  READY: channel={channel} ts={ts}", flush=True)
    print(f"  user={msg.user}", flush=True)
    print(f"  text={msg.text!r}", flush=True)
    print(f"  files={[f.get('name') for f in msg.files]}", flush=True)
    print("🔔 " * 20, flush=True)
    _print_state("After timer fire")

    file_names = [f.get("name") for f in msg.files]
    reply = f"Cooldown expired — no more edits will be accepted.\nProcessing: {msg.text!r}"
    if file_names:
        reply += f"\nFiles: {', '.join(file_names)}"
    await _slack_reply(channel, ts, reply)


# ── Event handlers ───────────────────────────────────────────────────


async def _handle_app_mention(event: dict) -> None:
    channel = event["channel"]
    ts = event["ts"]
    user = event.get("user", "unknown")
    raw_text = event.get("text", "")
    text = _strip_mention(raw_text)
    files = event.get("files", [])
    key = (channel, ts)

    # Cancel existing timer if re-mention (shouldn't happen, but safe)
    if key in pending and pending[key].timer:
        pending[key].timer.cancel()

    now = _now()
    fires_at = datetime.fromtimestamp(now.timestamp() + COOLDOWN_SECONDS, tz=timezone.utc)
    timer = _schedule_fire(channel, ts)

    pending[key] = PendingMessage(
        text=text,
        user=user,
        files=files,
        received_at=now,
        updated_at=now,
        fires_at=fires_at,
        timer=timer,
    )
    _print_state(f"EVENT: app_mention from {user} in {channel}")
    await _slack_react(channel, ts, "thumbsup")


async def _handle_message_changed(event: dict) -> None:
    channel = event["channel"]
    inner = event.get("message", {})
    ts = inner.get("ts", "")
    key = (channel, ts)

    if key not in pending:
        return  # Not tracking this message

    msg = pending[key]

    # Cancel old timer
    if msg.timer:
        msg.timer.cancel()

    raw_text = inner.get("text", msg.text)
    msg.text = _strip_mention(raw_text)
    msg.files = inner.get("files", msg.files)

    now = _now()
    msg.updated_at = now
    msg.fires_at = datetime.fromtimestamp(now.timestamp() + COOLDOWN_SECONDS, tz=timezone.utc)
    msg.timer = _schedule_fire(channel, ts)

    _print_state(f"EVENT: message_changed in {channel} ts={ts}")
    await _slack_react(channel, ts, "thumbsup")


async def _handle_thread_reply(event: dict) -> None:
    channel = event["channel"]
    thread_ts = event["thread_ts"]
    key = (channel, thread_ts)

    if key not in pending:
        return  # Not tracking the parent message

    msg = pending[key]

    # Cancel old timer
    if msg.timer:
        msg.timer.cancel()

    # Append text if present
    reply_text = event.get("text", "")
    if reply_text:
        msg.text = msg.text + "\n" + reply_text

    # Append files if present
    reply_files = event.get("files", [])
    msg.files.extend(reply_files)

    now = _now()
    msg.updated_at = now
    msg.fires_at = datetime.fromtimestamp(now.timestamp() + COOLDOWN_SECONDS, tz=timezone.utc)
    msg.timer = _schedule_fire(channel, thread_ts)

    _print_state(f"EVENT: thread_reply in {channel} thread_ts={thread_ts}")
    await _slack_react(channel, event["ts"], "thumbsup")


async def _handle_message_deleted(event: dict) -> None:
    channel = event["channel"]
    ts = event.get("deleted_ts", "")
    key = (channel, ts)

    if key not in pending:
        return  # Not tracking this message

    msg = pending.pop(key)
    if msg.timer:
        msg.timer.cancel()

    _print_state(f"EVENT: message_deleted in {channel} ts={ts}")


# ── FastAPI endpoint ─────────────────────────────────────────────────


@app.post("/event")
async def slack_event(request: Request) -> JSONResponse:
    body = await request.json()
    event_type = body.get("type")

    # URL verification challenge
    if event_type == "url_verification":
        challenge = body.get("challenge", "")
        print(f"URL verification challenge: {challenge}")
        return JSONResponse({"challenge": challenge})

    # Event callback
    if event_type == "event_callback":
        event = body.get("event", {})
        etype = event.get("type")
        subtype = event.get("subtype")

        # Ignore messages from our own bot
        if _is_bot_message(event):
            return JSONResponse({"ok": True})

        thread_ts = event.get("thread_ts")
        is_thread_reply = thread_ts is not None and event.get("ts") != thread_ts

        if is_thread_reply and etype == "message" and subtype in (None, "file_share"):
            # Thread reply (text or file) — check if parent is pending
            await _handle_thread_reply(event)
        elif etype == "app_mention":
            await _handle_app_mention(event)
        elif etype == "message" and subtype in (None, "file_share") and _is_bot_mention(event.get("text", "")):
            # Plain message or file_share with bot mention (from message.channels subscription)
            await _handle_app_mention(event)
        elif etype == "message" and subtype == "message_changed":
            await _handle_message_changed(event)
        elif etype == "message" and subtype == "message_deleted":
            await _handle_message_deleted(event)

    return JSONResponse({"ok": True})
