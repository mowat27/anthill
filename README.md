# Anthill

A lightweight Python workflow engine. Define handlers (workflow steps) via a decorator-based `App`, wire them to a `Channel` (I/O boundary), and execute through a `Runner`. Designed for composable, testable pipelines.

## Requirements

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) package manager

## Quickstart

```bash
# Install dependencies
uv sync

# Run a workflow via CLI
anthill run --agents-file handlers.py --initial-state result=5 plus_1

# Run an LLM workflow with prompt and model
anthill run --prompt "describe this project" --model sonnet specify

# Run with prompt from file (mutually exclusive with --prompt)
anthill run --prompt-file prompts/describe.md --model sonnet specify

# Start an API server to trigger workflows via HTTP
anthill server --host 0.0.0.0 --port 8000 --agents-file handlers.py

# Use just recipes for common workflows
just sdlc "Add authentication" opus           # Standard SDLC workflow
just sdlc_iso "Add dark mode" opus           # Isolated SDLC in git worktree
```

## Project Structure

```
src/anthill/
├── core/               # Framework kernel
│   ├── domain.py       # State type alias, Channel protocol, WorkflowFailedError
│   ├── app.py          # App handler registry, run_workflow helper
│   └── runner.py       # Runner execution engine
├── channels/
│   ├── cli.py          # CLI channel adapter (stdout/stderr reporting)
│   └── api.py          # API channel adapter (server logging)
├── git/                # Git worktree integration
│   └── worktrees.py    # Worktree class, git_worktree context manager
├── helpers/
│   └── json.py         # JSON extraction utilities
├── llm/                # LLM agent abstraction layer
│   ├── __init__.py     # Agent protocol
│   ├── errors.py       # AgentExecutionError
│   └── claude_code.py  # ClaudeCodeAgent (subprocess-based)
├── cli.py              # Argparse-based CLI entry point
└── server.py           # FastAPI webhook server
```

### Key Concepts

- **State** (`dict[str, Any]`) — All workflow data flows as a flat dictionary. Handlers receive and return `State`; the `Runner` injects `run_id` and `workflow_name`.
- **Channel** (Protocol) — I/O boundary adapter. Owns how progress/errors are reported and what initial state is supplied. This is the primary extension point for new I/O adapters.
- **App** — Handler registry. Use the `@app.handler` decorator to register workflow steps by function name. Configure log and worktree directories via `App(log_dir="...", worktree_dir="...")`.
- **Runner** — Execution engine. Binds an `App` + `Channel`, generates a `run_id`, and drives the workflow lifecycle.
- **run_workflow** — Composition helper. Folds state through a list of handler callables, enabling composite workflows without inheritance or a DAG scheduler.
- **Agent** (Protocol) — LLM abstraction. Any object with a `prompt(str) -> str` method qualifies. Extension point for new LLM backends.
- **ClaudeCodeAgent** — Concrete `Agent` implementation. Delegates prompts to the `claude` CLI via subprocess. Accepts an optional `model` parameter.
- **Worktree** — Git worktree wrapper. Provides `create()`, `remove()`, and `exists` for managing isolated git working directories. Paths are absolute for safety after cwd changes.
- **git_worktree** — Context manager that enters a worktree, guarantees cwd restoration via try/finally, and optionally creates/removes the worktree.

### Data Flow

**CLI Execution:**
1. CLI parses args and loads an agents file (Python module exporting `app`)
2. Builds a `CliChannel(workflow_name, initial_state)`
3. `Runner(app, channel).run()` merges initial state with `{run_id, workflow_name}`
4. Handler receives `(runner, state)` and returns new `State`
5. Composite handlers use `run_workflow` to chain sub-steps
6. For LLM workflows: handler creates an `Agent`, calls `agent.prompt()`, and spreads the response into state
7. Result state is printed to stdout
8. If handler calls `runner.fail()`, CLI catches `WorkflowFailedError`, prints to stderr, exits 1

**API Execution:**
1. POST `/webhook` with `{"workflow_name": "my_wf", "initial_state": {...}}`
2. Server validates workflow exists, creates `ApiChannel(workflow_name, initial_state)`
3. Returns `{"run_id": "abc123"}` immediately
4. Workflow runs in background task
5. Progress/errors appear in server logs (stdout/stderr)
6. If handler calls `runner.fail()`, server catches `WorkflowFailedError`, logs error, continues serving

### Writing Handlers

Create a Python file with an `App` instance and decorated handlers:

```python
from anthill.core.app import App, run_workflow
from anthill.core.runner import Runner
from anthill.core.domain import State

app = App()  # Defaults: log_dir="agents/logs/", worktree_dir="trees/"
# Or configure: App(log_dir="my/logs/", worktree_dir="worktrees/")

@app.handler
def my_step(runner: Runner, state: State) -> State:
    runner.report_progress("doing work")
    runner.logger.info("Custom log entry")  # per-run log file
    return {**state, "result": "done"}
```

Handlers always return a **new** dict (spread pattern) — never mutate incoming state.

Handlers can delegate to LLM agents:

```python
from anthill.llm.claude_code import ClaudeCodeAgent

@app.handler
def ask_llm(runner: Runner, state: State) -> State:
    agent = ClaudeCodeAgent(model=state.get("model"))
    response = agent.prompt(state["prompt"])
    return {**state, "result": response}
```

Handlers can isolate work in git worktrees:

```python
from anthill.git import Worktree, git_worktree
from datetime import datetime

@app.handler
def isolated_workflow(runner: Runner, state: State) -> State:
    worktree_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{runner.id}"
    wt = Worktree(base_dir=runner.app.worktree_dir, name=worktree_name)

    with git_worktree(wt, create=True, branch="feat/new", remove=False):
        # Execute steps inside worktree - cwd is wt.path
        state = run_workflow(runner, state, [step1, step2])

    # Cwd restored, worktree kept for review
    return {**state, "worktree_path": wt.path}
```

### Logging

The framework creates a log file for each workflow run at `{log_dir}/{timestamp}-{run_id}.log` (default: `agents/logs/`). Configure via `App(log_dir="path/")`.

Logs capture framework lifecycle events (runner init, workflow start/complete), handler execution (step names, state keys at DEBUG level), and errors. Access the logger in handlers via `runner.logger`:

```python
@app.handler
def my_step(runner: Runner, state: State) -> State:
    runner.logger.info("Starting work")
    runner.logger.debug(f"State: {state}")
    return {**state, "done": True}
```

Log format: `YYYY-MM-DD HH:MM:SS,mmm [LEVEL] anthill.run.{run_id} - message`

Logs do not appear in stdout/stderr (propagation disabled).

### CLI Commands

**anthill run** - Execute a workflow via CLI:
- `--agents-file <path>` - Python file exporting `app` (default: `handlers.py`)
- `--prompt <text>` - Prompt string to inject into initial state as `state["prompt"]`
- `--prompt-file <path>` - Read prompt from file (mutually exclusive with `--prompt`)
- `--model <name>` - Model name to inject as `state["model"]` (e.g., `opus`, `sonnet`)
- `--initial-state key=value` - Set additional state keys (repeatable)

**anthill server** - Start FastAPI webhook server:
- `--host <host>` - Bind address (default: `127.0.0.1`)
- `--port <port>` - Port number (default: `8000`)
- `--reload` - Enable auto-reload on code changes
- `--agents-file <path>` - Python file exporting `app` (default: `handlers.py`)

**API Usage:**
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{"workflow_name": "healthcheck"}'
# Returns: {"run_id": "abc123"}
```

The justfile provides convenient recipes:
- `just sdlc "prompt" opus` - Run standard SDLC workflow, auto-detects if prompt is a file path
- `just sdlc_iso "prompt" opus` - Run isolated SDLC workflow in a git worktree

## Development

### Quality Checks

```bash
# Run all checks (default just target)
just

# Individual checks
just ruff    # Lint
just ty      # Type-check
just test    # Tests
```

### Testing

```bash
uv run -m pytest tests/ -v
```

Tests are organized to mirror the source layout (`tests/core/`, `tests/channels/`, `tests/llm/`, `tests/git/`). Each test owns its setup using shared fixtures from `tests/conftest.py`. The `app` fixture provides log and worktree isolation via temp directories. Git-specific tests use the `git_repo` fixture from `tests/git/conftest.py`.

### Navigating the Codebase

Start with the **core layer** (`src/anthill/core/`):
- `domain.py` defines `State` and the `Channel` protocol — the two types everything else depends on
- `app.py` has the `App` registry and `run_workflow` composition helper
- `runner.py` ties `App` + `Channel` together and drives execution

The **channels layer** (`src/anthill/channels/`) has I/O adapters. `CliChannel` writes to stdout/stderr for terminal usage. `ApiChannel` writes to stdout/stderr for server logs. Add new channels here for other I/O patterns (message queue, database, etc.).

The **llm layer** (`src/anthill/llm/`) abstracts LLM interactions behind the `Agent` protocol. `ClaudeCodeAgent` is the concrete implementation. Add new LLM backends by implementing `prompt(str) -> str`.

The **git layer** (`src/anthill/git/`) provides git worktree support for isolated workflow execution. The `Worktree` class wraps git subprocess operations, and `git_worktree` context manager guarantees cwd restoration.

The **CLI** (`src/anthill/cli.py`) is the entry point. It loads user-defined handlers from a Python file (default: `handlers.py`) and wires everything together. Supports `--prompt` and `--prompt-file` (mutually exclusive) for injecting prompts into state.

### Framework Documentation

For framework development policies (testing strategy, instrumentation patterns), see `app_docs/`. For a concise reference card, see `CLAUDE.md`.
