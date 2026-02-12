# feature: Add git.core and git.branch modules

- Add `git.core` module with generic `execute(cmd)` function for running arbitrary git commands
- Add `git.branch` module with `current()` function to get the current branch name
- Export both via `git/__init__.py`

## Solution Design

### External Interface Change

Handlers and channels gain access to two new git utilities:

```python
from antkeeper.git import execute, current

# Execute any git command
output = execute(["git", "status"])

# Get current branch
branch = current()
```

### Architectural Schema Changes

```yaml
types:
  GitCommandError:
    kind: exception
    parent: Exception
    module: antkeeper.git.core

functions:
  execute:
    module: antkeeper.git.core
    args:
      - cmd: list[str]
    returns: str
    raises: GitCommandError

  current:
    module: antkeeper.git.branch
    args: []
    returns: str
    raises: GitCommandError
```

## Relevant Files

- `src/antkeeper/git/__init__.py` — add new exports (`execute`, `GitCommandError`, `current`)
- `src/antkeeper/git/worktrees.py` — reference for subprocess and error-handling patterns (do NOT modify)
- `tests/git/conftest.py` — provides `git_repo` fixture for new tests (do NOT modify)

### New Files

- `src/antkeeper/git/core.py` — `GitCommandError` exception and `execute()` function
- `src/antkeeper/git/branch.py` — `current()` function
- `tests/git/test_core.py` — tests for `execute()`
- `tests/git/test_branch.py` — tests for `current()`

## Workflow

### Step 1: Create `git/core.py`

- Create `src/antkeeper/git/core.py`
- Define `GitCommandError(Exception)` — raised when a git command exits with non-zero status
- Define `execute(cmd: list[str]) -> str`:
  - Uses `subprocess.run(cmd, capture_output=True, text=True)`
  - Returns `result.stdout.strip()`
  - Raises `GitCommandError(result.stderr.strip())` on non-zero return code
- Use `logging.getLogger("antkeeper.git.core")` — log the command at debug level before execution
- Follow docstring patterns from `worktrees.py` (Args/Returns/Raises sections)

### Step 2: Create `git/branch.py`

- Create `src/antkeeper/git/branch.py`
- Define `current() -> str`:
  - Imports `execute` from `antkeeper.git.core`
  - Calls `execute(["git", "rev-parse", "--abbrev-ref", "HEAD"])`
  - Returns the result directly
  - No additional error handling — let `GitCommandError` propagate
- Follow docstring patterns from `worktrees.py`

### Step 3: Update `git/__init__.py`

- Add imports: `from antkeeper.git.core import GitCommandError, execute`
- Add imports: `from antkeeper.git.branch import current`
- Add `execute`, `GitCommandError`, `current` to `__all__`
- Keep existing exports (`Worktree`, `WorktreeError`, `git_worktree`) unchanged
- Update module docstring to mention the new exports

### Step 4: Write tests

- Create `tests/git/test_core.py` and `tests/git/test_branch.py`
- See Testing Strategy below

### Step 5: Run validation commands

- Run all validation commands listed below

## Testing Strategy

### Unit Tests

#### `tests/git/test_core.py` — `TestExecute` class

- **`test_execute_returns_stdout`** — Call `execute(["git", "log", "--oneline"])` in `git_repo`. Assert result is a non-empty string (the initial commit summary). Confirms stdout is captured and stripped.
- **`test_execute_raises_git_command_error_on_failure`** — Call `execute(["git", "checkout", "nonexistent-branch"])`. Assert `pytest.raises(GitCommandError)`. Optionally check error message contains relevant substring.
- **`test_execute_returns_empty_string_for_silent_command`** — Call `execute(["git", "tag", "-l"])` (no tags exist). Assert result equals `""`.

#### `tests/git/test_branch.py` — `TestCurrent` class

- **`test_current_returns_default_branch`** — Call `current()` in `git_repo`. Independently query git for the expected branch name via `subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"])` to handle both `"main"` and `"master"` depending on git config. Assert match.
- **`test_current_returns_switched_branch`** — In `git_repo`, run `subprocess.run(["git", "checkout", "-b", "feat/test-branch"])` then call `current()`. Assert result equals `"feat/test-branch"`.
- **`test_current_on_detached_head`** — In `git_repo`, run `subprocess.run(["git", "checkout", "--detach"])` then call `current()`. Assert result equals `"HEAD"` (this is what `rev-parse --abbrev-ref` returns in detached HEAD state).

### Integration

No integration tests needed — these are low-level utilities tested directly.

### Edge Cases

- Empty stdout from a successful command (covered by `test_execute_returns_empty_string_for_silent_command`)
- Detached HEAD state (covered by `test_current_on_detached_head`)
- `GitCommandError` propagation from `current()` — not separately tested because `current()` delegates directly to `execute()` with no additional error handling. Testing the same error path twice would violate the one-test-per-path rule.

## Acceptance Criteria

- `execute(["git", "rev-parse", "--abbrev-ref", "HEAD"])` returns the current branch name as a string
- `execute()` raises `GitCommandError` on non-zero exit codes
- `current()` returns the current branch name
- `from antkeeper.git import execute, GitCommandError, current` works
- `worktrees.py` is unchanged
- `src/antkeeper/__init__.py` is unchanged
- All existing tests continue to pass
- All new tests pass

### Validation Commands

```bash
uv run ruff check src/ tests/
uv run ty check src/
uv run -m pytest tests/ -v
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- **Do NOT refactor `worktrees.py`** to use `execute()`. That is out of scope and risks breaking existing behavior.
- **Do NOT add new exports to `src/antkeeper/__init__.py`**. The top-level namespace is for high-level workflow constructs. Git utilities are available via `antkeeper.git`.
- **Do NOT add validation** for empty command lists or None stderr. `subprocess.run` handles these naturally, and the design philosophy says to avoid validation for scenarios that can't happen in practice.
- The `cmd` parameter takes the full command including `"git"` prefix (e.g., `["git", "status"]`). This matches the existing pattern in `worktrees.py` and avoids magic prefixing.
- `GitCommandError` is intentionally separate from `WorktreeError` — they represent different failure domains.

## Report

Report the following on completion:
- Files created (list all new files)
- Files modified (list all changed files)
- Tests added (count and summary)
- Validation command results (pass/fail for each)
