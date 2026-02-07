# Anthill Framework

Workflow engine. `@app.handler` registers handlers, `Runner` executes them.

**State** = `dict[str, Any]`, always return new copy. **Channel** = I/O boundary. **App** = handler registry. **Runner** = App + Channel. **Agent** = LLM wrapper (`ClaudeCodeAgent` wraps `claude` CLI).

Handlers: `def step(runner: Runner, state: State) -> State`. Chain via `run_workflow(runner, state, [step1, step2])`.

**Logging**: `App(log_dir=...)` sets log dir (default `agents/logs/`). `Runner` creates per-run log file `{timestamp}-{run_id}.log`. Use `runner.logger.info()` in handlers.

## Testing
- Tests mirror source: `tests/core/`, `tests/channels/`, `tests/llm/`
- Use `app` fixture (temp log dir), `runner_factory` for Runner+TestChannel
- Each test owns setup, no shared state
- One test per code path
- `uv run -m pytest tests/ -v`

## Dev
`just` = lint+typecheck+test. `uv sync` to install.
