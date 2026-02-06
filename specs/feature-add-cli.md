# feature: Add CLI with argparse and refactor Channel interface

- Add `anthill` CLI entry point with `run` subcommand using argparse, defaulting agents file to `handlers.py`.
- Break Channel protocol: add `initial_state` so Channels own state construction, simplifying Runner.
- Rename `main.py` to `handlers.py`, strip CLI logic; CLI module dynamically loads the agents file.

## Solution Design

### External Interface Change

After this change, Channels are responsible for providing initial state to the Runner. The CLI parses `--initial-state key=val` pairs and a `PROMPT` positional arg (which identifies the workflow to run), then the CliChannel packages the state pairs into `initial_state`.

**BREAKING CHANGE**: Ignore backwards compatibility. The old `CliChannel(type, workflow_name)` constructor and `Runner.run(initial_state)` signature are replaced entirely.

**CLI usage:**
```
anthill run [--agents-file=handlers.py] [--initial-state key=val ...] PROMPT
```

Where `PROMPT` is the workflow/handler name to execute (e.g., `plus_1_times_2`).

**Channel construction example (CLI):**
```python
channel = CliChannel(workflow_name="plus_1_times_2", initial_state={"result": "10"})
# channel.initial_state => {"result": "10"}
```

**Other channel examples (future, not in scope):**
```python
# A Slack channel would construct initial_state from a Slack event payload
# A GitHub channel would construct initial_state from an issue body
# Each channel owns how it builds initial_state from its native inputs
```

**Runner usage simplification:**
```python
runner = Runner(app, channel)
result = runner.run()  # No arguments - channel provides initial_state
```

### Architectural Schema Changes

```yaml
types:
  Channel:
    kind: protocol
    fields:
      - type: str
      - workflow_name: str
      - initial_state: State  # New field
    methods:
      - report_progress(self, run_id: str, message: str, **opts: Any) -> None
      - report_error(self, run_id: str, message: str) -> None

  CliChannel:
    kind: class
    constructor:
      - workflow_name: str
      - initial_state: dict[str, str]  # from --initial-state key=val pairs; default {}
    fields:
      - type: str              # always "cli"
      - workflow_name: str
      - initial_state: State   # built from state dict in __init__
    methods:
      - report_progress(self, run_id: str, message: str, **opts: Any) -> None
      - report_error(self, run_id: str, message: str) -> None
```

## Relevant Files

- `src/anthill/core/domain.py` — Add `initial_state: State` to Channel protocol.
- `src/anthill/core/runner.py` — Change `Runner.run()` to read `initial_state` from `self.channel` instead of accepting it as a parameter. Framework keys (`run_id`, `workflow_name`) must take precedence over channel-provided state.
- `src/anthill/channels/cli.py` — Rewrite CliChannel constructor to accept `workflow_name` and `initial_state` dict. Build `initial_state` in `__init__`. Hardcode `type = "cli"`.
- `main.py` — Delete (content moves to `handlers.py`).
- `pyproject.toml` — Add `[project.scripts]` entry point for `anthill` command.
- `tests/conftest.py` — Rename `TestMissionSource` to `TestChannel`. Add `initial_state` field. Update `runner_factory` fixture.
- `tests/test_workflows.py` — Update all tests to pass `initial_state` through the test channel instead of `runner.run()`.

### New Files

- `src/anthill/cli.py` — New CLI module using argparse with `run` subcommand.
- `handlers.py` — Renamed from `main.py`. Contains only the `App` instance and handler definitions. No CLI logic, no `main()`, no `__main__` block.

## Workflow

### Step 1: Update Channel protocol

- Add `initial_state: State` to the `Channel` protocol in `src/anthill/core/domain.py`.
- This is the foundational change that all other changes depend on.

### Step 2: Update Runner.run()

- Change `Runner.run()` in `src/anthill/core/runner.py` to take no arguments.
- Read `self.channel.initial_state` and merge with framework keys.
- **Merge order**: framework keys (`run_id`, `workflow_name`) must override anything in `initial_state`. Use: `state = {**self.channel.initial_state, "run_id": self.id, "workflow_name": self.workflow_name}`.
- The new signature: `def run(self) -> State`.

### Step 3: Rewrite CliChannel

- Change constructor to `__init__(self, workflow_name: str, initial_state: dict[str, str] | None = None)`.
- Hardcode `self.type = "cli"`.
- Build `self.initial_state` in `__init__` as `{**(initial_state or {})}`.
- Keep `report_progress` and `report_error` as-is.

### Step 4: Create the CLI module

- Create `src/anthill/cli.py` with a `main()` function as the entry point.
- Use `argparse.ArgumentParser` with `subparsers` for the `run` subcommand.
- `run` subcommand args:
  - `--agents-file` (default: `handlers.py`) — path to Python file containing `app` object.
  - `--initial-state` (action=`append`, default=[]) — repeatable `key=val` pairs.
  - `prompt` — positional argument (the workflow/handler name to run).
- Parse `--initial-state` pairs in the CLI: split each on first `=`. If a pair has no `=`, print an error and exit.
- Load the agents file using `importlib.util.spec_from_file_location` and `module_from_spec` to import the `app` object dynamically. Handle errors:
  - `FileNotFoundError` — print `"Error: agents file not found: {path}"` to stderr, exit 1.
  - `AttributeError` (no `app` on module) — print `"Error: {path} has no 'app' attribute"` to stderr, exit 1.
- Construct `CliChannel(workflow_name=args.prompt, initial_state=parsed_state)`.
- Create `Runner(app, channel)`, call `runner.run()`, print the final state.
- If no subcommand is given, print help and exit.

### Step 5: Add entry point to pyproject.toml

- Add `[project.scripts]` section: `anthill = "anthill.cli:main"`.

### Step 6: Rename main.py to handlers.py

- Remove the `main()` function, `__main__` block, and `sys` import.
- Keep only the `App` instance and handler definitions.
- Keep all imports needed by the handlers.

### Step 7: Update tests

- Rename `TestMissionSource` to `TestChannel` in `conftest.py`.
- Add `initial_state` parameter to `TestChannel.__init__()` and store it.
- Update `runner_factory` to accept `initial_state` parameter (default `{}`) and pass it to the test channel.
- Update all existing tests. Example migration pattern:

```python
# BEFORE
runner, source = runner_factory(app, "add_1")
result = runner.run({"result": 10})

# AFTER
runner, source = runner_factory(app, "add_1", {"result": 10})
result = runner.run()
```

- Add new tests for CliChannel (see Testing Strategy).
- Add new tests for CLI argument parsing (see Testing Strategy).

### Step 8: Run validation commands

- Run all tests, type checks, and linting.
- Verify `anthill run --help` works.
- Verify `anthill run --initial-state result=10 plus_1_times_2_times_2` works with handlers.py.

## Testing Strategy

### Unit Tests

**CliChannel tests** (`tests/test_cli_channel.py`):
- `test_cli_channel_initial_state` — Parameterized: verify `CliChannel("wf", {"k": "v"}).initial_state == {"k": "v"}` and `CliChannel("wf").initial_state == {}`.
- `test_cli_channel_workflow_name` — Verify `workflow_name` is set from constructor arg.

**CLI argument parsing tests** (`tests/test_cli.py`):
- `test_parse_run_with_prompt_only` — Verify minimal `run PROMPT` parsing.
- `test_parse_run_with_state_pairs` — Verify `--initial-state key=val --initial-state k2=v2` produces correct dict.
- `test_parse_run_with_agents_file` — Verify `--agents-file` overrides default.
- `test_parse_run_missing_prompt_exits` — Verify argparse exits when prompt is missing.

**Updated workflow tests** (`tests/test_workflows.py`):
- Update all four existing tests to pass initial_state through the test channel, calling `runner.run()` with no arguments.

### Integration

- `test_cli_loads_agents_file_and_runs` — Create a temp handlers file with a simple app+handler, invoke the CLI `main()` function programmatically, verify workflow executes and returns expected state.

### Edge Cases

- `--initial-state` with no `=` sign — CLI should print error and exit 1.
- `--agents-file` pointing to nonexistent file — print clear error, exit 1.
- `--agents-file` pointing to file with no `app` attribute — print clear error, exit 1.
- `--initial-state` with duplicate keys — last value wins (standard dict behavior, no special handling).
- `--initial-state` values are always strings — type coercion is the responsibility of handlers, not the framework.

## Acceptance Criteria

- `anthill run --help` prints usage showing `--agents-file`, `--initial-state`, and `PROMPT`.
- `anthill run --initial-state result=10 plus_1_times_2_times_2` executes the workflow from `handlers.py` and prints the result.
- `anthill run --agents-file=handlers.py --initial-state result=5 plus_1` works.
- `CliChannel` constructs `initial_state` from state dict.
- `Runner.run()` accepts no arguments; reads `initial_state` from channel.
- `Channel` protocol includes `initial_state: State`.
- All existing tests pass (updated for new interface).
- New unit tests for CliChannel and CLI parsing pass.
- `main.py` no longer exists; `handlers.py` contains only app + handlers.
- `pyproject.toml` has `[project.scripts] anthill = "anthill.cli:main"`.
- Type checks pass (`uv run -m ty check`).
- Linting passes (`uv run -m ruff check`).

### Validation Commands

```bash
# Run all tests
uv run -m pytest tests/ -v

# Type check
uv run -m ty check

# Lint
uv run -m ruff check

# Verify CLI help works (via entry point)
uv run anthill run --help

# Verify CLI runs a workflow
uv run anthill run --initial-state result=10 plus_1_times_2_times_2
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- This is a **BREAKING CHANGE**. Do not maintain backwards compatibility with the old `CliChannel(type, workflow_name)` constructor or the old `Runner.run(initial_state)` signature.
- `PROMPT` in the CLI is the workflow/handler name to execute. The naming follows the user's spec.
- `importlib.util` is used for dynamic module loading because it's in the Python standard library and allows loading from arbitrary file paths.
- `--initial-state` values are always strings from the CLI. Type coercion (e.g., `"10"` to `10`) is the responsibility of handlers, not the framework.
- State merge order in `Runner.run()`: framework keys (`run_id`, `workflow_name`) always override `initial_state` to prevent channels from clobbering framework internals.

## Report

Files changed: `src/anthill/core/domain.py`, `src/anthill/core/runner.py`, `src/anthill/channels/cli.py`, `pyproject.toml`, `tests/conftest.py`, `tests/test_workflows.py`. Files created: `src/anthill/cli.py`, `handlers.py`, `tests/test_cli_channel.py`, `tests/test_cli.py`. Files deleted: `main.py`. Tests added: 2 CliChannel unit tests, 4 CLI parsing tests, 1 integration test. Validations: pytest, ty check, ruff check, CLI help, CLI workflow execution.
