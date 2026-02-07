# Application Documentation Index

This directory contains policy and pattern documentation for the Antkeeper workflow framework.

## Files

- **testing_policy.md** - Testing approach, fixture management, test structure rules, and test organization. Covers how to write tests for the framework core, including the `app` fixture for log, worktree, and state isolation, the `git_repo` fixture for git worktree tests, patterns for testing git operations and state persistence, CLI testing patterns (argument parsing vs integration tests), API channel testing patterns (ApiChannel unit tests with FastAPI TestClient), SlackChannel testing patterns (mocking httpx), and Slack server testing patterns (AsyncMock, env patching, deterministic timers).

- **instrumentation.md** - Progress reporting, error handling (including `WorkflowFailedError`), run identification, logging patterns, automatic state persistence, and git worktree isolation. Explains the Channel interface for I/O (CliChannel, ApiChannel, SlackChannel), how handlers communicate status, per-run file-based logging, automatic JSON state persistence with correlation to log files, error handling differences between CLI and API execution, the `Worktree` class for git operations, the `git_worktree` context manager for cwd restoration guarantees, and worktree naming conventions.

- **http_server.md** - HTTP server architecture and endpoint design. Covers the standard FastAPI pattern in `server.py` (routes defined with `@api.post()` decorators), the `http/__init__.py` module exporting `run_workflow_background()` to break circular imports, `webhook.py` exporting `handle_webhook()` function, `slack_events.py` exporting `SlackEventProcessor` class with explicit state management, background task execution patterns, and the factory pattern in `create_app()`.

- **slack.md** - Slack integration: app configuration (bot token, user ID), event handling via POST `/slack_event`, the `SlackEventProcessor` class managing debounce state, debounce logic for rapid @mentions (`SLACK_COOLDOWN_SECONDS`), `PendingMessage` dataclass, event routing order (thread replies, edits, deletes, mentions), `SlackChannel` for thread-based replies, timer reset behavior, and environment variable setup (`.env` support).

## Usage

These docs describe **how the framework works** and **policies for extending it**, not how to use it as a library. For usage documentation, see the main [README.md](../README.md).

If you're writing framework code (in `src/antkeeper/core/`, `src/antkeeper/channels/`, `src/antkeeper/http/`, or `src/antkeeper/llm/`), read these docs.

If you're writing application handlers, see the "Writing Handlers" section in the main README.
