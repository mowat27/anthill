# feature: Add git worktree support for isolated workflows

- Add `Worktree` class and `git_worktree` context manager in `antkeeper.git.worktrees` wrapping git worktree subprocess operations.
- Add `worktree_dir` to `App` constructor (default `trees/`) and `sdlc_iso` composite workflow using worktrees.
- Context manager guarantees cwd restore via try/finally, optionally creates/removes worktrees, fails noisily on missing worktree.

## Solution Design

### External Interface Change

After this change, handlers can isolate workflow execution inside git worktrees. The `App` gains a `worktree_dir` configuration, and `handlers.py` gains `derive_feature` and `sdlc_iso` workflows.

**CLI usage (new workflow):**
```
antkeeper run sdlc_iso --model opus --prompt "Add dark mode toggle"
```

**Handler composition example:**
```python
from antkeeper.git.worktrees import Worktree, git_worktree

wt = Worktree(base_dir=runner.app.worktree_dir, name="20260207-a1b2c3d4")
with git_worktree(wt, create=True, branch="feature/dark-mode", remove=False) as wt:
    state = run_workflow(runner, state, [specify, implement, document])
```

### Architectural Schema Changes

```yaml
types:
  App:
    kind: class
    fields:
      - handlers: dict
      - log_dir: str
      - worktree_dir: str  # New field, default "trees/"

  WorktreeError:
    kind: exception
    bases: [Exception]

  Worktree:
    kind: class
    constructor:
      - base_dir: str
      - name: str
    fields:
      - base_dir: str  # stored as os.path.abspath(base_dir)
      - name: str
      - path: str  # os.path.abspath(os.path.join(base_dir, name))
    properties:
      - exists: bool  # os.path.isdir(self.path)
    methods:
      - create(branch: str | None = None) -> None
      - remove() -> None

  git_worktree:
    kind: contextmanager
    parameters:
      - worktree: Worktree
      - create: bool = False  # keyword-only
      - branch: str | None = None  # keyword-only
      - remove: bool = False  # keyword-only
    yields: Worktree
    raises:
      - WorktreeError  # when create=False and worktree doesn't exist
```

## Relevant Files

- `src/antkeeper/core/app.py` — Add `worktree_dir` parameter to `App.__init__`. Store as `self.worktree_dir`.
- `src/antkeeper/llm/claude_code.py` — Reference for subprocess + error handling pattern (`subprocess.run`, check `returncode`, raise custom error with stderr).
- `src/antkeeper/helpers/json.py` — `extract_json()` used by `derive_feature` handler.
- `handlers.py` — Add `derive_feature` handler and `sdlc_iso` composite workflow.
- `tests/conftest.py` — Update `app` fixture to pass `worktree_dir=tempfile.mkdtemp()`.
- `tests/core/test_logging.py` — Add `App(worktree_dir=...)` configuration tests to existing `TestAppConfiguration`.
- `justfile` — Add `sdlc_iso` recipe.

### New Files

- `src/antkeeper/git/__init__.py` — Re-export `Worktree`, `WorktreeError`, `git_worktree` from `antkeeper.git.worktrees`.
- `src/antkeeper/git/worktrees.py` — `WorktreeError`, `Worktree` class, `git_worktree` context manager.
- `.claude/commands/derive_feature.md` — Slash command that derives feature type and slug from a prompt.
- `tests/git/__init__.py` — Empty test package init.
- `tests/git/conftest.py` — `git_repo` fixture for real git operations in tests.
- `tests/git/test_worktree.py` — Unit tests for `Worktree` class.
- `tests/git/test_context.py` — Unit tests for `git_worktree` context manager.

## Workflow

### Step 1: Add `worktree_dir` to App

- In `src/antkeeper/core/app.py`, add `worktree_dir: str = "trees/"` parameter to `App.__init__`.
- Store as `self.worktree_dir = worktree_dir`.
- No other changes to core.

### Step 2: Create git package and worktrees module

- Create `src/antkeeper/git/__init__.py` that re-exports `Worktree`, `WorktreeError`, `git_worktree` from `.worktrees`.
- Create `src/antkeeper/git/worktrees.py` containing all three components:

**`WorktreeError`**: Simple exception class inheriting from `Exception`.

**Module-level logger**: `logger = logging.getLogger("antkeeper.git.worktrees")` — follow the pattern in `llm/claude_code.py`.

**`Worktree` class**:
- `__init__(self, base_dir: str, name: str)` — Stores `self.base_dir = os.path.abspath(base_dir)`, `self.name = name`, computes `self.path = os.path.abspath(os.path.join(base_dir, name))`.
- `exists` property — Returns `os.path.isdir(self.path)`.
- `create(self, branch: str | None = None)` — Calls `os.makedirs(self.base_dir, exist_ok=True)`. Builds command: `["git", "worktree", "add"]` with `["-b", branch]` if branch provided, then appends `self.path`. Runs `subprocess.run(cmd, capture_output=True, text=True)`. If `result.returncode != 0`, raises `WorktreeError` with stderr. Logs creation at INFO level.
- `remove(self)` — Runs `subprocess.run(["git", "worktree", "remove", self.path], capture_output=True, text=True)`. If `result.returncode != 0`, raises `WorktreeError` with stderr. Logs removal at INFO level.

**`git_worktree` context manager** (using `@contextmanager`):
```python
@contextmanager
def git_worktree(
    worktree: Worktree,
    *,
    create: bool = False,
    branch: str | None = None,
    remove: bool = False,
) -> Generator[Worktree, None, None]:
    if create:
        worktree.create(branch=branch)
    elif not worktree.exists:
        raise WorktreeError(f"Worktree does not exist: {worktree.path}")
    original_dir = os.getcwd()
    os.chdir(worktree.path)
    try:
        yield worktree
    finally:
        os.chdir(original_dir)
        if remove:
            worktree.remove()
```

Key behaviors:
- Creation/validation happens BEFORE `os.chdir` and BEFORE the try block. If `create()` fails or the worktree doesn't exist, the exception propagates without needing cwd restoration since cwd was never changed.
- `os.chdir(worktree.path)` happens before try. If chdir fails after create, the exception propagates — cwd is unchanged.
- Inside try/finally: yield worktree, then ALWAYS restore cwd in finally. If `remove=True`, remove after restoring cwd (so we're not inside the worktree when removing it).
- `worktree.remove()` in finally can raise `WorktreeError` — this is appropriate since it indicates a real problem that should not be silently swallowed. Per the framework's error propagation philosophy, let it bubble up.

### Step 3: Create derive_feature slash command

- Create `.claude/commands/derive_feature.md` — A slash command that:
  - Takes a feature description as input
  - Determines the feature type (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`)
  - Generates a kebab-case slug (e.g., `add-worktree-support`)
  - Returns ONLY a JSON object: `{"feature_type": "...", "slug": "..."}`
  - Similar in structure to `.claude/commands/branch.md` but does NOT create a branch

### Step 4: Add `derive_feature` handler

- In `handlers.py`, add a `derive_feature` handler following the existing handler pattern:
  - `runner.report_progress("Deriving feature metadata")`
  - Creates `ClaudeCodeAgent(model=state.get("model"))`
  - Sends prompt: `/derive_feature {state["prompt"]}` with instruction to return JSON
  - Uses `extract_json()` to parse the response
  - Logs prompt and response via `runner.logger`
  - `runner.report_progress("Feature metadata derived")`
  - Returns `{**state, "feature_type": parsed["feature_type"], "slug": parsed["slug"]}`

### Step 5: Add `sdlc_iso` composite workflow

- In `handlers.py`, add `sdlc_iso` handler:
  ```python
  @app.handler
  def sdlc_iso(runner: Runner, state: State) -> State:
      state = derive_feature(runner, state)
      worktree_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{runner.id}"
      branch_name = f"{state['feature_type']}/{state['slug']}"
      wt = Worktree(base_dir=runner.app.worktree_dir, name=worktree_name)
      with git_worktree(wt, create=True, branch=branch_name, remove=False):
          state = run_workflow(runner, state, [specify, implement, document])
      return {**state, "worktree_path": wt.path, "branch_name": branch_name}
  ```
- Key: `remove=False` keeps worktree alive for human review.
- Key: Uses `[specify, implement, document]` — NOT `branch`, because the worktree creation already handles branch creation.
- Worktree name follows the log file naming pattern (`{timestamp}-{run_id}`) for correlation.

### Step 6: Update justfile

- Add `sdlc_iso` recipe following the same pattern as existing `sdlc`:
  ```
  sdlc_iso prompt model="opus":
    #!/usr/bin/env bash
    if [ -f "{{prompt}}" ]; then
      uv run antkeeper run sdlc_iso --model {{model}} --prompt-file "{{prompt}}"
    else
      uv run antkeeper run sdlc_iso --model {{model}} --prompt "{{prompt}}"
    fi
  ```

### Step 7: Update test fixtures

- In `tests/conftest.py`, update the `app` fixture to include `worktree_dir`:
  ```python
  return App(log_dir=tempfile.mkdtemp(), worktree_dir=tempfile.mkdtemp())
  ```

### Step 8: Add App configuration tests

- In `tests/core/test_logging.py`, add to `TestAppConfiguration`:
  - `test_app_worktree_dir_defaults_to_trees` — `App().worktree_dir == "trees/"`
  - `test_app_worktree_dir_accepts_custom_value` — `App(worktree_dir="/tmp/wt").worktree_dir == "/tmp/wt"`

### Step 9: Create git_repo fixture and write Worktree tests

- Create `tests/git/__init__.py` (empty).
- Create `tests/git/conftest.py` with `git_repo` fixture:
  - Creates temp directory with `tempfile.mkdtemp()`
  - Runs `git init`, configures local `user.name` and `user.email` (for CI)
  - Creates a file, `git add .`, `git commit -m "init"`
  - Saves original cwd, `os.chdir` into repo
  - Yields the repo path
  - Restores original cwd in teardown

- Create `tests/git/test_worktree.py` with tests (see Testing Strategy).

### Step 10: Write context manager tests

- Create `tests/git/test_context.py` with context manager tests (see Testing Strategy).

### Step 11: Run validation commands

- Run all validation commands and fix any issues to zero errors.

## Testing Strategy

### Unit Tests

**App configuration** (`tests/core/test_logging.py`):
- `test_app_worktree_dir_defaults_to_trees` — `App().worktree_dir == "trees/"`
- `test_app_worktree_dir_accepts_custom_value` — `App(worktree_dir="/tmp/wt").worktree_dir == "/tmp/wt"`

**Worktree class** (`tests/git/test_worktree.py`) — all use `git_repo` fixture:
- `test_path_is_absolute_join_of_base_dir_and_name` — `wt.path == os.path.abspath(os.path.join(base_dir, name))`
- `test_exists_false_when_not_created` — `wt.exists is False` before `create()`
- `test_create_makes_worktree_on_disk` — After `create()`, `wt.exists is True`
- `test_create_with_branch` — After `create(branch="feat-x")`, `git -C <path> branch --show-current` returns `"feat-x"`
- `test_create_makes_base_dir` — `create()` with non-existent base_dir creates it
- `test_create_raises_worktree_error_on_failure` — Creating same worktree twice raises `WorktreeError`
- `test_remove_deletes_worktree` — After `create()` then `remove()`, `wt.exists is False`
- `test_remove_nonexistent_raises_worktree_error` — `remove()` without prior `create()` raises `WorktreeError`

**Context manager** (`tests/git/test_context.py`) — all use `git_repo` fixture:
- `test_creates_worktree_when_create_true` — Inside context with `create=True`, worktree exists
- `test_creates_with_branch` — Inside context with `create=True, branch="feat"`, branch is correct
- `test_changes_cwd_to_worktree` — Inside context, `os.getcwd() == wt.path`
- `test_yields_worktree_instance` — `with ... as result: assert result is wt`
- `test_enters_existing_worktree` — Pre-created worktree can be entered with `create=False`
- `test_raises_worktree_error_when_not_exists_and_create_false` — Raises `WorktreeError`
- `test_restores_cwd_on_normal_exit` — After context, `os.getcwd()` is original
- `test_restores_cwd_on_exception` — Exception inside context, cwd still restored
- `test_removes_when_remove_true` — After context with `remove=True`, `wt.exists is False`
- `test_keeps_when_remove_false` — After context with `remove=False`, `wt.exists is True`

### Edge Cases

- Path is absolute (`os.path.abspath`) so it remains valid after chdir
- `create()` ensures `base_dir` exists via `os.makedirs(..., exist_ok=True)`
- `git worktree add -b <branch>` fails if branch already exists — correct behavior (error propagates)
- `remove()` after chdir out of worktree succeeds (context manager restores cwd first)
- Exception inside context body does not prevent cwd restoration (try/finally)

## Acceptance Criteria

- `App(worktree_dir="custom/")` stores the worktree directory; default is `"trees/"`.
- `Worktree(base_dir, name)` computes an absolute path and provides `create()`, `remove()`, `exists`.
- `git_worktree` switches cwd into worktree and guarantees restoration via `try/finally`.
- `git_worktree` with `create=False` raises `WorktreeError` when worktree doesn't exist.
- `git_worktree` with `create=True` creates the worktree (and optionally a branch).
- `git_worktree` with `remove=True` removes the worktree on exit.
- `derive_feature` handler extracts `feature_type` and `slug` from LLM response into state.
- `sdlc_iso` handler creates a worktree, runs `[specify, implement, document]` inside it, and leaves it alive.
- `justfile` has `sdlc_iso` recipe.
- All existing tests pass with the updated `app` fixture.
- New worktree and context manager tests pass.
- Type checks pass (`just ty`).
- Linting passes (`just ruff`).
- All tests pass (`just test`).

### Validation Commands

```bash
# Run all tests
uv run -m pytest tests/ -v

# Type check
uv run ty check

# Lint
uv run ruff check

# Run all checks via justfile
just
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- **Package structure**: `src/antkeeper/git/` with `__init__.py` and `worktrees.py` as specified by the user. The `__init__.py` re-exports for convenience (`from antkeeper.git.worktrees import ...`).
- **os.chdir is process-wide**: The context manager uses `os.chdir()` which changes the process working directory. This is appropriate for the current single-threaded execution model.
- **Errors propagate**: `Worktree.create()` and `Worktree.remove()` raise `WorktreeError` wrapping git stderr. Handler-level errors (missing state keys, git failures) propagate to the Runner per the framework's philosophy.
- **Branch creation**: `git worktree add -b <branch>` creates a NEW branch. If the branch already exists, git will error — this is intentional.
- **Worktree naming**: Uses the same pattern as log files (`{YYYYMMDDHHmmSS}-{run_id}`) for correlation and uniqueness.
- **No branch handler in sdlc_iso**: The `[specify, implement, document]` pipeline omits `branch` because the worktree creation already handles branch creation.
- **Module-level logging**: `antkeeper.git.worktrees` has a module-level logger following the pattern in `llm/claude_code.py`. Logs worktree creation, removal, and context manager entry/exit.

## Report

Files changed: `src/antkeeper/core/app.py` (add `worktree_dir` param), `handlers.py` (add `derive_feature` + `sdlc_iso`), `tests/conftest.py` (update `app` fixture), `tests/core/test_logging.py` (add App config tests), `justfile` (add recipe). Files created: `src/antkeeper/git/__init__.py` (re-exports), `src/antkeeper/git/worktrees.py` (Worktree class, context manager, WorktreeError), `.claude/commands/derive_feature.md` (slash command), `tests/git/__init__.py`, `tests/git/conftest.py` (git_repo fixture), `tests/git/test_worktree.py`, `tests/git/test_context.py`. Tests added: 2 App config, 8 Worktree class, 10 context manager. Validations: pytest, ruff, ty.
