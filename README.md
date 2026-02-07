# Anthill

A lightweight Python workflow engine. Define handlers (workflow steps) via a decorator-based `App`, wire them to a `Channel` (I/O boundary), and execute through a `Runner`. Designed for composable, testable pipelines.

## Requirements

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) package manager

## Quickstart

```bash
# Install dependencies
uv sync

# Run a workflow
anthill run --agents-file handlers.py --initial-state result=5 plus_1

# Run an LLM workflow with prompt and model
anthill run --agents-file handlers.py --prompt "describe this project" --model sonnet specify
```

## Project Structure

```
src/anthill/
├── core/               # Framework kernel
│   ├── domain.py       # State type alias, Channel protocol
│   ├── app.py          # App handler registry, run_workflow helper
│   └── runner.py       # Runner execution engine
├── channels/
│   └── cli.py          # CLI channel adapter (stdout/stderr reporting)
├── llm/                # LLM agent abstraction layer
│   ├── __init__.py     # Agent protocol
│   ├── errors.py       # AgentExecutionError
│   └── claude_code.py  # ClaudeCodeAgent (subprocess-based)
└── cli.py              # Argparse-based CLI entry point
```

### Key Concepts

- **State** (`dict[str, Any]`) — All workflow data flows as a flat dictionary. Handlers receive and return `State`; the `Runner` injects `run_id` and `workflow_name`.
- **Channel** (Protocol) — I/O boundary adapter. Owns how progress/errors are reported and what initial state is supplied. This is the primary extension point for new I/O adapters.
- **App** — Handler registry. Use the `@app.handler` decorator to register workflow steps by function name.
- **Runner** — Execution engine. Binds an `App` + `Channel`, generates a `run_id`, and drives the workflow lifecycle.
- **run_workflow** — Composition helper. Folds state through a list of handler callables, enabling composite workflows without inheritance or a DAG scheduler.
- **Agent** (Protocol) — LLM abstraction. Any object with a `prompt(str) -> str` method qualifies. Extension point for new LLM backends.
- **ClaudeCodeAgent** — Concrete `Agent` implementation. Delegates prompts to the `claude` CLI via subprocess. Accepts an optional `model` parameter.

### Data Flow

1. CLI parses args and loads an agents file (Python module exporting `app`)
2. Builds a `CliChannel(workflow_name, initial_state)`
3. `Runner(app, channel).run()` merges initial state with `{run_id, workflow_name}`
4. Handler receives `(runner, state)` and returns new `State`
5. Composite handlers use `run_workflow` to chain sub-steps
6. For LLM workflows: handler creates an `Agent`, calls `agent.prompt()`, and spreads the response into state
7. Result state is printed to stdout

### Writing Handlers

Create a Python file with an `App` instance and decorated handlers:

```python
from anthill.core.app import App, run_workflow
from anthill.core.runner import Runner
from anthill.core.domain import State

app = App()

@app.handler
def my_step(runner: Runner, state: State) -> State:
    runner.report_progress("doing work")
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

### Running Tests

```bash
uv run -m pytest tests/ -v
```

Tests follow these rules:
- **Test the framework, not the app.** Import from `anthill.core.*`.
- **Each test owns its setup.** No shared global state.
- **Replace I/O at the boundary.** Swap channels with capturing doubles.
- **One test per code path.**

### Navigating the Codebase

Start with the **core layer** (`src/anthill/core/`):
- `domain.py` defines `State` and the `Channel` protocol — the two types everything else depends on
- `app.py` has the `App` registry and `run_workflow` composition helper
- `runner.py` ties `App` + `Channel` together and drives execution

The **channels layer** (`src/anthill/channels/`) has I/O adapters. `CliChannel` is the only implementation; add new channels here for other I/O patterns (API, message queue, etc.).

The **llm layer** (`src/anthill/llm/`) abstracts LLM interactions behind the `Agent` protocol. `ClaudeCodeAgent` is the concrete implementation. Add new LLM backends by implementing `prompt(str) -> str`.

The **CLI** (`src/anthill/cli.py`) is the entry point. It loads user-defined handlers from a Python file (default: `handlers.py`) and wires everything together.

**Test doubles** live in `tests/conftest.py` — `TestChannel` captures progress/error messages in lists, and `runner_factory` creates test `Runner` instances.
