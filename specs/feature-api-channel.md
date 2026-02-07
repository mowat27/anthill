# feature: API channel and webhook server with Runner.fail fix

- Add `ApiChannel` and FastAPI server with `POST /webhook` that runs workflows as background tasks, returns `run_id` immediately.
- BREAKING CHANGE: `Runner.fail()` raises `WorkflowFailedError` instead of `exit(1)`; CLI catches and exits, preserving behaviour.
- New `anthill server` CLI subcommand starts uvicorn with forwarded options.

## Solution Design

### External Interface Change

After this change, workflows can be triggered via HTTP in addition to CLI:

**HTTP usage:**
```
POST /webhook
Content-Type: application/json

{"workflow_name": "my_workflow", "initial_state": {"key": "value"}}

Response: {"run_id": "a1b2c3d4"}
```

**CLI server start:**
```bash
anthill server --host 0.0.0.0 --port 8000 --agents-file handlers.py
```

**CLI run (unchanged interface, new error handling):**
```bash
anthill run --agents-file handlers.py my_workflow
# On failure: prints error to stderr, exits 1 (same as before)
```

### Architectural Schema Changes

```yaml
types:
  WorkflowFailedError:
    kind: exception
    bases: [Exception]

  ApiChannel:
    kind: class
    constructor:
      - workflow_name: str
      - initial_state: State
    fields:
      - type: str  # "api"
      - workflow_name: str
      - initial_state: State
    methods:
      - report_progress(run_id: str, message: str, **opts: Any) -> None
      - report_error(run_id: str, message: str) -> None

  WebhookRequest:
    kind: pydantic_model
    fields:
      - workflow_name: str
      - initial_state: dict[str, Any]

  WebhookResponse:
    kind: pydantic_model
    fields:
      - run_id: str
```

### REST Changes

- `POST /webhook` — Accepts `WebhookRequest` body, validates workflow exists, creates Runner with ApiChannel, schedules `runner.run()` as a FastAPI background task, returns `WebhookResponse` with `run_id`. Returns 422 if body invalid. Returns 404 if workflow_name not found in app.

## Relevant Files

- `src/anthill/core/domain.py` — Add `WorkflowFailedError` exception alongside existing domain types.
- `src/anthill/core/runner.py` — Change `Runner.fail()` to raise `WorkflowFailedError` instead of `exit(1)`.
- `src/anthill/channels/cli.py` — Reference for channel implementation patterns. No changes needed.
- `src/anthill/cli.py` — Add `server` subcommand, catch `WorkflowFailedError` in `run` command, move `load_app` to remain importable by server.
- `pyproject.toml` — Add `fastapi` and `uvicorn[standard]` dependencies, add `httpx` to dev deps.
- `tests/core/test_workflows.py` — Update `test_failure` to expect `WorkflowFailedError` instead of `SystemExit`.
- `tests/conftest.py` — Reference for test patterns (TestChannel, runner_factory).

### New Files

- `src/anthill/channels/api.py` — `ApiChannel` implementing the Channel protocol with `type="api"`.
- `src/anthill/server.py` — FastAPI app with `POST /webhook` endpoint.
- `tests/channels/test_api_channel.py` — Unit tests for `ApiChannel`.
- `tests/test_server.py` — Tests for the server endpoint.

## Workflow

### Step 1: Add WorkflowFailedError and update Runner.fail()

- In `src/anthill/core/domain.py`, add `WorkflowFailedError(Exception)` — simple exception, no custom attributes.
- In `src/anthill/core/runner.py`, change `Runner.fail()`:
  - Remove `print(message, file=sys.stderr)` and `exit(1)`.
  - Replace with `raise WorkflowFailedError(message)`. Keep the existing `self.logger.error(...)` line.
  - Keep return type as `NoReturn` (a function that always raises satisfies `NoReturn`).
  - Import `WorkflowFailedError` from `anthill.core.domain`.
  - Remove `sys` import if no longer needed (check other usages first).

### Step 2: Update CLI to catch WorkflowFailedError

- In `src/anthill/cli.py`, in the `run` command block:
  - Wrap `runner.run()` in a try/except that catches `WorkflowFailedError`.
  - In the except block: `print(str(e), file=sys.stderr)` then `sys.exit(1)`.
  - This preserves the current CLI behaviour where users see the error on stderr and get exit code 1.
  - Import `WorkflowFailedError` from `anthill.core.domain`.

### Step 3: Update existing tests for Runner.fail() change

- In `tests/core/test_workflows.py`, update `test_failure`:
  - Change `pytest.raises(SystemExit)` to `pytest.raises(WorkflowFailedError)`.
  - Import `WorkflowFailedError` from `anthill.core.domain`.
  - Keep the assertion on `source.error_messages` — note that `fail()` no longer calls `report_error()`, so the test handler must call `report_error()` separately (which it already does on the line before `fail()`). The assertion `source.error_messages == ["something broke"]` still works because the handler calls `runner.report_error("something broke")` before `runner.fail("Workflow failed")`.

### Step 4: Add dependencies

- In `pyproject.toml`, add `fastapi` and `uvicorn[standard]` to `dependencies`.
- Add `httpx` to the `dev` dependency group (needed for FastAPI's `TestClient`).
- Run `uv sync`.

### Step 5: Create ApiChannel

- Create `src/anthill/channels/api.py`:
  - `ApiChannel` class with `type = "api"`.
  - Constructor takes `workflow_name: str` and `initial_state: dict[str, str] | None = None`, defaults to `{}` if None (same pattern as CliChannel).
  - `report_progress(self, run_id, message, **opts)`: `print(f"[{self.workflow_name}, {run_id}] {message}", flush=True)`.
  - `report_error(self, run_id, message)`: `self.report_progress(run_id, message, file=sys.stderr)` (same delegation pattern as CliChannel).
  - No module-level logger (per user instruction — output goes to Uvicorn's log stream).

### Step 6: Create server module

- Create `src/anthill/server.py`:
  - Import `FastAPI`, `BackgroundTasks`, `HTTPException` from `fastapi`.
  - Import `BaseModel` from `pydantic`.
  - Import `load_app` from `anthill.cli`.
  - Import `ApiChannel` from `anthill.channels.api`.
  - Import `Runner` from `anthill.core.runner`.
  - Import `WorkflowFailedError` from `anthill.core.domain`.
  - Define Pydantic models:
    - `WebhookRequest(BaseModel)` with `workflow_name: str` and `initial_state: dict[str, Any] = {}`.
    - `WebhookResponse(BaseModel)` with `run_id: str`.
  - Define `_run_workflow(runner: Runner) -> None` function:
    - Calls `runner.run()` inside a try/except.
    - Catches `WorkflowFailedError`: pass (already logged by Runner).
    - Catches `Exception`: `print(f"Unexpected error in workflow: {e}", file=sys.stderr)`.
  - Define `create_app(agents_file: str = "handlers.py") -> FastAPI`:
    - Loads app via `load_app(agents_file)`.
    - Creates `FastAPI()` instance.
    - Defines `POST /webhook` endpoint inside the factory:
      - Accepts `WebhookRequest` body and `BackgroundTasks`.
      - Validates workflow exists: call `anthill_app.get_handler(request.workflow_name)`. If `ValueError` raised, return `HTTPException(status_code=404, detail=f"Unknown workflow: {request.workflow_name}")`.
      - Creates `ApiChannel(request.workflow_name, request.initial_state)`.
      - Creates `Runner(anthill_app, channel)`.
      - Adds `_run_workflow(runner)` as background task.
      - Returns `WebhookResponse(run_id=runner.id)`.
    - Returns the FastAPI instance.
  - At module level: `app = create_app()` — this is what uvicorn imports.

### Step 7: Add server CLI subcommand

- In `src/anthill/cli.py`:
  - Add `server` subparser: `server_parser = subparsers.add_parser("server")`.
  - Add arguments: `--host` (default `"127.0.0.1"`), `--port` (type=int, default `8000`), `--reload` (action `"store_true"`), `--agents-file` (default `"handlers.py"`).
  - In the command dispatch block, add `elif args.command == "server":`.
  - Import uvicorn inside the block: `import uvicorn`.
  - Call `uvicorn.run("anthill.server:app", host=args.host, port=args.port, reload=args.reload)`.
  - Note: `--agents-file` for the server subcommand needs to reach `create_app()`. Use an environment variable: `os.environ["ANTHILL_AGENTS_FILE"] = args.agents_file` before calling `uvicorn.run()`. Update `create_app()` default: `create_app(agents_file: str = os.environ.get("ANTHILL_AGENTS_FILE", "handlers.py"))`.

### Step 8: Write ApiChannel tests

- Create `tests/channels/test_api_channel.py` following the pattern in `test_cli_channel.py`.

### Step 9: Write server tests

- Create `tests/test_server.py` using FastAPI's `TestClient` from `httpx`.

### Step 10: Run validation commands

- Run all validation commands and fix any issues to zero errors.

## Testing Strategy

### Unit Tests

**ApiChannel** (`tests/channels/test_api_channel.py`):
- `test_api_channel_type` — `ApiChannel("wf").type == "api"`.
- `test_api_channel_initial_state` — Parametrized: `({"k": "v"}, {"k": "v"})` and `(None, {})`. Same pattern as `test_cli_channel.py`.
- `test_report_progress_prints_to_stdout` — Call `report_progress("id", "msg")`, capture with `capsys`, assert format `[workflow_name, id] msg`.
- `test_report_error_prints_to_stderr` — Call `report_error("id", "msg")`, capture with `capsys`, assert output on stderr.

**Runner.fail()** (`tests/core/test_workflows.py`):
- `test_failure` — MODIFY EXISTING: change `pytest.raises(SystemExit)` to `pytest.raises(WorkflowFailedError)`. Keep assertion on `source.error_messages`.

**Server endpoint** (`tests/test_server.py`):
- `test_webhook_returns_run_id` — POST valid request, assert 200, assert `run_id` in response JSON.
- `test_webhook_unknown_workflow_returns_404` — POST with unknown workflow_name, assert 404 response.
- `test_webhook_invalid_body_returns_422` — POST with missing workflow_name, assert 422 response.

### Integration

**CLI run command** (`tests/test_cli.py`):
- `test_run_command_catches_workflow_failed_error` — Create a handler that calls `runner.fail()`, run via CLI with monkeypatch, assert `SystemExit` with code 1 and error on stderr.

### Edge Cases

- `ApiChannel` with `None` initial_state defaults to empty dict.
- POST `/webhook` with empty `initial_state` (defaults to `{}`).
- POST `/webhook` with non-existent `workflow_name` returns 404 before scheduling background task.
- Background task handles `WorkflowFailedError` without crashing the server.
- Background task handles unexpected exceptions without crashing the server.

## Acceptance Criteria

- `WorkflowFailedError` is defined in `src/anthill/core/domain.py`.
- `Runner.fail()` raises `WorkflowFailedError` instead of calling `exit(1)`.
- CLI `run` command catches `WorkflowFailedError`, prints to stderr, exits 1 (same observable behaviour as before).
- `ApiChannel` implements the Channel protocol with `type="api"` and print-based reporting.
- `POST /webhook` accepts `workflow_name` and `initial_state`, returns `run_id`, runs workflow in background.
- `POST /webhook` returns 404 for unknown workflow names.
- `anthill server` starts uvicorn with `--host`, `--port`, `--reload`, `--agents-file` options.
- All existing tests pass (with `test_failure` updated for new exception type).
- New tests pass for ApiChannel, server endpoint, and CLI error handling.
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

- **BackgroundTasks limitation**: FastAPI's `BackgroundTasks` runs in the same process after the response. For long-running workflows, this blocks a worker thread. This is acceptable for the initial implementation; production deployments can use `uvicorn anthill.server:app` with multiple workers.
- **Agents file propagation**: The `--agents-file` CLI option is passed to `create_app()` via the `ANTHILL_AGENTS_FILE` environment variable, since `uvicorn.run()` imports the module string `"anthill.server:app"` and the factory needs the path at import time.
- **BREAKING CHANGE**: `Runner.fail()` no longer calls `exit(1)`. Any code that caught `SystemExit` from `fail()` must now catch `WorkflowFailedError`. This is intentional and backwards compatibility is explicitly not required.
- **No module-level logger in ApiChannel**: Per user instruction, ApiChannel uses plain `print()` statements. Output appears in Uvicorn's log stream.
- **Pydantic models**: Used for `WebhookRequest`/`WebhookResponse` because FastAPI's request validation and OpenAPI docs generation depend on them. Pydantic is a transitive dependency of FastAPI.
- **Server module uses factory pattern**: `create_app()` returns a configured FastAPI instance. This makes the server testable — tests can call `create_app()` with a custom agents file pointing to test handlers.

## Report

Files changed: `src/anthill/core/domain.py` (add WorkflowFailedError), `src/anthill/core/runner.py` (fail raises exception), `src/anthill/cli.py` (catch exception + server subcommand), `pyproject.toml` (add fastapi, uvicorn, httpx), `tests/core/test_workflows.py` (update test_failure). Files created: `src/anthill/channels/api.py` (ApiChannel), `src/anthill/server.py` (FastAPI app + webhook endpoint), `tests/channels/test_api_channel.py` (4 tests), `tests/test_server.py` (3 tests). Tests added: 4 ApiChannel unit tests, 3 server endpoint tests, 1 CLI integration test. Validations: pytest, ruff, ty, just.
