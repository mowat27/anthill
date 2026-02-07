# Testing Policy

## Philosophy

Test the framework, not the app. The core machinery (`anthill.core.*`) is the unit under test. User-defined handlers exist only as test data to exercise the framework.

## Test Structure

### Each Test Owns Its Setup

Build the `App`, register handlers, and wire the `Runner` inside each test. No shared global state. This makes test scope explicit and prevents coupling between test cases.

```python
def test_single_handler(runner_factory):
    app = App()

    @app.handler
    def my_handler(runner, state: State) -> State:
        return {**state, "result": state["result"] + 1}

    runner, source = runner_factory(app, "my_handler", {"result": 10})
    result = runner.run()
    assert result["result"] == 11
```

### Replace I/O at the Boundary

Swap channels that do I/O (stdout, stderr) with capturing doubles that collect into lists. Match the interface via duck typing (no inheritance required).

**TestChannel** is the primary test double, defined in `tests/conftest.py`:
- Captures `report_progress()` calls into `progress_messages: list[str]`
- Captures `report_error()` calls into `error_messages: list[str]`
- Provides initial state without external dependencies

**runner_factory** is a pytest fixture that creates `(Runner, TestChannel)` pairs for tests:

```python
runner, source = runner_factory(app, "workflow_name", {"initial": "state"})
```

## Test Coverage Rules

### One Test Per Code Path

If two tests traverse the same core path with different data, they're the same test. A single-handler workflow is one path regardless of what the handler computes.

Focus on:
- Single handler execution
- Multi-step workflow composition via `run_workflow()`
- Error propagation (SystemExit)
- Handler resolution (unknown workflow names)

Avoid testing:
- Handler business logic (that's app code, not framework code)
- Different data values through the same path
- I/O formatting details (those belong in channel-specific tests)

## Running Tests

```bash
uv run -m pytest tests/ -v
```

Run via justfile:
```bash
just test
```

## Test Organization

Tests mirror source layout:
```
tests/
├── core/              # Tests for src/anthill/core/
├── channels/          # Tests for src/anthill/channels/
├── helpers/           # Tests for src/anthill/helpers/
├── llm/               # Tests for src/anthill/llm/
└── test_cli.py        # Tests for src/anthill/cli.py
```

## Fixture Management

All shared fixtures live in `tests/conftest.py`:
- `app` - Returns `App(log_dir=tempfile.mkdtemp())` per test for log isolation
- `runner_factory` - Creates Runner + TestChannel pairs, accepts optional `app` parameter
- `TestChannel` - In-memory channel double for capturing I/O

Keep fixture scope minimal. Prefer function-scoped fixtures to session-scoped unless there's a compelling performance reason.

### Log Isolation in Tests

The `app` fixture directs logs to a temp directory per test, preventing log files from accumulating in the working directory. Tests that create Runners should use the `app` fixture:

```python
def test_something(app, runner_factory):
    runner, source = runner_factory(app, "workflow", {})
    # Log files go to app.log_dir (temp directory)
```
