# feature: Add init subcommand to CLI

- `antkeeper init [path]` creates a starter `handlers.py` with healthcheck handler and commented examples
- Prints environment variable guidance to stdout after file creation
- Optional positional path argument defaults to current directory

## Solution Design

### External Interface Change

The CLI gains an `init` subcommand that scaffolds a new project directory:

```bash
# Initialize in current directory
antkeeper init

# Initialize in a specific directory
antkeeper init my_project
```

After creating the file, stdout shows:

```
Created handlers.py in /absolute/path

Run your first workflow:
  antkeeper run healthcheck

Start the API server:
  antkeeper server

Environment variables:
  ANTKEEPER_HANDLERS_FILE  Path to handlers file (default: handlers.py)
  SLACK_BOT_TOKEN          Slack bot OAuth token (for Slack channel)
  SLACK_BOT_USER_ID        Slack bot user ID (for Slack channel)
  SLACK_COOLDOWN_SECONDS   Slack debounce cooldown in seconds (default: 30)
```

If `handlers.py` already exists at the target path, prints an error to stderr and exits 1.

## Relevant Files

- `src/antkeeper/cli.py` — CLI entry point. Add `init` subparser and init logic here, following the existing `run`/`server` pattern.
- `tests/test_cli.py` — CLI tests. Add arg parsing and integration tests for `init` here, following existing `TestArgParsing`/`TestCliIntegration` patterns.
- `handlers.py` — Reference for the healthcheck handler pattern and worktree isolation example (`sdlc_iso`). Used as inspiration for the generated template content.

## Workflow

### Step 1: Add HANDLERS_TEMPLATE constant to cli.py

- Define a module-level string constant `HANDLERS_TEMPLATE` in `src/antkeeper/cli.py` containing the generated `handlers.py` content.
- Template content must include:
  - Module docstring explaining the file's purpose
  - Imports: `datetime` from stdlib, `App` and `run_workflow` from `antkeeper.core.app`, `Runner` from `antkeeper.core.runner`, `State` from `antkeeper.core.domain`, `Worktree` and `git_worktree` from `antkeeper.git.worktrees`
  - `app = App()` instance creation
  - A working `healthcheck` handler that uses `runner.report_progress()` and `runner.logger.info()`, returning `{**state, "status": "ok"}` — no LLM dependency
  - A commented-out workflow composition example showing two steps chained with `run_workflow`
  - A commented-out worktree isolation example based on the `sdlc_iso` pattern in `handlers.py` (using `Worktree`, `git_worktree` context manager, `run_workflow` inside the worktree)
- Import paths must match those used in `handlers.py` (e.g. `from antkeeper.core.app import App, run_workflow`)

### Step 2: Add init subcommand to CLI parser and dispatch

- Add a new subparser `init` to the existing `subparsers` in `main()`:
  ```python
  init_parser = subparsers.add_parser("init")
  init_parser.add_argument("path", nargs="?", default=".")
  ```
- Add an `elif args.command == "init":` branch in `main()` that:
  1. Resolves `args.path` to an absolute path using `os.path.realpath()`
  2. Constructs the target file path: `os.path.join(path, "handlers.py")`
  3. Checks if handlers.py already exists at that path; if so, prints `Error: handlers.py already exists in {path}` to stderr and calls `sys.exit(1)`
  4. Opens and writes `HANDLERS_TEMPLATE` to the target file
  5. Prints the confirmation message and environment variable info to stdout (as shown in External Interface Change above)
- Error handling: catch `FileNotFoundError` (directory doesn't exist) and `PermissionError` (no write access) — print a user-friendly message to stderr and `sys.exit(1)` for each. These are boundary errors that benefit from clear messages rather than stack traces.

### Step 3: Add tests

- Add `TestInitArgParsing` class to `tests/test_cli.py`:
  - `_build_parser()` helper that builds a parser with the `init` subparser (same pattern as existing `TestArgParsing._build_parser()`)
  - `test_parse_init_defaults_path_to_dot` — parse `["init"]`, assert `args.path == "."` and `args.command == "init"`
  - `test_parse_init_with_explicit_path` — parse `["init", "my_project"]`, assert `args.path == "my_project"`

- Add `TestInitIntegration` class to `tests/test_cli.py`:
  - `test_init_creates_handlers_file` — use `tempfile.mkdtemp()` as target, monkeypatch `sys.argv` to `["antkeeper", "init", tmpdir]`, call `main()`, assert `handlers.py` exists in the directory and contains `app = App()` and `def healthcheck`
  - `test_init_prints_env_info` — same setup, use `capsys` to verify stdout contains `ANTKEEPER_HANDLERS_FILE` and `Created handlers.py`
  - `test_init_errors_if_handlers_exists` — pre-create `handlers.py` in tmpdir, call `main()`, assert `SystemExit` with code 1 and stderr contains `already exists`
  - `test_init_default_path_uses_cwd` — use `monkeypatch.chdir()` to a tmpdir, monkeypatch `sys.argv` to `["antkeeper", "init"]` (no path), call `main()`, assert `handlers.py` created in the tmpdir
  - `test_init_errors_if_directory_missing` — target a non-existent directory, assert `SystemExit` with code 1

  All tests use `try/finally` for cleanup, consistent with existing integration tests. Use `tempfile.mkdtemp()` not `tmp_path`.

### Step 4: Run validation commands

- Run all validation commands listed below and fix any failures.

## Testing Strategy

### Unit Tests

- `TestInitArgParsing`: Verify the `init` subparser parses the optional `path` positional argument correctly with default `"."` and with explicit values. Pure arg-parsing tests, no I/O.

### Integration

- `TestInitIntegration`: End-to-end tests that invoke `main()` with monkeypatched `sys.argv`, verify file creation on disk, verify stdout content with `capsys`, and verify error behavior when file exists or directory is missing.

### Edge Cases

- `handlers.py` already exists at target — must error, not overwrite
- No path argument — must default to current working directory
- Target directory does not exist — must error with clear message
- Generated file content is syntactically valid Python with correct imports

## Acceptance Criteria

- `antkeeper init` creates `handlers.py` in the current directory with a working healthcheck handler
- `antkeeper init my_dir` creates `handlers.py` in `my_dir`
- Generated `handlers.py` contains `app = App()`, a `healthcheck` handler, commented workflow example, and commented worktree isolation example
- Running `antkeeper init` prints environment variable information to stdout
- Running `antkeeper init` when `handlers.py` already exists prints an error to stderr and exits 1
- All existing tests continue to pass
- New tests cover arg parsing, file creation, stdout output, file-exists error, default path, and missing directory

### Validation Commands

```bash
uv run -m pytest tests/ -v
uv run ruff check src/ tests/
uv run pyright src/
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- The generated healthcheck handler deliberately avoids LLM dependencies (`ClaudeCodeAgent`) so that `antkeeper init && antkeeper run healthcheck` works without any additional setup.
- The template imports (`antkeeper.core.app`, `antkeeper.core.runner`, etc.) use the same direct import paths as the project's own `handlers.py` rather than the convenience re-exports from `antkeeper.__init__`.
- The `datetime`, `Worktree`, and `git_worktree` imports are included in the template because the commented-out worktree example references them. This avoids confusing new users with imports that don't resolve.

## Report

- **Spec file**: `specs/feature-add-init-subcommand.md`
- **Files changed**: `src/antkeeper/cli.py` (add subparser, template constant, init logic), `tests/test_cli.py` (add 2 test classes with 7 tests total)
- **Tests added**: 2 arg-parsing tests, 5 integration tests
- **Validations**: pytest, ruff, pyright
