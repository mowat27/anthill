# chore: Add Python logging to framework operations

- Add file-based Python logging to Runner, configured via `App(log_dir=...)`, defaulting to `agents/logs/`.
- Log framework lifecycle, handler execution, LLM calls, and errors at INFO/DEBUG/ERROR levels.
- Reorganize tests into package structure mirroring source layout; update tests to use shared `app` fixture.

## Solution Design

### Architectural Schema Changes

```yaml
types:
    App:
      kind: class
      fields:
        - handlers: dict  # existing
        - log_dir: str  # New field, default "agents/logs/"

    Runner:
      kind: class
      fields:
        - id: str  # existing
        - channel: Channel  # existing
        - app: App  # existing
        - logger: logging.Logger  # New field
```

### External Interface Change

**App** gains a `log_dir` parameter:
```python
app = App(log_dir="my/logs/")  # custom
app = App()                     # defaults to "agents/logs/"
```

**Runner** exposes `runner.logger` (a `logging.Logger` instance). Handlers can use it directly:
```python
@app.handler
def my_step(runner: Runner, state: State) -> State:
    runner.logger.info("Starting work")
    runner.logger.debug(f"State: {state}")
    return {**state, "done": True}
```

Log files are created at `{log_dir}/{YYYYMMDDhhmmss}-{run_id}.log` with format:
```
2026-02-07 14:30:00,123 [INFO] antkeeper.run.a1b2c3d4 - Workflow started: my_workflow
```

## Relevant Files

- `src/antkeeper/core/app.py` — Add `log_dir` parameter to `App.__init__`; add logging to `run_workflow`.
- `src/antkeeper/core/runner.py` — Create logger with FileHandler in `Runner.__init__`; log lifecycle events in all methods.
- `src/antkeeper/channels/cli.py` — Add module-level logger; log initialization at DEBUG.
- `src/antkeeper/llm/claude_code.py` — Add module-level logger; log prompts, responses, and errors.
- `src/antkeeper/cli.py` — Add module-level logger; log CLI lifecycle events.
- `tests/conftest.py` — Add `app` fixture that returns `App(log_dir=tempfile.mkdtemp())` per test; update `runner_factory` to use it.
- `app_docs/instrumentation.md` — Update logging section to reflect new capability.

### New Files

- `tests/core/__init__.py` — Empty package init for reorganized test subpackage.
- `tests/channels/__init__.py` — Empty package init for reorganized test subpackage.
- `tests/llm/__init__.py` — Empty package init for reorganized test subpackage.

## Workflow

### Step 1: Add `log_dir` parameter to App

- In `src/antkeeper/core/app.py`, change `App.__init__` to accept `log_dir: str = "agents/logs/"` and store as `self.log_dir`.
- No other changes to App class at this step.

### Step 2: Create logger in Runner

- In `src/antkeeper/core/runner.py`, add imports: `import logging`, `import os`, `from datetime import datetime`.
- In `Runner.__init__`, after generating `self.id`:
  - Create log directory: `os.makedirs(app.log_dir, exist_ok=True)`
  - Build log filename: `f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{self.id}.log"`
  - Build log path: `os.path.join(app.log_dir, log_filename)`
  - Create logger: `self.logger = logging.getLogger(f"antkeeper.run.{self.id}")`
  - Set logger level to `logging.DEBUG`
  - Create `logging.FileHandler(log_path)`
  - Set formatter: `logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")`
  - Add handler to `self.logger`
  - Set `self.logger.propagate = False` to prevent stdout leakage
- Add logging statements to Runner methods:
  - `__init__`: `INFO` — `"Runner initialized: run_id={self.id}, workflow={self.channel.workflow_name}"`; `DEBUG` — `"Log file: {log_path}"`, `"Channel type: {self.channel.type}"`
  - `run()`: `INFO` — `"Workflow started: {self.workflow_name}"`; `DEBUG` — `"Initial state: {state}"`; after handler returns: `INFO` — `"Workflow completed: {self.workflow_name}"`; `DEBUG` — `"Final state: {state}"`; wrap workflow call in try/except: `ERROR` — `"Workflow failed: {self.workflow_name} - {type(e).__name__}: {e}"` then re-raise
  - `report_progress()`: `INFO` — `"Progress: {message}"`
  - `report_error()`: `ERROR` — `"Error reported: {message}"`
  - `fail()`: `ERROR` — `"Workflow fatal error: {message}"`

### Step 3: Add logging to run_workflow

- In `src/antkeeper/core/app.py`, in the `run_workflow` function:
  - Before the loop: `runner.logger.info(f"run_workflow started with {len(steps)} steps: {[s.__name__ for s in steps]}")`
  - Inside loop, before each step: `runner.logger.info(f"Executing step: {step.__name__}")`
  - Inside loop, after each step: `runner.logger.debug(f"Step completed: {step.__name__}, state keys: {list(state.keys())}")`
  - After the loop: `runner.logger.info("run_workflow completed")`

### Step 4: Add module-level logging to outer layers

- In `src/antkeeper/channels/cli.py`:
  - Add `import logging` and `logger = logging.getLogger("antkeeper.channels.cli")` at module level.
  - In `__init__`: `logger.debug(f"CliChannel initialized: workflow_name={workflow_name}")`
  - In `report_progress`: `logger.debug(f"Progress [{run_id}]: {message}")`
  - In `report_error`: `logger.debug(f"Error [{run_id}]: {message}")`

- In `src/antkeeper/llm/claude_code.py`:
  - Add `import logging` and `logger = logging.getLogger("antkeeper.llm.claude_code")` at module level.
  - In `__init__`: `logger.debug(f"ClaudeCodeAgent initialized: model={self.model}")`
  - In `prompt()`:
    - Before subprocess: `logger.info(f"LLM prompt submitted (length={len(prompt)} chars)")` and `logger.debug(f"LLM prompt content: {prompt}")`
    - After subprocess: `logger.debug(f"LLM subprocess command: {cmd}")`
    - On success: `logger.info(f"LLM response received (length={len(result.stdout)} chars)")` and `logger.debug(f"LLM response content: {result.stdout}")`
    - On FileNotFoundError: `logger.error("claude binary not found")`
    - On non-zero exit: `logger.error(f"claude exited with code {result.returncode}: {result.stderr}")`

- In `src/antkeeper/cli.py`:
  - Add `import logging` and `logger = logging.getLogger("antkeeper.cli")` at module level.
  - After parsing args: `logger.debug(f"CLI args parsed: command={args.command}")`
  - After loading app: `logger.info(f"App loaded from {agents_file}")`
  - On FileNotFoundError: `logger.error(f"Agents file not found: {agents_file}")`
  - On AttributeError: `logger.error(f"{agents_file} has no 'app' attribute")`
  - After creating runner: `logger.info(f"Runner created: run_id={runner.id}")`
  - After `runner.run()`: `logger.info("Workflow run complete")`

Note: Module-level loggers in outer layers (`antkeeper.channels.cli`, `antkeeper.llm.claude_code`, `antkeeper.cli`) will only produce output if a handler is attached to them or a parent logger. By default, these logs go nowhere — they serve as extension points for users who want to configure additional logging. The primary logging (lifecycle, state, errors) happens through `runner.logger` which always has a FileHandler.

### Step 5: Update conftest.py and existing tests for test isolation

- In `tests/conftest.py`, add `import tempfile`.
- Add a new function-scoped `app` fixture that returns `App(log_dir=tempfile.mkdtemp())`. This gives every test a fresh App with logs directed to a temp directory.
- Update `runner_factory` to accept the `app` fixture and use it as default, removing the need for tests to create `App()` inline.
- Update all existing test files to use the `app` fixture instead of creating `App()` inline. This is a mechanical replacement: remove `app = App()` lines and add `app` to the test method signature. No assertion or logic changes.

### Step 6: Reorganize test files

Move test files to mirror the source structure.

| Old location | New location |
|---|---|
| `tests/test_workflows.py` | `tests/core/test_workflows.py` |
| `tests/test_cli_channel.py` | `tests/channels/test_cli_channel.py` |
| `tests/test_claude_code_agent.py` | `tests/llm/test_claude_code_agent.py` |
| `tests/test_cli.py` | `tests/test_cli.py` (stays — mirrors `src/antkeeper/cli.py` at root) |
| `tests/conftest.py` | `tests/conftest.py` (stays — pytest discovers it for all subdirs) |
| `tests/__init__.py` | `tests/__init__.py` (stays) |

Create new empty `__init__.py` files:
- `tests/core/__init__.py`
- `tests/channels/__init__.py`
- `tests/llm/__init__.py`

### Step 7: Update instrumentation.md

- In `app_docs/instrumentation.md`, replace the "Logging" section (lines 62-68) to describe the new file-based logging capability.
- Document that `Runner` creates a per-run log file, the filename format, and that handlers can access logging via `runner.logger`.

### Step 8: Run validation commands

- Run all validation commands below and fix any issues until zero errors and zero warnings.

## Testing Strategy

### Unit Tests

New file: `tests/core/test_logging.py`

**App configuration:**
- `test_app_log_dir_defaults_to_agents_logs` — `App().log_dir == "agents/logs/"`
- `test_app_log_dir_accepts_custom_value` — `App(log_dir="/tmp/custom").log_dir == "/tmp/custom"`

**Runner log file creation:**
- `test_runner_creates_log_directory` — After `Runner(app, channel)`, `os.path.isdir(app.log_dir)` is True.
- `test_runner_creates_log_file_with_correct_name_format` — Exactly one `.log` file in log dir, filename matches `r"^\d{14}-[a-f0-9]{8}\.log$"`, run_id portion matches `runner.id`.

**Log content and format:**
- `test_log_format_matches_expected_pattern` — Log file lines match `r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[\w+\] antkeeper\..+ - .+"`.
- `test_runner_log_file_contains_initialization_message` — Log file contains `[INFO]` and runner ID.
- `test_runner_logs_workflow_start_and_end` — After `runner.run()`, log contains INFO entries for start and completion.
- `test_runner_logs_initial_and_final_state_at_debug` — Log contains DEBUG entries with state contents.

**Step logging:**
- `test_run_workflow_logs_steps` — For a two-step workflow, log contains INFO entries for each step name and DEBUG entries for completion.

**Error logging:**
- `test_runner_logs_error_at_error_level` — When handler raises, log contains `[ERROR]` with exception info.

**Logger isolation:**
- `test_antkeeper_logger_does_not_leak_to_stdout` — After workflow, capsys stdout/stderr does not contain log format lines.

All logging tests use the `app` fixture (which provides `App(log_dir=tempfile.mkdtemp())`). Tests must clean up FileHandlers after use to prevent resource leaks across the test suite (use `try/finally` or fixture teardown to call `handler.close()` and remove from logger).

### Edge Cases

- Log directory already exists — `os.makedirs(exist_ok=True)` handles this; covered by existing tests that run multiple times.
- Empty workflow name — Logger still creates file; no special handling needed.
- Multiple Runners from same App — Each gets its own log file and its own logger instance (keyed by run_id); no handler accumulation on shared loggers.

## Acceptance Criteria

- `App(log_dir="x")` stores `log_dir` attribute; defaults to `"agents/logs/"`.
- `Runner.__init__` creates log directory if needed and creates a log file named `{YYYYMMDDhhmmss}-{run_id}.log`.
- Log file contains timestamped entries at INFO, DEBUG, and ERROR levels for framework operations.
- `runner.logger` is accessible to handlers for custom logging.
- Log output does not leak to stdout/stderr (logger propagation is disabled).
- Module-level loggers exist in `cli.py`, `channels/cli.py`, and `llm/claude_code.py`.
- Tests reorganized into `tests/core/`, `tests/channels/`, `tests/llm/` mirroring source structure.
- All existing tests pass from their new locations.
- `app_docs/instrumentation.md` updated to document logging.

### Validation Commands

```bash
# Run all quality checks (lint + typecheck + test)
just

# Run tests explicitly with verbose output
uv run -m pytest tests/ -v

# Verify test files moved correctly
test -f tests/core/test_workflows.py && echo "OK" || echo "FAIL"
test -f tests/channels/test_cli_channel.py && echo "OK" || echo "FAIL"
test -f tests/llm/test_claude_code_agent.py && echo "OK" || echo "FAIL"
test ! -f tests/test_workflows.py && echo "OK: old file removed" || echo "FAIL: old file still exists"
test ! -f tests/test_cli_channel.py && echo "OK: old file removed" || echo "FAIL: old file still exists"
test ! -f tests/test_claude_code_agent.py && echo "OK: old file removed" || echo "FAIL: old file still exists"

# Verify log file creation works
uv run python -c "
from antkeeper.core.app import App
from antkeeper.core.runner import Runner
import tempfile, os, glob
app = App(log_dir=tempfile.mkdtemp())

class Ch:
    type = 'test'
    workflow_name = 'smoke'
    initial_state = {}
    def report_progress(self, *a, **k): pass
    def report_error(self, *a, **k): pass

r = Runner(app, Ch())
logs = glob.glob(os.path.join(app.log_dir, '*.log'))
assert len(logs) == 1, f'Expected 1 log file, found {len(logs)}'
assert r.id in logs[0], 'run_id not in log filename'
print(f'Log file created: {logs[0]}')
with open(logs[0]) as f:
    content = f.read()
    assert '[INFO]' in content, 'No INFO entries in log'
    print('Log content OK')
"
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this chore.

## Notes

- The logger is attached per-Runner instance (keyed by `antkeeper.run.{run_id}`), NOT to a shared parent logger. This prevents handler accumulation when multiple Runners are created from the same App.
- Module-level loggers in outer layers (`antkeeper.channels.cli`, `antkeeper.llm.claude_code`, `antkeeper.cli`) are fire-and-forget — they only produce output if a user configures handlers on them or their parents. They are not connected to the per-run FileHandler by default.
- `os.makedirs` errors (permissions, disk full) are allowed to propagate per design philosophy — these are runtime errors that should surface to the caller.
- The `ClaudeCodeAgent` interface is NOT changed (no optional logger parameter). It uses a module-level logger only.

## Report

Report: files changed (with line counts), files moved, new test file with test count, validation command results (all must pass). Max 200 words.
