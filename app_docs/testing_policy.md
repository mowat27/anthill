# Testing Policy

## Philosophy

Test the framework, not the app. The core machinery (`antkeeper.core.*`) is the unit under test. User-defined handlers exist only as test data to exercise the framework.

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
- Error propagation (WorkflowFailedError)
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
├── core/              # Tests for src/antkeeper/core/
├── channels/          # Tests for src/antkeeper/channels/
│   └── test_slack_channel.py  # SlackChannel unit tests
├── helpers/           # Tests for src/antkeeper/helpers/
├── llm/               # Tests for src/antkeeper/llm/
├── git/               # Tests for src/antkeeper/git/
│   ├── conftest.py    # git_repo fixture
│   ├── test_worktree.py      # Worktree class tests
│   └── test_context.py       # git_worktree context manager tests
├── test_cli.py        # Tests for src/antkeeper/cli.py
└── test_slack_server.py  # Tests for Slack event endpoint
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
- Test error handling: CLI catches `WorkflowFailedError`, prints to stderr, exits with code 1

For file-based inputs (e.g., `--prompt-file`), integration tests should write known content to a temp file and verify it flows through to the handler state.

### API Channel Testing Patterns

API channel tests follow the same test double pattern as CLI channel:

**ApiChannel unit tests** (`tests/channels/test_api_channel.py`):
- Test channel type identifier
- Test initial state handling (parametrized for None default)
- Test progress output goes to stdout with correct format
- Test error output goes to stderr using delegation pattern

**Server endpoint tests** (`tests/test_server.py`):
- Use FastAPI's `TestClient` from `httpx` package
- Create fixture with temp agents file containing test handlers
- Test successful workflow triggering returns run_id
- Test unknown workflow names return 404
- Test invalid request bodies return 422 validation errors
- Each test cleans up temp files in fixture teardown

### SlackChannel Testing Patterns

SlackChannel tests (`tests/channels/test_slack_channel.py`) mock the HTTP transport layer:

**Mock httpx.Client.post** - Patch `antkeeper.channels.slack.httpx.Client` to intercept Slack API calls without network I/O:

```python
@patch("antkeeper.channels.slack.httpx.Client")
def test_report_progress_posts_to_slack_thread(self, mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
    mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

    channel = SlackChannel("wf", slack_token="xoxb-test", channel_id="C123", thread_ts="1234.5678")
    channel.report_progress("run1", "step done")

    mock_client.post.assert_called_once_with(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": "Bearer xoxb-test"},
        json={"channel": "C123", "thread_ts": "1234.5678", "text": "[wf, run1] step done"},
    )
```

**HTTP failure resilience** - Verify that `httpx.HTTPError` is caught and logged, not raised:

```python
@patch("antkeeper.channels.slack.httpx.Client")
def test_report_progress_survives_http_failure(self, mock_client_cls):
    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.HTTPError("connection failed")
    mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
    mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)

    channel = SlackChannel("wf", slack_token="xoxb-test", channel_id="C123", thread_ts="1234.5678")
    channel.report_progress("run1", "step done")  # should not raise
```

Tests cover: channel type identifier, initial state handling (parametrized for None default), progress message format, error message `[ERROR]` prefix, and HTTP failure resilience.

### Slack Server Testing Patterns

Slack event endpoint tests (`tests/test_slack_server.py`) exercise the `/slack_event` POST route:

**Mock slack_api** - Patch `antkeeper.http.slack_events.slack_api` with `AsyncMock` to intercept all Slack API calls (reactions, chat.postMessage) without network I/O:

```python
api_mock = AsyncMock(return_value={"ok": True})
slack_api_patch = patch("antkeeper.http.slack_events.slack_api", api_mock)
```

**Environment variable patching** - Use `patch.dict(os.environ, {...})` to inject required Slack env vars (`SLACK_BOT_TOKEN`, `SLACK_BOT_USER_ID`, `SLACK_COOLDOWN_SECONDS`):

```python
env_patch = patch.dict(os.environ, {
    "SLACK_BOT_TOKEN": "xoxb-test",
    "SLACK_BOT_USER_ID": "U_BOT",
    "SLACK_COOLDOWN_SECONDS": "0",
})
```

**Testing without environment variables** - Use a separate `slack_client_no_env` fixture to test behavior when environment variables are missing. This fixture creates a test client with only `SLACK_COOLDOWN_SECONDS` set, then explicitly pops `SLACK_BOT_TOKEN` and `SLACK_BOT_USER_ID` from `os.environ` after calling `create_app()`. This approach handles the case where `dotenv.load_dotenv()` might have loaded these variables from a `.env` file:

```python
@pytest.fixture
def slack_client_no_env(self):
    with patch.dict(os.environ, {"SLACK_COOLDOWN_SECONDS": "0"}):
        app = create_app("tests/fixtures/handlers.py")
        # Remove vars after create_app() in case dotenv loaded them
        os.environ.pop("SLACK_BOT_TOKEN", None)
        os.environ.pop("SLACK_BOT_USER_ID", None)
        yield TestClient(app)
```

This pattern ensures clean isolation even when a `.env` file exists in the project directory.

**Deterministic timers** - Set `SLACK_COOLDOWN_SECONDS=0` to eliminate debounce delays. For tests that verify debounce behavior (deduplication, edits, replies), override to a large value (`9999`) so the timer never fires during the test:

```python
@patch.dict(os.environ, {"SLACK_COOLDOWN_SECONDS": "9999"})
def test_duplicate_event_deduplication(self, slack_client):
    ...
```

**Timer task completion** - For tests that verify timer-fired workflow dispatch, use `time.sleep(0.2)` after sending the event to allow the background asyncio timer task to complete before asserting on mock calls.

Tests cover: URL verification challenge response (with and without env vars), environment variable validation (missing both, missing token only, missing user ID only), bot self-message filtering, mention acknowledgement (reaction), event deduplication, message edit updates, thread reply appending (with and without files), message deletion, timer-fired workflow dispatch, unknown workflow error posting, unknown event type handling, and orphan thread reply filtering.

## Fixture Management

All shared fixtures live in `tests/conftest.py`:
- `app` - Returns `App(log_dir=tempfile.mkdtemp(), worktree_dir=tempfile.mkdtemp(), state_dir=tempfile.mkdtemp())` per test for log, worktree, and state isolation
- `runner_factory` - Creates Runner + TestChannel pairs, accepts optional `app` parameter
- `TestChannel` - In-memory channel double for capturing I/O

Git-specific fixtures live in `tests/git/conftest.py`:
- `git_repo` - Creates a temp git repository with an initial commit, sets up git config (user.name, user.email), changes cwd into the repo, and restores original cwd on teardown. Use this for tests that exercise git worktree operations.

Keep fixture scope minimal. Prefer function-scoped fixtures to session-scoped unless there's a compelling performance reason.

### Log, Worktree, and State Isolation in Tests

The `app` fixture directs logs, worktrees, and state files to temp directories per test, preventing files from accumulating in the working directory. Tests that create Runners should use the `app` fixture:

```python
def test_something(app, runner_factory):
    runner, source = runner_factory(app, "workflow", {})
    # Log files go to app.log_dir (temp directory)
    # Worktrees go to app.worktree_dir (temp directory)
    # State files go to app.state_dir (temp directory)
```

### State Persistence Testing Patterns

Tests for state persistence (`tests/core/test_state_persistence.py`) verify:
- State directory creation
- State file naming pattern matches log files (`{timestamp}-{run_id}.json`)
- State file contains correct JSON keys (run_id, workflow_name, handler additions)
- State persisted after each `run_workflow()` step
- Handlers can read persisted state mid-workflow to verify persistence timing

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
