# Anthill Framework

Workflow engine. `@app.handler` registers handlers, `Runner` executes them.

**State** = `dict[str, Any]`, return new copy. **Channel** = I/O boundary (CliChannel, ApiChannel). **App** = handler registry. **Runner** = App + Channel. **Agent** = LLM wrapper (`ClaudeCodeAgent` wraps `claude` CLI). **Worktree** = git worktree wrapper.

Handlers: `def step(runner: Runner, state: State) -> State`. Chain via `run_workflow(runner, state, [step1, step2])`.

**Error handling**: `runner.fail(msg)` raises `WorkflowFailedError`. CLI catches, prints stderr, exits 1. API server catches, logs, continues.

**Logging**: `App(log_dir=..., worktree_dir=...)` sets dirs (defaults `agents/logs/`, `trees/`). `Runner` creates per-run log `{timestamp}-{run_id}.log`. Use `runner.logger.info()`.

**Git worktrees**: `Worktree(base_dir, name)`. `git_worktree(wt, create=True, branch="feat", remove=False)` context manager guarantees cwd restore. Paths absolute.

**API server**: `anthill server --host 0.0.0.0 --port 8000 --agents-file handlers.py`. POST `/webhook` with `{"workflow_name": "wf", "initial_state": {}}`, returns `{"run_id": "..."}`. Runs background task.

## Testing
- Mirror source: `tests/core/`, `tests/channels/`, `tests/llm/`, `tests/git/`
- `app` fixture (temp dirs), `runner_factory` for Runner+TestChannel
- Git tests use `git_repo` fixture
- Each test owns setup
- FastAPI tests use `TestClient`, temp agents files
- `uv run -m pytest tests/ -v`

## Handlers
Organize: steps, shared constants, workflows. Constants only when shared.

## Dev
`just` = lint+typecheck+test. `uv sync` to install.
