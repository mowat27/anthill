# feature: Add git worktree support for isolated workflows

- Add `Worktree` class and `worktree_context` context manager wrapping git worktree subprocess operations.
- Add `worktree_dir` to `App` constructor (like `log_dir`) and a new `sdlc_worktree` composite workflow.
- Context manager guarantees cwd restore via try/finally, optionally creates/removes worktrees.

## Solution Design

### External Interface Change

After this change, handlers can isolate workflow execution inside git worktrees. The `App` gains a `worktree_dir` configuration, and `handlers.py` gains a new `sdlc_worktree` workflow that runs specify/implement/document inside a freshly created worktree.

**CLI usage (new workflow):**
```
anthill run sdlc_worktree --model opus --prompt "Add dark mode toggle"
```

**Justfile usage:**
```
just sdlc_worktree "Add dark mode toggle"
```

**Handler composition example:**
```python
from anthill.worktrees import Worktree, worktree_context

wt = Worktree(base_dir=runner.app.worktree_dir, name="20260207-a1b2c3d4")
with worktree_context(wt, create=True, branch="feature/dark-mode", remove=False):
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
      - worktree_dir: str  # New field, default "agents/worktrees/"

  Worktree:
    kind: class
    constructor:
      - base_dir: str
      - name: str
    fields:
      - base_dir: str
      - name: str
      - path: str  # os.path.abspath(os.path.join(base_dir, name))
    properties:
      - exists: bool  # os.path.isdir(self.path)
    methods:
      - create(branch: str | None = None) -> None
      - remove() -> None

  worktree_context:
    kind: contextmanager
    parameters:
      - worktree: Worktree
      - create: bool = False  # keyword-only
      - branch: str | None = None  # keyword-only
      - remove: bool = False  # keyword-only
    yields: Worktree
    raises:
      - WorktreeError  # when create=False and worktree doesn't exist

  WorktreeError:
    kind: exception
    bases: [Exception]
```

## Relevant Files

- `src/anthill/core/app.py` — Add `worktree_dir` parameter to `App.__init__`. Store it as `self.worktree_dir`.
- `handlers.py` — Add `derive_feature` handler and `sdlc_worktree` composite workflow. Add imports for `Worktree`, `worktree_context`, `datetime`.
- `tests/conftest.py` — Update `app` fixture to include `worktree_dir=tempfile.mkdtemp()`.
- `tests/core/test_logging.py` — Add tests for `App(worktree_dir=...)` default and custom values.
- `justfile` — Add `sdlc_worktree` recipe.
- `app_docs/testing_policy.md` — Add `tests/worktrees/` to test organization tree.

### New Files

- `src/anthill/worktrees.py` — Single module containing `WorktreeError`, `Worktree` class, and `worktree_context` context manager.
- `tests/worktrees/__init__.py` — Empty test package init.
- `tests/worktrees/test_worktree.py` — Unit tests for `Worktree` class (create, remove, exists, path).
- `tests/worktrees/test_context.py` — Unit tests for `worktree_context` context manager.

## Workflow

### Step 1: Add `worktree_dir` to App

- In `src/anthill/core/app.py`, add `worktree_dir: str = "agents/worktrees/"` parameter to `App.__init__`.
- Store as `self.worktree_dir = worktree_dir`.
- No other changes to core.

### Step 2: Create worktrees module

- Create `src/anthill/worktrees.py` containing all three components in a single file:

**`WorktreeError`**: Simple exception class inheriting from `Exception`. Used when the context manager is asked to enter a non-existent worktree (create=False).

**`Worktree` class**:
- `__init__(self, base_dir: str, name: str)` — Stores `base_dir`, `name`, computes `self.path = os.path.abspath(os.path.join(base_dir, name))`. Use `os.path.abspath()` to ensure paths remain valid after `os.chdir()`.
- `exists` property — Returns `os.path.isdir(self.path)`.
- `create(self, branch: str | None = None)` — Runs `git worktree add -b <branch> <path>` if branch is provided, or `git worktree add <path>` if not. Use `subprocess.run(cmd, capture_output=True, text=True)` and check `returncode`. On failure, raise `WorktreeError` with the stderr message (matching the `AgentExecutionError` pattern in `llm/claude_code.py`). Call `os.makedirs(self.base_dir, exist_ok=True)` before the git command to ensure the parent directory exists.
- `remove(self)` — Runs `git worktree remove <path>`. Same error handling pattern.

**`worktree_context` context manager** (using `@contextmanager`):
```python
@contextmanager
def worktree_context(
    worktree: Worktree,
    *,
    create: bool = False,
    branch: str | None = None,
    remove: bool = False,
) -> Generator[Worktree, None, None]:
    original_dir = os.getcwd()
    if create:
        worktree.create(branch=branch)
    elif not worktree.exists:
        raise WorktreeError(f"Worktree does not exist: {worktree.path}")
    os.chdir(worktree.path)
    try:
        yield worktree
    finally:
        os.chdir(original_dir)
        if remove:
            worktree.remove()
```

Key behaviors:
- Creation/validation happens BEFORE the try block. If `create()` fails or the worktree doesn't exist, the exception propagates without entering the try/finally — no need to restore cwd since it was never changed.
- `os.chdir(worktree.path)` happens BEFORE the try block. If chdir fails (shouldn't happen since create succeeded), the original dir doesn't need restoring.
- Inside the try/finally: yield the worktree, then ALWAYS restore cwd in finally. If `remove=True`, remove after restoring cwd (so we're not inside the worktree when removing it).
- Exceptions from user code propagate normally. The finally block only does chdir (which won't fail since original_dir exists) and optionally remove.

### Step 3: Add `derive_feature` handler

- In `handlers.py`, add a `derive_feature` handler following the same pattern as `specify` and `branch`:
  - Creates `ClaudeCodeAgent(model=state.get("model"))`
  - Sends a prompt asking the LLM to derive `feature_type` and `slug` from the user's prompt
  - The prompt should instruct: analyze the prompt, determine if it's a feature/chore/patch/bugfix/refactor, derive a kebab-case slug
  - Uses `extract_json()` to parse the response
  - Returns `{**state, "feature_type": parsed["feature_type"], "slug": parsed["slug"]}`

### Step 4: Add `sdlc_worktree` composite workflow

- In `handlers.py`, add `sdlc_worktree` handler:
  ```python
  @app.handler
  def sdlc_worktree(runner: Runner, state: State) -> State:
      state = derive_feature(runner, state)
      worktree_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{runner.id}"
      branch_name = f"{state['feature_type']}/{state['slug']}"
      wt = Worktree(base_dir=runner.app.worktree_dir, name=worktree_name)
      with worktree_context(wt, create=True, branch=branch_name, remove=False):
          state = run_workflow(runner, state, [specify, implement, document])
      return {**state, "worktree_path": wt.path, "branch_name": branch_name}
  ```
- Key: `remove=False` keeps worktree alive for human review.
- Key: Uses `[specify, implement, document]` — NOT branch, because the branch is created by the worktree.
- Worktree name follows the log file naming pattern (`{timestamp}-{run_id}`).

### Step 5: Update justfile

- Add `sdlc_worktree` recipe:
  ```
  sdlc_worktree prompt model="opus":
    uv run anthill run sdlc_worktree --model {{model}} --prompt "{{prompt}}"
  ```

### Step 6: Update test fixtures

- In `tests/conftest.py`, update the `app` fixture to include `worktree_dir`:
  ```python
  return App(log_dir=tempfile.mkdtemp(), worktree_dir=tempfile.mkdtemp())
  ```

### Step 7: Write tests for Worktree class

- Create `tests/worktrees/__init__.py` (empty).
- Create `tests/worktrees/test_worktree.py` with a `git_repo` fixture and tests (see Testing Strategy).

### Step 8: Write tests for worktree_context

- Create `tests/worktrees/test_context.py` with context manager tests (see Testing Strategy).

### Step 9: Add App configuration tests

- In `tests/core/test_logging.py`, add tests for `App().worktree_dir` default value and custom value.

### Step 10: Update documentation

- Add `tests/worktrees/` to the test organization tree in `app_docs/testing_policy.md`.

### Step 11: Run validation commands

- Run all validation commands and fix any issues to zero errors.

## Testing Strategy

### Fixtures

**`git_repo` fixture** (in `tests/worktrees/conftest.py`):
- Creates a temp directory with `tempfile.mkdtemp()`
- Runs `git init`, configures local `user.name` and `user.email` (for CI)
- Creates a file, `git add .`, `git commit -m "init"`
- Saves original cwd, `os.chdir` into repo
- Yields the repo path
- Restores original cwd in teardown, cleans up temp dir

### Unit Tests

**App configuration** (`tests/core/test_logging.py`):
- `test_app_worktree_dir_default` — `App().worktree_dir == "agents/worktrees/"`
- `test_app_worktree_dir_custom` — `App(worktree_dir="/tmp/wt").worktree_dir == "/tmp/wt"`

**Worktree class** (`tests/worktrees/test_worktree.py`):
- `test_path_joins_base_dir_and_name` — Verifies `wt.path == os.path.abspath(os.path.join(base_dir, name))`
- `test_exists_false_when_not_created` — `wt.exists is False` before `create()`
- `test_create_makes_worktree_on_disk` — After `create()`, `wt.exists is True` and `os.path.isdir(wt.path)`
- `test_create_with_branch` — After `create(branch="feat-x")`, `git -C <path> branch --show-current` returns `"feat-x"`
- `test_create_raises_on_failure` — Creating from a non-git directory raises `WorktreeError`
- `test_create_twice_raises` — Second `create()` on same worktree raises `WorktreeError`
- `test_remove_deletes_worktree` — After `create()` then `remove()`, `wt.exists is False`
- `test_remove_nonexistent_raises` — `remove()` without prior `create()` raises `WorktreeError`

**Context manager** (`tests/worktrees/test_context.py`):
- `test_creates_worktree_when_create_true` — Inside context with `create=True`, worktree exists
- `test_creates_with_branch` — Inside context with `create=True, branch="feat"`, branch is correct
- `test_changes_cwd_to_worktree` — Inside context, `os.getcwd() == wt.path`
- `test_yields_worktree_instance` — `with ... as result: assert result is wt`
- `test_enters_existing_worktree` — Pre-created worktree can be entered with `create=False`
- `test_raises_when_not_exists_and_create_false` — Raises `WorktreeError`
- `test_restores_cwd_on_normal_exit` — After context, `os.getcwd()` is original
- `test_restores_cwd_on_exception` — Exception inside context, cwd still restored
- `test_removes_when_remove_true` — After context with `remove=True`, `wt.exists is False`
- `test_keeps_when_remove_false` — After context with `remove=False`, `wt.exists is True`

### Edge Cases

- Path is absolute (`os.path.abspath`) so it remains valid after chdir
- `create()` ensures `base_dir` exists via `os.makedirs(..., exist_ok=True)`
- `git worktree add -b <branch>` fails if branch already exists — this is correct behavior (error propagates)
- `remove()` after chdir out of worktree succeeds (context manager restores cwd first)
- Exception inside context body does not prevent cwd restoration (try/finally)

## Acceptance Criteria

- `App(worktree_dir="custom/")` stores the worktree directory; default is `"agents/worktrees/"`.
- `Worktree(base_dir, name)` computes an absolute path and provides `create()`, `remove()`, `exists`.
- `worktree_context` switches cwd into worktree and guarantees restoration via `try/finally`.
- `worktree_context` with `create=False` raises `WorktreeError` when worktree doesn't exist.
- `worktree_context` with `create=True` creates the worktree (and optionally a branch).
- `worktree_context` with `remove=True` removes the worktree on exit.
- `derive_feature` handler extracts `feature_type` and `slug` from LLM response into state.
- `sdlc_worktree` handler creates a worktree, runs `[specify, implement, document]` inside it, and leaves it alive.
- `justfile` has `sdlc_worktree` recipe.
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

- **Single file module**: `src/anthill/worktrees.py` contains `WorktreeError`, `Worktree`, and `worktree_context` in one file (~50 LOC). No package directory needed — this keeps the module lightweight.
- **os.chdir is process-wide**: The context manager uses `os.chdir()` which changes the process working directory. This is appropriate for the current single-threaded execution model. If concurrent workflow execution is added later, this would need to be revisited.
- **Errors propagate**: `Worktree.create()` and `Worktree.remove()` raise `WorktreeError` wrapping git stderr. Handler-level errors (missing state keys, git failures) propagate to the Runner as per the framework's error handling philosophy.
- **Branch creation**: `git worktree add -b <branch>` creates a NEW branch. If the branch already exists, git will error — this is intentional (prevents duplicate worktrees on the same branch).
- **Worktree naming**: Uses the same pattern as log files (`{YYYYMMDDHHmmSS}-{run_id}`) for correlation and uniqueness.
- **No branch handler in sdlc_worktree**: The `[specify, implement, document]` pipeline omits `branch` because the worktree creation already handles branch creation.

## Report

Files changed: `src/anthill/core/app.py` (add `worktree_dir` param), `handlers.py` (add `derive_feature` + `sdlc_worktree`), `tests/conftest.py` (update `app` fixture), `tests/core/test_logging.py` (add App config tests), `justfile` (add recipe), `app_docs/testing_policy.md` (add `tests/worktrees/`). Files created: `src/anthill/worktrees.py` (Worktree class, context manager, WorktreeError), `tests/worktrees/__init__.py`, `tests/worktrees/test_worktree.py`, `tests/worktrees/test_context.py`. Tests added: 2 App config, 8 Worktree class, 10 context manager. Validations: pytest, ruff, ty.
