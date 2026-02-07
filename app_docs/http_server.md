# HTTP Server

The Anthill HTTP server exposes workflows over HTTP using FastAPI. It accepts incoming requests, validates them against registered handlers, and dispatches workflow runs as background tasks.

## Architecture

The server is split into an orchestrator module and an `http/` package containing individual endpoint modules:

```
src/anthill/
    server.py              # Orchestrator: create_app(), _run_workflow(), module-level `app`
    http/
        __init__.py
        webhook.py         # POST /webhook endpoint
        slack_events.py    # POST /slack_event endpoint (see app_docs/slack.md)
```

`server.py` is responsible for:

1. Loading environment variables from `.env` via `python-dotenv`.
2. Loading the Anthill `App` from a Python file using `load_app()`.
3. Creating the `FastAPI` instance.
4. Delegating route registration to `setup_webhook_routes()` and `setup_slack_routes()`.
5. Providing the shared `_run_workflow()` helper used by both endpoint modules.

Each endpoint module exposes a `setup_*_routes(api, anthill_app)` function that registers its routes on the FastAPI instance. This keeps endpoint logic self-contained while the orchestrator controls composition.

## Factory Pattern

```python
def create_app(
    agents_file: str = os.environ.get("ANTHILL_AGENTS_FILE", "handlers.py"),
) -> FastAPI:
```

`create_app()` builds a fully configured FastAPI application:

1. Calls `dotenv.load_dotenv()` to load `.env` into the process environment.
2. Calls `load_app(agents_file)` to dynamically import the Python file and extract its `app` attribute (an `anthill.core.app.App` instance).
3. Creates a `FastAPI()` instance.
4. Calls `setup_webhook_routes(api, anthill_app)` and `setup_slack_routes(api, anthill_app)`.
5. Returns the configured `FastAPI` instance.

A module-level `app = create_app()` is defined so that uvicorn can reference `anthill.server:app` directly.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHILL_AGENTS_FILE` | `handlers.py` | Path to the Python file containing the Anthill `app` object. Read at import time by `create_app()`. When using the CLI `server` subcommand, the `--agents-file` flag writes to this env var before uvicorn starts. |

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

Defined as `WebhookRequest(BaseModel)` in `src/anthill/http/webhook.py`.

### Response

```json
{
    "run_id": "abc123-..."
}
```

| Field | Type | Description |
|---|---|---|
| `run_id` | `str` | Unique identifier for the background workflow run. |

Defined as `WebhookResponse(BaseModel)` in `src/anthill/http/webhook.py`.

### Error Responses

| Status | Condition |
|---|---|
| 404 | `workflow_name` does not match any registered handler. |

### Execution Flow

1. Validate `workflow_name` exists via `anthill_app.get_handler()`. Return 404 if not found.
2. Create an `ApiChannel` with the workflow name and initial state.
3. Create a `Runner` with the App and channel.
4. Add `_run_workflow(runner)` as a FastAPI background task.
5. Return the `run_id` immediately (HTTP 200).

## Background Task Pattern

Both `/webhook` and `/slack_event` use the shared `_run_workflow()` function to execute workflows:

```python
def _run_workflow(runner: Runner) -> None:
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
- For `/slack_event`, the task is run via `asyncio.to_thread(_run_workflow, runner)` inside an async timer callback, keeping the event loop unblocked.

## Starting the Server

### Via the Anthill CLI

```bash
anthill server --host 0.0.0.0 --port 8000 --agents-file handlers.py
```

| Flag | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Host address to bind. |
| `--port` | `8000` | Port number to bind. |
| `--reload` | off | Enable uvicorn auto-reload on code changes. |
| `--agents-file` | `handlers.py` | Path to the Python file containing the Anthill app. Sets `ANTHILL_AGENTS_FILE` before starting uvicorn. |

The CLI `server` subcommand sets the `ANTHILL_AGENTS_FILE` environment variable and then calls `uvicorn.run("anthill.server:app", ...)`.

### Via uvicorn directly

```bash
ANTHILL_AGENTS_FILE=handlers.py uvicorn anthill.server:app --host 0.0.0.0 --port 8000
```

Set `ANTHILL_AGENTS_FILE` in the environment (or in a `.env` file) before running.
