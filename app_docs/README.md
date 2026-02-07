# Application Documentation Index

This directory contains policy and pattern documentation for the Anthill workflow framework.

## Files

- **testing_policy.md** - Testing approach, fixture management, test structure rules, and test organization. Covers how to write tests for the framework core, including the `app` fixture for log, worktree, and state isolation, the `git_repo` fixture for git worktree tests, patterns for testing git operations and state persistence, CLI testing patterns (argument parsing vs integration tests), and API channel testing patterns (ApiChannel unit tests with FastAPI TestClient).

- **instrumentation.md** - Progress reporting, error handling (including `WorkflowFailedError`), run identification, logging patterns, automatic state persistence, and git worktree isolation. Explains the Channel interface for I/O (CliChannel, ApiChannel), how handlers communicate status, per-run file-based logging, automatic JSON state persistence with correlation to log files, error handling differences between CLI and API execution, the `Worktree` class for git operations, the `git_worktree` context manager for cwd restoration guarantees, and worktree naming conventions.

- **http_server.md** - HTTP server architecture, endpoint design, and the factory pattern in `http/__init__.py`. Covers the webhook endpoint (`webhook.py`), the Slack events endpoint (`slack_events.py`), background task execution, and how `server.py` delegates to the `http/` package.

- **slack.md** - Slack integration: app configuration (bot token, user ID), event handling via POST `/slack_event`, debounce logic for rapid @mentions (`SLACK_COOLDOWN_SECONDS`), `SlackChannel` for thread-based replies, and environment variable setup (`.env` support).

## Usage

These docs describe **how the framework works** and **policies for extending it**, not how to use it as a library. For usage documentation, see the main [README.md](../README.md).

If you're writing framework code (in `src/anthill/core/`, `src/anthill/channels/`, `src/anthill/http/`, or `src/anthill/llm/`), read these docs.

If you're writing application handlers, see the "Writing Handlers" section in the main README.
