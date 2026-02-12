# bugfix: git.execute() auto-prepend "git" prefix

- `execute()` should prepend `"git"` to the command list if `cmd[0]` is not already `"git"`
- Both `execute(["status"])` and `execute(["git", "status"])` must work (backward compatible)
- Update `branch.py` caller and documentation to reflect the new behavior

## Solution Design

### Architectural Schema Changes

```yaml
functions:
  execute:
    module: antkeeper.git.core
    args:
      - cmd: list[str]  # "git" prefix now optional; auto-prepended if missing
    returns: str
    raises: GitCommandError
```

## Relevant Files

Use these files to fix the bug:

- `src/antkeeper/git/core.py` — contains `execute()` function that needs the guard added
- `src/antkeeper/git/branch.py` — caller of `execute()` that should be updated to use the shorter form
- `tests/git/test_core.py` — existing tests for `execute()`, needs new tests for without-prefix behavior
- `tests/git/conftest.py` — provides `git_repo` fixture (do NOT modify)
- `app_docs/instrumentation.md` — documents `execute()` API, needs updating

## Workflow

### Step 1: Update `execute()` in `core.py`

- Add a guard at the top of the function body: if `cmd[0] != "git"`, prepend `"git"` by creating a new list `["git"] + cmd`
- Update the docstring to reflect that the `"git"` prefix is optional and will be auto-prepended if missing
- Do NOT add validation for empty lists — per design philosophy, avoid validation for impossible scenarios

The function should become:

```python
def execute(cmd: list[str]) -> str:
    if cmd[0] != "git":
        cmd = ["git"] + cmd
    logger.debug(f"Executing: {cmd}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise GitCommandError(result.stderr.strip())
    return result.stdout.strip()
```

### Step 2: Update `branch.py` caller

- Change `execute(["git", "rev-parse", "--abbrev-ref", "HEAD"])` to `execute(["rev-parse", "--abbrev-ref", "HEAD"])`
- This demonstrates the new API and ensures internal consistency

### Step 3: Add new tests in `test_core.py`

- Keep all 3 existing tests unchanged (they validate backward compatibility with `"git"` prefix)
- Add new tests inside the existing `TestExecute` class for the without-prefix behavior (see Testing Strategy below)

### Step 4: Update `instrumentation.md`

- In the "Git Command Execution" section, update the description of `execute()` to reflect that the `"git"` prefix is optional
- Update the bullet point from "Takes full command as list including `"git"` prefix (no magic prefixing)" to "Automatically prepends `"git"` if not present; accepts commands with or without the prefix"
- Update code examples to show the shorter form as primary and note the explicit prefix form still works

### Step 5: Run validation commands

- Run all validation commands listed below

## Testing Strategy

### Unit Tests

Add these tests to the existing `TestExecute` class in `tests/git/test_core.py`:

- **`test_execute_prepends_git_when_not_present`** — Call `execute(["log", "--oneline"])` (no `"git"` prefix). Assert it returns a non-empty string. Confirms auto-prepend works for the happy path.
- **`test_execute_without_git_prefix_raises_on_failure`** — Call `execute(["checkout", "nonexistent-branch"])` (no `"git"` prefix). Assert `GitCommandError` is raised. Confirms error handling works with auto-prepend.
- **`test_execute_without_git_prefix_returns_empty_string`** — Call `execute(["tag", "-l"])` (no `"git"` prefix). Assert result equals `""`. Confirms empty output works with auto-prepend.

### Integration

The existing tests in `tests/git/test_branch.py` will implicitly exercise the no-prefix path after `branch.py` is updated. No new branch tests needed.

### Edge Cases

- Commands with `"git"` prefix still work (covered by existing tests — backward compatibility)
- Commands without `"git"` prefix work (covered by 3 new tests)
- Error propagation works with both forms (covered by existing + new error test)

## Acceptance Criteria

- `execute(["status"])` and `execute(["git", "status"])` produce identical results
- `execute(["checkout", "nonexistent-branch"])` raises `GitCommandError` (no prefix)
- `branch.current()` still works after updating to use `["rev-parse", "--abbrev-ref", "HEAD"]`
- All existing tests continue to pass unchanged
- All new tests pass
- Documentation accurately describes the new behavior

### Validation Commands

```bash
uv run ruff check src/ tests/
uv run ty check src/
uv run -m pytest tests/ -v
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- Do NOT modify `worktrees.py` — it uses `subprocess.run()` directly, not `execute()`. Converting it is out of scope.
- Do NOT add validation for empty command lists. Per design philosophy, avoid validation for impossible scenarios. An `IndexError` on empty list is appropriate for a programming bug.
- Do NOT handle edge cases like `"/usr/bin/git"` paths or `"git-lfs"` — these are not real usage patterns for this function.
- The original spec (`feature-git-module.md`) noted "avoids magic prefixing" — this bugfix intentionally reverses that decision per user request.

## Report

Report the following on completion:
- Files changed (list all modified files)
- Tests added (count and summary)
- Validation command results (pass/fail for each)
