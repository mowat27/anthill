# Anthill Framework

Workflow engine. `@app.handler` registers handlers, `Runner` executes them.

**State** = `dict[str, Any]`, always return new copy. **Channel** = I/O boundary. **App** = handler registry. **Runner** = App + Channel. **Agent** = LLM wrapper (`ClaudeCodeAgent` wraps `claude` CLI). **Worktree** = git worktree wrapper for isolated execution.

Handlers: `def step(runner: Runner, state: State) -> State`. Chain via `run_workflow(runner, state, [step1, step2])`.

**Logging**: `App(log_dir=..., worktree_dir=...)` sets dirs (defaults `agents/logs/`, `trees/`). `Runner` creates per-run log `{timestamp}-{run_id}.log`. Use `runner.logger.info()` in handlers.

**Git worktrees**: `Worktree(base_dir, name)` wraps git operations. `git_worktree(wt, create=True, branch="feat", remove=False)` context manager guarantees cwd restore via try/finally. Paths absolute, safe after chdir.

## Testing
- Tests mirror source: `tests/core/`, `tests/channels/`, `tests/llm/`, `tests/git/`
- Use `app` fixture (temp log+worktree dirs), `runner_factory` for Runner+TestChannel
- Git tests use `git_repo` fixture from `tests/git/conftest.py`
- Each test owns setup, no shared state
- One test per code path
- `uv run -m pytest tests/ -v`

## Dev
`just` = lint+typecheck+test. `uv sync` to install.
