# feature: Slack channel with debounce and thread-aware replies

- Add `SlackChannel` that posts handler progress/error messages to the originating Slack thread via `httpx.Client`.
- Add `POST /slack_event` endpoint with debounce timer — accumulates edits and thread replies before dispatching to a workflow handler.
- Server sends Slack acknowledgements (reactions on receive, thread message on timer fire); handlers reply via `runner.report_progress()`.

## Solution Design

### External Interface Change

After this change, workflows can be triggered from Slack in addition to CLI and HTTP webhook:

**Slack usage:**
1. User @mentions the bot in a Slack channel: `@Anthill my_workflow do something`
2. Bot adds a thumbsup reaction acknowledging receipt
3. User can edit the message or reply in the thread with more text/files within the cooldown window (default 30s) — each action resets the timer
4. When the cooldown expires, the bot posts "Processing your request..." in the thread and dispatches to the `my_workflow` handler
5. Handler calls `runner.report_progress("Step 1 done")` — message appears in the Slack thread
6. Handler calls `runner.report_error("Something went wrong")` — error-formatted message appears in the Slack thread

**CLI start:**
```bash
anthill slack-server --host 0.0.0.0 --port 8000 --agents-file handlers.py
```

Requires `.env` file with `SLACK_BOT_TOKEN` and `SLACK_BOT_USER_ID`.

**Existing channels (unchanged):**
- `CliChannel` — `report_progress`/`report_error` write to stdout/stderr
- `ApiChannel` — `report_progress`/`report_error` write to stdout/stderr (server logs)
- `SlackChannel` — `report_progress`/`report_error` post to the originating Slack thread

### Architectural Schema Changes

```yaml
types:
  PendingMessage:
    kind: dataclass
    fields:
      - channel_id: str
      - ts: str
      - user: str
      - text: str
      - files: list[dict]
      - workflow_name: str
      - timer_task: asyncio.Task | None

  SlackChannel:
    kind: class
    constructor:
      - workflow_name: str
      - initial_state: State | None
      - slack_token: str
      - channel_id: str
      - thread_ts: str
    fields:
      - type: str  # "slack"
      - workflow_name: str
      - initial_state: State
    methods:
      - report_progress(run_id: str, message: str, **opts: Any) -> None
      - report_error(run_id: str, message: str) -> None
```

### REST Changes

- `POST /slack_event` — Receives Slack Events API payloads. Handles `url_verification` (returns challenge). For `event_callback` envelopes: routes bot mentions to pending message store with debounce timer, handles edits/deletes/thread replies, dispatches workflow on timer fire. Always returns 200 promptly.

## Relevant Files

- `src/anthill/core/domain.py` — Defines `Channel` protocol. SlackChannel must satisfy this. **No changes needed.**
- `src/anthill/core/runner.py` — Runner delegates `report_progress`/`report_error` to channel. **No changes needed.**
- `src/anthill/core/app.py` — App handler registry, `run_workflow`. **No changes needed.**
- `src/anthill/channels/api.py` — Reference for channel implementation pattern (constructor, type, report methods).
- `src/anthill/channels/cli.py` — Reference for channel implementation pattern (logging, delegation).
- `src/anthill/server.py` — Existing webhook server. Refactored: webhook logic moves to `http/webhook.py`, `create_app` becomes a clean orchestrator calling `setup_*` functions. `_run_workflow` stays here as shared infrastructure. **Modified.**
- `src/anthill/cli.py` — CLI entry point. Add `slack-server` subcommand. Update `server` subcommand uvicorn target if needed.
- `pyproject.toml` — Add `httpx` and `python-dotenv` to main dependencies.
- `tests/conftest.py` — Reference for `TestChannel`, `app` fixture, `runner_factory` patterns.
- `tests/channels/test_api_channel.py` — Reference for channel unit test patterns.
- `tests/test_server.py` — Existing server tests. Keep importing from `anthill.server` (unchanged). **No changes needed.**

### New Files

- `src/anthill/http/__init__.py` — Package init (can be empty or re-export setup functions).
- `src/anthill/http/webhook.py` — `setup_webhook_routes(api, anthill_app)` — existing `/webhook` endpoint logic extracted from `server.py`.
- `src/anthill/http/slack_events.py` — `setup_slack_routes(api, anthill_app)` — Slack event routing, pending message store, debounce timer logic.
- `src/anthill/channels/slack.py` — `SlackChannel` implementing the Channel protocol.
- `tests/channels/test_slack_channel.py` — Unit tests for SlackChannel.
- `tests/test_slack_server.py` — Integration tests for the Slack event endpoint.

## Workflow

### Step 1: Add dependencies

- In `pyproject.toml`, add `httpx` and `python-dotenv` to the `dependencies` list (main, not dev). `httpx` is needed at runtime for SlackChannel's Slack API calls and for the server's Slack API calls. `python-dotenv` loads `SLACK_BOT_TOKEN` from `.env`.
- Note: `httpx` remains in dev deps too (needed for FastAPI TestClient).
- Run `uv sync`.

### Step 2: Create SlackChannel

- Create `src/anthill/channels/slack.py`.
- `SlackChannel` class satisfying the `Channel` protocol:
  - Constructor: `(workflow_name: str, initial_state: State | None = None, *, slack_token: str, channel_id: str, thread_ts: str)`.
  - `self.type = "slack"`.
  - `self.workflow_name = workflow_name`.
  - `self.initial_state: State = {**(initial_state or {})}` — same pattern as CliChannel/ApiChannel.
  - Store `_slack_token`, `_channel_id`, `_thread_ts` as private attributes.
  - Create a module-level logger: `logger = logging.getLogger("anthill.channels.slack")`.
  - Log at construction: `logger.debug(f"SlackChannel initialized: channel={channel_id}, thread_ts={thread_ts}")`.
  - Private method `_post_to_thread(self, text: str) -> None`: uses sync `httpx.Client` (not async) to POST to `https://slack.com/api/chat.postMessage` with JSON body `{"channel": self._channel_id, "thread_ts": self._thread_ts, "text": text}` and header `Authorization: Bearer {self._slack_token}`. Wrap in try/except for `httpx.HTTPError` — log the error via `logger.error()` but do NOT re-raise (Slack API failures must not crash the workflow).
  - `report_progress(self, run_id, message, **opts)`: calls `self._post_to_thread(f"[{self.workflow_name}, {run_id}] {message}")`. Logs via `logger.debug()`.
  - `report_error(self, run_id, message)`: calls `self._post_to_thread(f"[{self.workflow_name}, {run_id}] [ERROR] {message}")`. Logs via `logger.debug()`.

**Key design choice — sync `httpx.Client` not async:** The Channel protocol methods are synchronous. Handlers call `runner.report_progress()` synchronously. When the Slack server dispatches a workflow via `BackgroundTasks`, FastAPI runs the sync function in a threadpool. From that thread, sync HTTP calls via `httpx.Client` work correctly with no event loop juggling. This avoids the complexity of creating new event loops or bridging async/sync.

**Key design choice — thread context captured at construction:** The `_channel_id` and `_thread_ts` are set once when the SlackChannel is created (from the original @mention's channel and timestamp). Every `report_progress`/`report_error` call uses these values to post to the correct Slack thread. No changes to the Channel protocol or Runner needed.

**Key design choice — HTTP errors caught, not propagated:** Per design philosophy, the channel is an I/O boundary. A transient Slack API failure should not crash the handler. Log and continue.

### Step 3: Create `http` package and refactor server

This step extracts endpoint logic into an `http` package and adds the Slack endpoint.

#### 3a: Create `src/anthill/http/__init__.py`

Empty file (or re-export setup functions for convenience).

#### 3b: Create `src/anthill/http/webhook.py`

Extract the existing `/webhook` endpoint from `server.py` into a `setup_webhook_routes(api, anthill_app)` function:
- Move `WebhookRequest`, `WebhookResponse` models here.
- Move the `POST /webhook` handler here, registering it on the passed `api` instance.
- Import `_run_workflow` from `anthill.server`.

#### 3c: Create `src/anthill/http/slack_events.py`

This module contains Slack event handling logic: event routing, pending message store, debounce timers, Slack API calls for acknowledgements, and the `setup_slack_routes` function.

**Helper functions (module-level):**

- `is_bot_message(event: dict) -> bool`: returns `bool(event.get("bot_id"))`.
- `is_bot_mention(text: str, bot_user_id: str) -> bool`: returns `f"<@{bot_user_id}>" in text`.
- `strip_mention(text: str) -> str`: uses `re.sub(r"^\s*<@U[A-Z0-9]+>\s*", "", text)` to strip the mention prefix and return clean text.

**`PendingMessage` dataclass:**
- Fields: `channel_id: str`, `ts: str`, `user: str`, `text: str`, `files: list[dict]`, `workflow_name: str`, `timer_task: asyncio.Task | None`.

**`async def slack_api(token: str, method: str, payload: dict) -> dict`:**
- Uses `httpx.AsyncClient` to POST to `https://slack.com/api/{method}` with `Authorization: Bearer {token}` header and JSON payload. Returns response JSON.
- This is used by the async server endpoint for Slack acknowledgements (reactions, "Processing..." message). It is separate from the sync `httpx.Client` used by `SlackChannel`.

**`setup_slack_routes(api: FastAPI, anthill_app: App) -> None`:**
- Initializes `pending: dict[tuple[str, str], PendingMessage] = {}` — scoped to the closure, not module-level. Each `setup_slack_routes()` call gets its own store (enables test isolation).
- Registers `POST /slack_event` endpoint on the provided `api` FastAPI instance.
- `SLACK_BOT_TOKEN`, `SLACK_BOT_USER_ID`, and `SLACK_COOLDOWN_SECONDS` (default `30`) are read from `os.environ` at request time inside the endpoint handler, not at setup time.

#### 3d: Refactor `server.py`

`server.py` becomes a clean orchestrator:

```python
def create_app(agents_file: str = ...) -> FastAPI:
    anthill_app = load_app(agents_file)
    api = FastAPI()
    setup_webhook_routes(api, anthill_app)
    setup_slack_routes(api, anthill_app)
    return api
```

- `_run_workflow` stays in `server.py` as shared infrastructure (imported by both `http/webhook.py` and `http/slack_events.py`).
- Existing imports (`from anthill.server import create_app`) continue to work — no breaking changes to tests or CLI.

#### 3e: `POST /slack_event` endpoint (registered by `setup_slack_routes`)
- Accepts raw JSON via `request: Request` then `body = await request.json()`. NOT a Pydantic model — Slack event payloads vary in shape.
- Routing order (matching spike design):

  1. **URL verification**: If `body.get("type") == "url_verification"`, return `{"challenge": body["challenge"]}`.
  2. Extract `event = body.get("event", {})`. If no event, return 200.
  3. **Bot self-filter**: If `is_bot_message(event)`, return 200.
  4. Extract `channel_id = event.get("channel", "")` and `event_ts = event.get("ts", "")`.
  5. **Thread reply** (checked BEFORE mention per spike findings): If `event.get("thread_ts")` exists and `event["ts"] != event["thread_ts"]`, look up `key = (channel_id, event["thread_ts"])` in `pending`. If found: cancel `entry.timer_task`, append reply text/files to entry, restart timer. Add reaction to the reply via `slack_api(token, "reactions.add", ...)`. Return 200. If not found (timer already fired or not our thread): return 200.
  6. **Message edit**: If `event.get("subtype") == "message_changed"`, extract `nested = event.get("message", {})`. Look up `key = (channel_id, nested.get("ts", ""))` in `pending`. If found: cancel timer, replace `entry.text` with `nested.get("text", "")`, apply `strip_mention` again to get clean text, restart timer. Return 200.
  7. **Message delete**: If `event.get("subtype") == "message_deleted"`, look up `key = (channel_id, event.get("deleted_ts", ""))` in `pending`. If found: cancel timer, remove entry. Return 200.
  8. **Bot mention** (new message): For events where `event.get("type")` is `"app_mention"` or `"message"` (with no subtype or subtype `"file_share"`), check `is_bot_mention(event.get("text", ""), bot_user_id)`. If mention detected:
     - Strip mention to get clean text.
     - Extract workflow name as first word of clean text (e.g. `"my_workflow do stuff"` → `"my_workflow"`).
     - Create `PendingMessage(channel_id=channel_id, ts=event_ts, user=event.get("user", ""), text=clean_text, files=event.get("files", []), workflow_name=workflow_name, timer_task=None)`.
     - Store in `pending[(channel_id, event_ts)]`. If key already exists (duplicate event from both `app_mention` and `message`), skip.
     - Add thumbsup reaction: `await slack_api(token, "reactions.add", {"channel": channel_id, "timestamp": event_ts, "name": "thumbsup"})`.
     - Start debounce timer: `entry.timer_task = asyncio.create_task(_on_timer_fire(key))`.
     - Return 200.
  9. All other events: return 200.

**Debounce timer:**
- `async def _on_timer_fire(key: tuple[str, str])` (defined inside `setup_slack_routes` closure so it can access `pending`, `slack_token`, `anthill_app`, `cooldown`):
  - `await asyncio.sleep(cooldown)`.
  - `entry = pending.pop(key, None)`. If `None`, return (deleted or already processed).
  - Post "Processing your request..." in the thread: `await slack_api(token, "chat.postMessage", {"channel": entry.channel_id, "thread_ts": entry.ts, "text": "Processing your request..."})`.
  - Validate workflow exists: try `anthill_app.get_handler(entry.workflow_name)`. If `ValueError`, post error reply in thread listing available workflows and return.
  - Build initial state: `{"prompt": entry.text, "slack_user": entry.user}`. If `entry.files`, add `"files": entry.files`.
  - Create `SlackChannel(workflow_name=entry.workflow_name, initial_state=initial_state, slack_token=token, channel_id=entry.channel_id, thread_ts=entry.ts)`.
  - Create `Runner(anthill_app, channel)`.
  - Run workflow: call `_run_workflow(runner)` (imported from `anthill.server`). This is sync, so run via `asyncio.to_thread(_run_workflow, runner)` to avoid blocking the event loop.

### Step 4: Add `slack-server` CLI subcommand

- In `src/anthill/cli.py`:
  - Add `slack_server_parser = subparsers.add_parser("slack-server")`.
  - Arguments: `--host` (default `"127.0.0.1"`), `--port` (type=int, default `8000`), `--reload` (action `"store_true"`), `--agents-file` (default `"handlers.py"`).
  - In command dispatch, add `elif args.command == "slack-server":`.
  - Import uvicorn and `dotenv` inside the block.
  - Call `dotenv.load_dotenv()` — this loads `SLACK_BOT_TOKEN` and `SLACK_BOT_USER_ID` from `.env` into `os.environ`.
  - Set `os.environ["ANTHILL_AGENTS_FILE"] = args.agents_file`.
  - Call `uvicorn.run("anthill.server:app", host=args.host, port=args.port, reload=args.reload)`.
- Update the `main()` docstring to document the new subcommand.

### Step 5: Write SlackChannel tests

- Create `tests/channels/test_slack_channel.py` following the pattern from `test_api_channel.py`.
- Class `TestSlackChannel`:

  - `test_slack_channel_type`: Instantiate `SlackChannel("wf", slack_token="t", channel_id="C1", thread_ts="123.456")`. Assert `channel.type == "slack"`.
  - `test_slack_channel_initial_state` (parametrized): `({"k": "v"}, {"k": "v"})` and `(None, {})`. Assert `channel.initial_state == expected`.
  - `test_report_progress_posts_to_slack_thread`: Mock `httpx.Client.post` (via `unittest.mock.patch`). Call `channel.report_progress("run1", "step done")`. Assert the mock was called with the correct URL, headers (token), and JSON body containing `channel`, `thread_ts`, and `text`.
  - `test_report_error_posts_error_formatted_message`: Same mock setup. Call `channel.report_error("run1", "broke")`. Assert JSON body `text` contains `[ERROR]`.
  - `test_report_progress_survives_http_failure`: Mock `httpx.Client.post` to raise `httpx.HTTPError`. Call `channel.report_progress(...)`. Assert no exception raised (error is swallowed and logged).

### Step 6: Write Slack server tests

- Create `tests/test_slack_server.py` using FastAPI TestClient.
- Fixture `slack_client`: creates temp-dir `App` with a test handler, patches env vars (`SLACK_BOT_TOKEN`, `SLACK_BOT_USER_ID`, `SLACK_COOLDOWN_SECONDS=0`), calls `create_app(agents_path)`, yields `TestClient(api)`. Setting cooldown to 0 makes tests deterministic. Mock `slack_api` to capture calls without hitting real Slack.

  - `test_url_verification_returns_challenge`: POST `{"type": "url_verification", "challenge": "abc123"}`. Assert 200 and `{"challenge": "abc123"}` in response.
  - `test_bot_self_message_ignored`: POST event with `bot_id` set. Assert 200, no pending entry, no timer started.
  - `test_bot_mention_creates_pending_and_acknowledges`: POST an `app_mention` event with text `"<@U_BOT> greet hello"`. Assert 200, `reactions.add` was called (thumbsup), pending entry exists.
  - `test_duplicate_event_deduplication`: POST same mention event twice (same `channel` + `ts`). Assert only one pending entry.
  - `test_message_edit_updates_pending_text`: POST mention, then `message_changed` event with new text. Assert pending entry text is updated.
  - `test_thread_reply_appends_to_pending`: POST mention, then thread reply. Assert pending text includes appended content.
  - `test_thread_reply_with_files_appends_files`: POST mention, then thread reply with `files` array. Assert pending files list is extended.
  - `test_message_delete_removes_pending`: POST mention, then `message_deleted` event. Assert pending entry removed, timer cancelled.
  - `test_timer_fire_dispatches_workflow`: With cooldown=0, POST mention event. Wait briefly for timer. Assert "Processing..." was posted, handler was invoked (via side effect in test handler).
  - `test_unknown_workflow_posts_error`: POST mention with workflow name not in app. Wait for timer. Assert error reply posted to thread.
  - `test_unknown_event_type_returns_200`: POST unhandled event type. Assert 200, no errors.
  - `test_thread_reply_without_pending_parent_ignored`: POST thread reply with `thread_ts` not in pending store. Assert 200, no error.

### Step 7: Run validation commands

- Run all validation commands and fix any issues to zero errors.

## Testing Strategy

### Unit Tests

**SlackChannel** (`tests/channels/test_slack_channel.py`):
- Channel type identifier is `"slack"`
- Initial state handling (parametrized: provided dict and None)
- `report_progress` sends correct Slack API payload (channel, thread_ts, text with progress format)
- `report_error` sends correct Slack API payload (text with `[ERROR]` format)
- HTTP failures in `report_*` are caught and logged, not propagated

**Key mock approach:** Patch `httpx.Client.post` to intercept HTTP calls. No real Slack API calls.

### Integration

**Slack server** (`tests/test_slack_server.py`):
- URL verification returns challenge
- Bot self-messages filtered (no pending entry)
- Mention → pending entry + reaction acknowledgement
- Edit → pending text updated, timer reset
- Thread reply → text/files appended, timer reset
- Delete → pending entry removed, timer cancelled
- Timer fire → workflow dispatched with SlackChannel
- Unknown workflow → error posted to thread
- Duplicate event deduplication

**Key mock approach:** Patch `slack_api` helper to capture calls. Set `SLACK_COOLDOWN_SECONDS=0` for deterministic timer behaviour. Use `asyncio.sleep(0.1)` in tests to allow timer tasks to complete.

### Edge Cases

- Thread reply arrives after timer fired (parent not in pending) — silently ignored
- HTTP failure during Slack acknowledgement (reaction) — logged, does not prevent workflow dispatch
- Empty message text after stripping mention — workflow name extraction handles gracefully
- Multiple rapid edits within cooldown — only final text is used
- `file_share` subtype with bot mention — treated as mention with files

## Acceptance Criteria

- `SlackChannel` satisfies the `Channel` protocol with `type="slack"` and posts to Slack threads.
- `report_progress` and `report_error` post to the correct Slack thread using the `channel_id` and `thread_ts` captured at construction.
- HTTP failures in `report_*` are caught and logged, never crash the workflow.
- `POST /slack_event` handles URL verification, bot filtering, mention detection, edits, thread replies, and deletes.
- Debounce timer accumulates edits and thread replies before dispatching.
- Reactions are added on message receipt; "Processing..." message is posted on timer fire.
- Handlers interact with Slack solely via `runner.report_progress()` and `runner.report_error()` — no Slack-specific APIs needed in handler code.
- Unknown workflow names produce an error reply in the Slack thread.
- `anthill slack-server` CLI subcommand starts the Slack server with `--host`, `--port`, `--reload`, `--agents-file` options.
- Core files (`domain.py`, `runner.py`, `app.py`) are not modified.
- All existing tests pass unchanged.
- New tests pass.
- Type checks pass.
- Linting passes.

### Validation Commands

```bash
# Install dependencies
uv sync

# Run all tests
uv run -m pytest tests/ -v

# Type check
uv run ty check

# Lint
uv run ruff check

# Run all checks via justfile
just
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- **Sync httpx in SlackChannel, async httpx in server:** The channel uses sync `httpx.Client` because handler code is synchronous (runs in threadpool via `BackgroundTasks`). The server endpoint uses async `httpx.AsyncClient` because it runs on the async event loop. These are independent — the channel never shares an HTTP client with the server.
- **Pending store is closure-scoped:** The `pending` dict is created inside `setup_slack_routes()` and captured by the endpoint closure. Each call to `setup_slack_routes()` gets a fresh store. This enables test isolation without module-level mutable state.
- **Cooldown of 0 in tests:** Setting `SLACK_COOLDOWN_SECONDS=0` makes the timer fire immediately after `asyncio.sleep(0)`, which yields control once and then processes. Tests use a brief `asyncio.sleep(0.1)` to allow the timer task to complete.
- **No thread safety concerns:** The pending store is accessed only from async handlers on FastAPI's single-threaded event loop. Asyncio is cooperative — no concurrent access within a single coroutine execution. No locks needed.
- **Duplicate event suppression:** Slack sends both `app_mention` and `message` events for the same @mention. The `(channel_id, ts)` key naturally deduplicates — the second event finds the key already exists and skips.
- **Bot user ID vs bot_id:** `SLACK_BOT_USER_ID` (e.g. `U0ADNA35YG2`) is used for mention detection in message text. `event.get("bot_id")` is used to filter the bot's own outgoing messages. These are different Slack identifiers.
- **Workflow name extraction:** First word of cleaned mention text. If the first word doesn't match a registered handler, an error is posted to the thread when the timer fires. The handler is NOT invoked.

## Report

Files changed: `src/anthill/server.py` (refactored to orchestrator, delegates to `http` package), `src/anthill/cli.py` (add `slack-server` subcommand), `pyproject.toml` (add `httpx` and `python-dotenv` to main deps). Files created: `src/anthill/http/__init__.py`, `src/anthill/http/webhook.py` (extracted from `server.py`), `src/anthill/http/slack_events.py` (Slack event routing, pending store, debounce, `setup_slack_routes`), `src/anthill/channels/slack.py` (SlackChannel), `tests/channels/test_slack_channel.py` (5 tests), `tests/test_slack_server.py` (12 tests). Tests added: 17 total. Validations: pytest, ruff, ty, just. Core unchanged: domain.py, runner.py, app.py.
