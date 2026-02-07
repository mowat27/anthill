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
