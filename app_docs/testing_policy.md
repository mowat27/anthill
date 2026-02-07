# Testing Policy

## Philosophy

Test the framework, not the app. The core machinery (`anthill.core.*`) is the unit under test. User-defined handlers exist only as test data to exercise the framework.

## Test Structure

### Each Test Owns Its Setup

Build the `App`, register handlers, and wire the `Runner` inside each test. No shared global state. This makes test scope explicit and prevents coupling between test cases.

```python
def test_single_handler(runner_factory):
    app = App()

    @app.handler
    def my_handler(runner, state: State) -> State:
        return {**state, "result": state["result"] + 1}

    runner, source = runner_factory(app, "my_handler", {"result": 10})
    result = runner.run()
    assert result["result"] == 11
```

### Replace I/O at the Boundary

Swap channels that do I/O (stdout, stderr) with capturing doubles that collect into lists. Match the interface via duck typing (no inheritance required).

**TestChannel** is the primary test double, defined in `tests/conftest.py`:
- Captures `report_progress()` calls into `progress_messages: list[str]`
- Captures `report_error()` calls into `error_messages: list[str]`
- Provides initial state without external dependencies

**runner_factory** is a pytest fixture that creates `(Runner, TestChannel)` pairs for tests:

```python
runner, source = runner_factory(app, "workflow_name", {"initial": "state"})
```

## Test Coverage Rules

### One Test Per Code Path

If two tests traverse the same core path with different data, they're the same test. A single-handler workflow is one path regardless of what the handler computes.

Focus on:
- Single handler execution
- Multi-step workflow composition via `run_workflow()`
- Error propagation (SystemExit)
- Handler resolution (unknown workflow names)

Avoid testing:
- Handler business logic (that's app code, not framework code)
- Different data values through the same path
- I/O formatting details (those belong in channel-specific tests)

## Running Tests

```bash
uv run -m pytest tests/ -v
```

Run via justfile:
```bash
just test
```

## Test Organization

Tests mirror source layout:
```
tests/
├── core/              # Tests for src/anthill/core/
├── channels/          # Tests for src/anthill/channels/
├── helpers/           # Tests for src/anthill/helpers/
├── llm/               # Tests for src/anthill/llm/
├── git/               # Tests for src/anthill/git/
│   ├── conftest.py    # git_repo fixture
│   ├── test_worktree.py      # Worktree class tests
│   └── test_context.py       # git_worktree context manager tests
└── test_cli.py        # Tests for src/anthill/cli.py
```

### CLI Testing Patterns

CLI tests are split into two categories:

**Argument parsing tests** (`TestArgParsing`) - Test argparse behavior in isolation:
- Build a parser mirror in `_build_parser()` to avoid loading the full CLI machinery
- Test flag parsing, mutual exclusion, and invalid input handling
- Use `pytest.raises(SystemExit)` for argparse error cases

**Integration tests** (`TestCliIntegration`) - Test end-to-end CLI execution:
- Create temp files for handlers and input files
- Use `monkeypatch.setattr("sys.argv", ...)` to simulate CLI invocation
- Use `capsys` to capture stdout/stderr
- Clean up temp files in `finally` blocks

For file-based inputs (e.g., `--prompt-file`), integration tests should write known content to a temp file and verify it flows through to the handler state.

## Fixture Management

All shared fixtures live in `tests/conftest.py`:
- `app` - Returns `App(log_dir=tempfile.mkdtemp(), worktree_dir=tempfile.mkdtemp())` per test for log and worktree isolation
- `runner_factory` - Creates Runner + TestChannel pairs, accepts optional `app` parameter
- `TestChannel` - In-memory channel double for capturing I/O

Git-specific fixtures live in `tests/git/conftest.py`:
- `git_repo` - Creates a temp git repository with an initial commit, sets up git config (user.name, user.email), changes cwd into the repo, and restores original cwd on teardown. Use this for tests that exercise git worktree operations.

Keep fixture scope minimal. Prefer function-scoped fixtures to session-scoped unless there's a compelling performance reason.

### Log and Worktree Isolation in Tests

The `app` fixture directs logs and worktrees to temp directories per test, preventing files from accumulating in the working directory. Tests that create Runners or use worktrees should use the `app` fixture:

```python
def test_something(app, runner_factory):
    runner, source = runner_factory(app, "workflow", {})
    # Log files go to app.log_dir (temp directory)
    # Worktrees go to app.worktree_dir (temp directory)
```

### Git Worktree Testing Patterns

Tests for git worktree functionality should use the `git_repo` fixture from `tests/git/conftest.py`. This fixture:
- Creates a temp directory with a fully initialized git repository
- Adds an initial commit (required for worktree operations)
- Configures local git identity (user.name, user.email) for CI compatibility
- Changes cwd into the repository for the test duration
- Restores the original cwd on teardown

Example:
```python
def test_worktree_create(git_repo):
    wt = Worktree(base_dir="trees", name="feature")
    wt.create(branch="feat/new")
    assert wt.exists
```

Tests for the `git_worktree` context manager should verify:
- Worktree creation (with and without branch)
- Cwd switching and restoration
- Error handling for missing worktrees
- Cleanup behavior (remove=True/False)
