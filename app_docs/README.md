# Application Documentation Index

This directory contains policy and pattern documentation for the Anthill workflow framework.

## Files

- **testing_policy.md** - Testing approach, fixture management, test structure rules, and test organization. Covers how to write tests for the framework core, including the `app` fixture for log and worktree isolation, the `git_repo` fixture for git worktree tests, and patterns for testing git operations.

- **instrumentation.md** - Progress reporting, error handling, run identification, logging patterns, state persistence, and git worktree isolation. Explains the Channel interface for I/O, how handlers communicate status, per-run file-based logging, the `Worktree` class for git operations, the `git_worktree` context manager for cwd restoration guarantees, and worktree naming conventions.

## Usage

These docs describe **how the framework works** and **policies for extending it**, not how to use it as a library. For usage documentation, see the main [README.md](../README.md).

If you're writing framework code (in `src/anthill/core/`, `src/anthill/channels/`, or `src/anthill/llm/`), read these docs.

If you're writing application handlers, see the "Writing Handlers" section in the main README.
