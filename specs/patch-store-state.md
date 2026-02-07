# patch: Persist state as JSON on every change

- Add `state_dir` to `App` (default `.antkeeper/state/`), persist state as JSON every time it changes
- `Runner` writes `{timestamp}-{run_id}.json` on initial state creation, after handler returns, and after each `run_workflow` step
- File naming mirrors log files for correlation

## Solution Design

### External Interface Change

`App` gains a `state_dir` parameter alongside existing `log_dir` and `worktree_dir`:

```python
app = App(state_dir=".antkeeper/state/")  # custom directory
app = App()                              # defaults to ".antkeeper/state/"
```

Channels are unaffected. Handlers are unaffected — persistence is transparent. The state file is overwritten on each change (single file per run, not one per step).

### Architectural Schema Changes

```yaml
types:
    App:
      kind: class
      fields:
        - handlers: dict
        - log_dir: str
        - worktree_dir: str
        - state_dir: str  # New field, default ".antkeeper/state/"
    Runner:
      kind: class
      methods:
        - _persist_state(state: State) -> None  # New private method
```

## Relevant Files

- `src/antkeeper/core/app.py` — `App.__init__` needs `state_dir` parameter. `run_workflow` needs to call `runner._persist_state(state)` after each step.
- `src/antkeeper/core/runner.py` — `Runner.__init__` needs to create the state directory and compute the state file path. Add `_persist_state` method. `Runner.run()` needs to persist after initial state creation and after handler returns.
- `tests/core/test_logging.py` — `TestAppConfiguration` needs tests for `state_dir` default and custom values.
- `tests/conftest.py` — `app` fixture needs to include a temp `state_dir`.

### New Files

- `tests/core/test_state_persistence.py` — Tests for state persistence behaviour.

## Workflow

### Step 1: Add `state_dir` to `App`

- Add `state_dir: str = ".antkeeper/state/"` parameter to `App.__init__`.
- Store as `self.state_dir`.

### Step 2: Add state persistence to `Runner`

- In `Runner.__init__`, create the state directory with `os.makedirs(app.state_dir, exist_ok=True)`.
- Compute the state file path using the same timestamp and run_id pattern as the log file: `{timestamp}-{run_id}.json`. Use the same `datetime.now()` call that already exists for the log filename — extract the timestamp to a local variable so both filenames share it.
- Store the path as `self._state_path`.
- Add a `_persist_state(self, state: State) -> None` method that writes `json.dump(state, f, indent=2)` to `self._state_path`. This overwrites the file each time (latest state snapshot).
- In `Runner.run()`, call `self._persist_state(state)` after creating the initial state dict and again after the handler returns.

### Step 3: Add state persistence to `run_workflow`

- In `run_workflow()`, after each `state = step(runner, state)` call, add `runner._persist_state(state)`.

### Step 4: Update `app` fixture

- In `tests/conftest.py`, add `state_dir=tempfile.mkdtemp()` to the `App()` call in the `app` fixture.

### Step 5: Add App configuration tests

- In `tests/core/test_logging.py` `TestAppConfiguration`, add:
  - `test_app_state_dir_defaults_to_antkeeper_state` — assert `App().state_dir == ".antkeeper/state/"`
  - `test_app_state_dir_accepts_custom_value` — assert custom value is stored

### Step 6: Add state persistence tests

- Create `tests/core/test_state_persistence.py` with tests described in the Testing Strategy below.

### Step 7: Validate

- Run validation commands below.

## Testing Strategy

### Unit Tests

In `tests/core/test_state_persistence.py`:

- **`test_runner_creates_state_directory`** — Create a Runner via `runner_factory`, assert `os.path.isdir(app.state_dir)`.
- **`test_runner_creates_state_file_on_run`** — Register a noop handler, run it, assert a `.json` file exists in `app.state_dir` with the correct name pattern `{timestamp}-{run_id}.json`.
- **`test_state_file_contains_initial_state_keys`** — Register a noop handler (returns state unchanged), run it, read the JSON file, assert it contains `run_id` and `workflow_name` keys.
- **`test_state_file_reflects_handler_changes`** — Register a handler that adds a key, run it, read the JSON file, assert the added key is present in the persisted state.
- **`test_state_file_updated_after_each_run_workflow_step`** — Register a two-step workflow using `run_workflow`. The first step adds `"step1": True`, the second reads the state file and asserts `"step1"` is already persisted (proving persistence happened after step 1). Alternatively: mock `_persist_state` and assert call count equals expected number (initial + per-step + final).
- **`test_state_file_name_matches_log_file_name`** — Create a Runner, glob for `.log` and `.json` files, assert both have the same `{timestamp}-{run_id}` stem.

In `tests/core/test_logging.py` `TestAppConfiguration`:

- **`test_app_state_dir_defaults_to_antkeeper_state`**
- **`test_app_state_dir_accepts_custom_value`**

### Edge Cases

- Handler raises an exception — state file should contain the last successfully persisted state (initial state). No special handling needed; the exception propagates before the post-handler persist call.
- State contains non-JSON-serializable values — let `json.dump` raise `TypeError` naturally. This is a handler error, not a framework error.

## Acceptance Criteria

- `App()` has `state_dir` defaulting to `".antkeeper/state/"`
- `App(state_dir="custom/")` stores the custom path
- `Runner.__init__` creates the state directory
- `Runner.run()` persists state after initial creation and after handler returns
- `run_workflow()` persists state after each step
- State file is named `{YYYYMMDDhhmmss}-{run_id}.json` in `app.state_dir`
- State file contains valid JSON matching the current state dict
- All existing tests continue to pass
- `app` fixture includes temp `state_dir`

### Validation Commands

```bash
uv run -m pytest tests/ -v
just ruff
just ty
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- The state file is overwritten on each persist (not appended). This keeps it simple — one file per run with the latest snapshot.
- The timestamp in the filename is set once in `Runner.__init__` (shared with the log file), so the state and log files have identical stems for easy correlation.
- `json.dump` with `indent=2` for readability. No custom serializer — if state contains non-serializable values, that's a handler bug.
- `_persist_state` is a private method (underscore prefix) since it's framework internals, but `run_workflow` accesses it directly since both are in the core package.

## Report

Report: files changed (with line-level summary), tests added (count and names), validation command results (pass/fail counts). Confirm state file is written at each expected point by citing the test that verifies it. Max 200 words.
