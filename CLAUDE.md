# Anthill Framework

Workflow engine. `@app.handler` registers handlers, `Runner` executes them.

**State** = `dict[str, Any]`, always return new copy. **Channel** = I/O boundary. **App** = handler registry. **Runner** = App + Channel. **Agent** = LLM wrapper (`ClaudeCodeAgent` wraps `claude` CLI).

Handlers: `def step(runner: Runner, state: State) -> State`. Chain via `run_workflow(runner, state, [step1, step2])`.

## Testing
- Import `anthill.core.*` only
- Each test owns setup, no shared state
- Replace I/O with TestChannel
- One test per code path
- `uv run -m pytest tests/ -v`

## Dev
`just` = lint+typecheck+test. `uv sync` to install.
