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

The framework does not use Python's logging module. All output goes through the `Channel` interface:
- `report_progress()` for normal messages
- `report_error()` for errors

Handlers should not print directly. Use the `Runner` methods to ensure correct formatting and routing.

## LLM Agent Execution

The `ClaudeCodeAgent` reports subprocess execution failures via `AgentExecutionError`:

```python
try:
    response = agent.prompt("/specify build a feature")
except AgentExecutionError as e:
    runner.fail(f"Agent failed: {e}")
```

No automatic retry or telemetry. Handlers are responsible for error handling policy.
