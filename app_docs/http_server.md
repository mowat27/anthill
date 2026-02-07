# HTTP Server

The Antkeeper HTTP server exposes workflows over HTTP using FastAPI. It accepts incoming requests, validates them against registered handlers, and dispatches workflow runs as background tasks.

## Architecture

The server follows the standard FastAPI pattern: `server.py` defines routes with `@api.post()` decorators and delegates implementation to library functions in the `http/` package:

```
src/antkeeper/
    server.py              # Entry point: create_app(), route definitions, module-level `app`
    http/
        __init__.py        # Shared utilities: run_workflow_background()
        webhook.py         # Webhook logic: handle_webhook()
        slack_events.py    # Slack logic: SlackEventProcessor class
```

`server.py` is responsible for:

1. Loading environment variables from `.env` via `python-dotenv`.
2. Loading the Antkeeper `App` from a Python file using `load_app()`.
3. Creating the `FastAPI` instance.
4. Defining all routes (`POST /webhook`, `POST /slack_event`) directly with `@api.post()` decorators.
5. Delegating each route's implementation to library functions in one line.

Each endpoint module in `http/` exports plain functions or classes that handle the route logic. This eliminates circular dependencies and makes route definitions visible at a glance in `server.py`.

## Factory Pattern

```python
def create_app(
    agents_file: str = os.environ.get("ANTKEEPER_HANDLERS_FILE", "handlers.py"),
) -> FastAPI:
```

`create_app()` builds a fully configured FastAPI application:

1. Calls `dotenv.load_dotenv()` to load `.env` into the process environment.
2. Calls `load_app(agents_file)` to dynamically import the Python file and extract its `app` attribute (an `antkeeper.core.app.App` instance).
3. Creates a `FastAPI()` instance and a `SlackEventProcessor(antkeeper_app)` instance.
4. Defines routes directly with `@api.post()` decorators inside `create_app()`, delegating to `handle_webhook()` and `slack.handle_event()`.
5. Returns the configured `FastAPI` instance.

A module-level `app = create_app()` is defined so that uvicorn can reference `antkeeper.server:app` directly.

### Route Definition Pattern

Routes are defined inline with decorator syntax:

```python
@api.post("/webhook", response_model=WebhookResponse)
async def webhook(request: WebhookRequest, background_tasks: BackgroundTasks):
    return await handle_webhook(request, background_tasks, antkeeper_app)

@api.post("/slack_event")
async def slack_event(request: Request):
    body = await request.json()
    return await slack.handle_event(body)
```

This makes all endpoints visible at the top level of `server.py`, matching the standard FastAPI pattern from the official docs.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTKEEPER_HANDLERS_FILE` | `handlers.py` | Path to the Python file containing the Antkeeper `app` object. Read at import time by `create_app()`. When using the CLI `server` subcommand, the `--agents-file` flag sets this env var before uvicorn starts. Previously named `ANTKEEPER_AGENTS_FILE` (renamed in v0.1.0). |

## POST /webhook

Generic endpoint for triggering any registered workflow.

### Request

```json
{
    "workflow_name": "my_workflow",
    "initial_state": {"key": "value"}
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `workflow_name` | `str` | Yes | Name of a registered handler on the App. |
| `initial_state` | `dict[str, Any]` | No | Initial state dictionary passed to the workflow. Defaults to `{}`. |

Defined as `WebhookRequest(BaseModel)` in `src/antkeeper/http/webhook.py`.

### Response

```json
{
    "run_id": "abc123-..."
}
```

| Field | Type | Description |
|---|---|---|
| `run_id` | `str` | Unique identifier for the background workflow run. |

Defined as `WebhookResponse(BaseModel)` in `src/antkeeper/http/webhook.py`.

### Error Responses

| Status | Condition |
|---|---|
| 404 | `workflow_name` does not match any registered handler. |

### Execution Flow

The route delegates to `handle_webhook()` in `webhook.py`:

1. Validate `workflow_name` exists via `antkeeper_app.get_handler()`. Raise 404 HTTPException if not found.
2. Create an `ApiChannel` with the workflow name and initial state.
3. Create a `Runner` with the App and channel.
4. Add `run_workflow_background(runner)` as a FastAPI background task.
5. Return the `run_id` immediately (HTTP 200).

## POST /slack_event

Slack Events API endpoint for receiving bot mentions and message events.

### Environment Variable Validation

The endpoint validates that required Slack environment variables are present before processing non-verification events:

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | Bot User OAuth Token (starts with `xoxb-`). |
| `SLACK_BOT_USER_ID` | Yes | Bot's Slack user ID (e.g. `U07ABC123`). |

**Validation behavior:**

- For `url_verification` requests: validation is skipped, allowing Slack to complete the initial app setup handshake even when environment variables are not yet configured.
- For all other event types: if either variable is missing or empty, the endpoint returns HTTP 422 with a diagnostic message listing the missing variables.

Example error response:

```json
{
    "detail": "Missing required environment variables: SLACK_BOT_TOKEN, SLACK_BOT_USER_ID"
}
```

The error message dynamically lists only the variables that are actually missing.

### Request

Slack sends JSON payloads with varying structures depending on event type. See the Slack Events API documentation for full schemas.

### Response

| Status | Condition | Body |
|---|---|---|
| 200 | URL verification | `{"challenge": "<value>"}` |
| 200 | Event processed | `{"ok": true}` |
| 422 | Missing env vars | `{"detail": "Missing required environment variables: ..."}` |

### Execution Flow

The route handler in `server.py` performs validation inline before delegating to `SlackEventProcessor.handle_event()`:

1. Parse request body as JSON.
2. Check if `body.type == "url_verification"`. If so, return challenge response immediately (skip env validation).
3. Check if `SLACK_BOT_TOKEN` and `SLACK_BOT_USER_ID` are present and non-empty. If either is missing, raise HTTPException 422 with diagnostic message.
4. Delegate to `slack.handle_event(body)` for event processing (bot filtering, debounce, workflow dispatch).

This design ensures that misconfigured deployments fail fast with clear error messages while preserving the URL verification flow that Slack requires during initial app setup.

## Background Task Pattern

Both `/webhook` and `/slack_event` use the shared `run_workflow_background()` function from `http/__init__.py` to execute workflows:

```python
def run_workflow_background(runner: Runner) -> None:
    try:
        runner.run()
    except WorkflowFailedError:
        pass
    except Exception as e:
        print(f"Unexpected error in workflow: {e}", file=sys.stderr)
```

Key behaviours:

- `WorkflowFailedError` is caught silently. This is an expected outcome when a workflow step signals failure.
- Any other exception is printed to stderr but does not propagate. This prevents background task crashes from affecting the HTTP server.
- For `/webhook`, the task is added via FastAPI's `BackgroundTasks` mechanism (runs in the same process after the response is sent).
- For `/slack_event`, the task is run via `asyncio.to_thread(run_workflow_background, runner)` inside an async timer callback, keeping the event loop unblocked.

### Why http/__init__.py?

Moving `run_workflow_background()` from `server.py` to `http/__init__.py` breaks the circular import that existed when `http/` modules imported back to `server.py`. Now `http/` modules import from their own package, and `server.py` imports from `http/` — a clean one-way dependency.

## Starting the Server

### Via the Antkeeper CLI

```bash
antkeeper server --host 0.0.0.0 --port 8000 --agents-file handlers.py
```

| Flag | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Host address to bind. |
| `--port` | `8000` | Port number to bind. |
| `--reload` | off | Enable uvicorn auto-reload on code changes. |
| `--agents-file` | `handlers.py` | Path to the Python file containing the Antkeeper app. Sets `ANTKEEPER_HANDLERS_FILE` before starting uvicorn. |

The CLI `server` subcommand sets the `ANTKEEPER_HANDLERS_FILE` environment variable and then calls `uvicorn.run("antkeeper.server:app", ...)`.

### Via uvicorn directly

```bash
ANTKEEPER_HANDLERS_FILE=handlers.py uvicorn antkeeper.server:app --host 0.0.0.0 --port 8000
```

Set `ANTKEEPER_HANDLERS_FILE` in the environment (or in a `.env` file) before running.
