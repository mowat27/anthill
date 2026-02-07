# Antkeeper Framework

Workflow engine. `@app.handler` registers handlers, `Runner` executes.

**State** = `dict[str, Any]`, return new copy. **Channel** = I/O (CliChannel, ApiChannel, SlackChannel). **App** = handler registry. **Runner** = App + Channel. **Agent** = LLM wrapper (`ClaudeCodeAgent` wraps `claude` CLI). **Worktree** = git worktree.

Handlers: `def step(runner: Runner, state: State) -> State`. Chain: `run_workflow(runner, state, [step1, step2])`.

**Logging**: `App(log_dir, worktree_dir, state_dir)` sets dirs (default `agents/logs/`, `trees/`, `.antkeeper/state/`). `Runner` creates `{timestamp}-{run_id}.log` + `{timestamp}-{run_id}.json`. Auto-persist. Use `runner.logger.info()`.

**Git**: `Worktree(base_dir, name)`. `git_worktree(wt, create=True, branch="feat", remove=False)` guarantees cwd restore. Absolute paths.

**HTTP**: `server.py` defines routes, delegates to `http/webhook.py` (`handle_webhook()`), `http/slack_events.py` (`SlackEventProcessor` class). `http/__init__.py` exports `run_workflow_background()`. Slack: env `SLACK_BOT_TOKEN`, `SLACK_BOT_USER_ID`. Handlers file: `ANTKEEPER_HANDLERS_FILE` (`.env` ok).

**Testing**: Mirror source (`tests/core/`, `tests/channels/`, etc). `app` fixture (temp dirs), `runner_factory` (Runner+TestChannel), `git_repo` fixture. Each test owns setup. One test per path. `uv run -m pytest tests/ -v`.

**Handlers**: Steps, shared constants, workflows. Constants only when shared.

**Worktree discipline**: Edit relative to cwd, never IDE paths outside worktree.

**Dev**: `just` = lint+typecheck+test. `uv sync` to install.
