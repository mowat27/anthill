# Slack Server Design Notes

Findings from the spike that should inform the real Slack channel implementation.

## Dependencies

- **FastAPI + uvicorn** — async request handling, essential for debounce timers
- **httpx** — async HTTP client for calling Slack APIs from within async handlers
- **python-dotenv** — load `SLACK_BOT_TOKEN` and config from `.env` (keep tokens out of env vars on the command line)

## Slack App Setup

### Bot Token Scopes

| Scope | Purpose |
|---|---|
| `app_mentions:read` | Receive @mention events |
| `channels:history` | Receive message edits/deletes in public channels |
| `files:read` | Read file metadata and content |
| `chat:write` | Post messages as the bot |
| `reactions:write` | Add emoji reactions to messages |

### Event Subscriptions

Subscribe to **both**:
- **Bot events**: `app_mention`
- **Events on behalf of users**: `message.channels`

The `message.channels` subscription is what delivers edits (`message_changed`), deletes (`message_deleted`), and file shares. It also delivers regular messages — including ones with bot mentions — which means the same @mention can arrive as both an `app_mention` and a `message` event. The server must handle both paths.

## Slack Events API Envelope

All events arrive as POST requests with a JSON body. Two envelope types:

**URL verification** (one-time, when configuring the subscription URL):
```json
{"type": "url_verification", "challenge": "abc123"}
```
Respond with `{"challenge": "abc123"}`.

**Event callback** (all real events):
```json
{"type": "event_callback", "event": { ... }}
```
Respond with 200 OK promptly. Slack retries if response is slow.

## Event Routing

Events are distinguished by `event.type` and `event.subtype`:

| What happened | `event.type` | `event.subtype` | Key fields |
|---|---|---|---|
| Bot @mentioned | `app_mention` | — | `ts`, `channel`, `user`, `text`, `files` |
| Message with @mention | `message` | `None` or `file_share` | Same as above — check text for `<@BOT_ID>` |
| Message edited | `message` | `message_changed` | `message.ts`, `message.text` (nested) |
| Message deleted | `message` | `message_deleted` | `deleted_ts` |
| Thread reply (text) | `message` | `None` | `thread_ts` (parent), `ts` (reply) |
| Thread reply (file) | `message` | `file_share` | `thread_ts` (parent), `ts` (reply), `files` |
| File uploaded standalone | `message` | `file_share` | No `thread_ts` — separate message, no parent link |

### Bot mention detection

The `app_mention` event isn't always delivered (depending on subscription config). The `message.channels` subscription delivers the same message as `type: "message"` with no subtype. Check for bot mentions in both paths:

```python
# text contains "<@U0ADNA35YG2> some command"
def is_bot_mention(text: str) -> bool:
    return f"<@{BOT_USER_ID}>" in text
```

Strip the mention prefix to get the clean command text:
```python
re.sub(r"^\s*<@U[A-Z0-9]+>\s*", "", text)
```

### Thread reply detection

A thread reply has `thread_ts` pointing to the parent message, and its own `ts` differs from `thread_ts`:

```python
thread_ts = event.get("thread_ts")
is_thread_reply = thread_ts is not None and event.get("ts") != thread_ts
```

Check thread replies **before** checking for bot mentions in the routing logic — a thread reply to a pending message should be captured even if it doesn't @mention the bot.

### Bot self-message filtering

The bot's own replies arrive back as events. Filter them early to avoid infinite loops:

```python
def is_bot_message(event: dict) -> bool:
    return bool(event.get("bot_id"))
```

## File Attachment Behaviour

Key findings:
- **Files at send time**: When a user @mentions the bot and attaches files in the same message, the event includes a `files` array. This works.
- **Files cannot be added via edit**: Slack does not allow attaching files when editing a message.
- **Files in a separate message**: If a user uploads a file after the @mention (not in a thread), it arrives as a completely separate `message` event with its own `ts`, empty `text`, and **no reference to the parent message**. There is no way to reconcile it.
- **Files in a thread reply**: If a user replies in the thread with a file, the event has `thread_ts` pointing to the parent. This **can** be reconciled.

**Design implication**: Thread replies are the mechanism for adding files after the initial @mention. The server should accumulate text and files from thread replies into the pending message.

## Debounce Timer Implementation

### Use `asyncio.create_task`, not `call_later`

`loop.call_later()` with sync callbacks does not fire reliably under uvicorn. Use an async task with `asyncio.sleep` instead:

```python
def schedule_fire(channel: str, ts: str) -> asyncio.Task:
    return asyncio.create_task(_on_timer_fire(channel, ts))

async def _on_timer_fire(channel: str, ts: str) -> None:
    await asyncio.sleep(COOLDOWN_SECONDS)
    # ... process the message
```

The returned `asyncio.Task` supports `.cancel()` for resetting timers on edits and thread replies.

### Timer lifecycle

1. **@mention received** — create pending entry, start timer task
2. **Edit received** — cancel old timer task, update text, start new timer task
3. **Thread reply received** — cancel old timer task, append text/files, start new timer task
4. **Delete received** — cancel timer task, remove pending entry
5. **Timer fires** — pop pending entry, process the accumulated message

### Pending message store

Keyed by `(channel, ts)` where `ts` is the original @mention's timestamp:

```python
pending: dict[tuple[str, str], PendingMessage]
```

This key is stable across edits (the `ts` of the original message doesn't change) and thread replies (they reference it via `thread_ts`).

## Slack API Calls

Use `httpx.AsyncClient` for non-blocking HTTP from within async handlers:

```python
async def slack_api(method: str, payload: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://slack.com/api/{method}",
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json=payload,
        )
        return resp.json()
```

Two main operations:
- **Acknowledge** — `reactions.add` with emoji name (e.g. `"thumbsup"`) and the message `timestamp`
- **Reply** — `chat.postMessage` with `thread_ts` to post in the message thread

## Async Considerations

- All event handlers must be `async` to call Slack APIs without blocking the event loop
- Debounce timers run as background `asyncio.Task`s on the same event loop as the server
- Cancelling a task that is mid-sleep is clean — `asyncio.sleep` raises `CancelledError`
- Cancelled timer tasks that wake up and find their pending entry already removed (by a newer timer or a delete) should silently return
- `print()` output from background tasks may need `flush=True` to appear promptly in the uvicorn log
