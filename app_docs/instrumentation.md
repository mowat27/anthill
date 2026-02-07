# Instrumentation

## Progress Reporting

Handlers report progress via the `Runner`:

```python
@app.handler
def my_step(runner: Runner, state: State) -> State:
    runner.report_progress("doing work")
    return {**state, "result": "done"}
```

The `Runner` delegates to the `Channel`, which formats and outputs the message based on its implementation:

- **CliChannel**: Writes to stdout with format `[workflow_name, run_id] message`
- **TestChannel**: Appends to `progress_messages` list for verification

## Error Reporting

Report non-fatal errors (informational warnings) via `runner.report_error()`:

```python
runner.report_error("optional validation failed, continuing")
```

For fatal errors, use `runner.fail()`:

```python
if "required_key" not in state:
    runner.fail("Missing required_key in state")
```

`fail()` prints to stderr and exits with code 1.

## Run Identification

Every workflow execution gets a unique `run_id` (8-character hex string). The `Runner` injects it into state along with `workflow_name`:

```python
state = {
    **channel.initial_state,
    "run_id": runner.id,
    "workflow_name": runner.workflow_name
}
```

Progress and error messages include the `run_id` for correlation.

## State Persistence

The framework does not persist state. Handlers receive `State` as an immutable input and return a new `State` dict. If persistence is needed, implement it in a handler or custom channel:

```python
@app.handler
def persist_state(runner: Runner, state: State) -> State:
    with open(f"/tmp/{state['run_id']}.json", "w") as f:
        json.dump(state, f)
    return state
```

## Logging

The framework provides file-based Python logging via the `Runner`. Each workflow run creates a dedicated log file.

### Configuration

```python
app = App(log_dir="my/logs/")  # custom directory
app = App()                     # defaults to "agents/logs/"
```

### Per-Run Log Files

`Runner.__init__` creates a log file at `{log_dir}/{YYYYMMDDhhmmss}-{run_id}.log` with format:

```
2026-02-07 14:30:00,123 [INFO] anthill.run.a1b2c3d4 - Workflow started: my_workflow
```

The framework logs lifecycle events (runner init, workflow start/complete), handler execution (step names, state keys), and errors at INFO/DEBUG/ERROR levels. Log output does not leak to stdout/stderr (logger propagation is disabled).

### Using the Logger in Handlers

Handlers can access `runner.logger` for custom logging:

```python
@app.handler
def my_step(runner: Runner, state: State) -> State:
    runner.logger.info("Starting work")
    runner.logger.debug(f"State: {state}")
    return {**state, "done": True}
```

### Module-Level Loggers

Module-level loggers exist in `cli.py`, `channels/cli.py`, and `llm/claude_code.py`. These only produce output if a user configures handlers on them or their parents — they serve as extension points for additional logging.

## LLM Agent Execution

The `ClaudeCodeAgent` reports subprocess execution failures via `AgentExecutionError`:

```python
try:
    response = agent.prompt("/specify build a feature")
except AgentExecutionError as e:
    runner.fail(f"Agent failed: {e}")
```

No automatic retry or telemetry. Handlers are responsible for error handling policy.

## Git Worktree Isolation

The `anthill.git` module provides git worktree support for isolating workflow execution in separate working directories.

### Configuration

```python
app = App(worktree_dir="trees/")  # custom directory
app = App()                        # defaults to "trees/"
```

Access the configured worktree directory via `runner.app.worktree_dir`.

### Worktree Class

The `Worktree` class wraps git worktree subprocess operations:

```python
from anthill.git import Worktree, WorktreeError

wt = Worktree(base_dir=runner.app.worktree_dir, name="20260207-a1b2c3d4")
wt.create(branch="feat/new-feature")  # Creates worktree with new branch
# wt.path is absolute, safe after cwd changes
wt.remove()  # Removes worktree
```

All paths are stored as absolute (`os.path.realpath`) so they remain valid after `os.chdir()`.

### git_worktree Context Manager

The `git_worktree` context manager guarantees cwd restoration via try/finally:

```python
from anthill.git import git_worktree, Worktree, WorktreeError

wt = Worktree(base_dir=runner.app.worktree_dir, name="feature-work")

# Create, enter, and clean up
with git_worktree(wt, create=True, branch="feat/x", remove=True):
    # Work inside worktree - cwd is wt.path
    state = run_workflow(runner, state, [step1, step2])
# Worktree is removed, cwd is restored

# Enter existing worktree
with git_worktree(wt, create=False):
    # Work inside existing worktree
    pass
# cwd restored, worktree kept
```

Key guarantees:
- **Cwd restoration**: `os.chdir()` back to original directory in finally block
- **Error propagation**: Git failures raise `WorktreeError` with stderr
- **Cleanup safety**: Removal happens after cwd restoration (not while inside worktree)
- **Validation**: Raises `WorktreeError` if `create=False` and worktree doesn't exist

Cwd changes are process-wide. The context manager is designed for single-threaded execution.

### Worktree Naming Pattern

Follow the log file naming convention for correlation:

```python
worktree_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{runner.id}"
# Example: "20260207143000-a1b2c3d4"
```

This allows matching worktrees to their log files via the run_id.

### Error Handling

Git operations raise `WorktreeError` on failure:

```python
from anthill.git import WorktreeError

try:
    wt.create(branch="feat/x")
except WorktreeError as e:
    runner.fail(f"Worktree creation failed: {e}")
```

The framework does not catch these errors. Handlers are responsible for error policy.
