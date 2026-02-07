# chore: Prepare antkeeper for PyPI release

- Move dev tools out of production dependencies and split optional features into extras
- Add package metadata, LICENSE file, public API exports, and `__main__.py`
- Rename `ANTKEEPER_AGENTS_FILE` env var to `ANTKEEPER_HANDLERS_FILE`

## Solution Design

### Architectural Schema Changes

```yaml
files:
  pyproject.toml:
    changes:
      - description: "Add required metadata fields"
      - dependencies: ["python-dotenv"]  # core only
      - optional_dependencies:
          server: ["fastapi", "uvicorn[standard]"]
          slack: ["httpx"]
          all: ["antkeeper[server,slack]"]
      - dependency_groups:
          dev: ["pytest", "httpx", "ruff", "ty"]
      - scripts:
          antkeeper: "antkeeper.cli:main"  # already present, no change
      - metadata:
          license: "MIT"
          authors: [{ name: "Adrian Mowat" }]
          classifiers: [...]
          urls: { Homepage, Repository }

  src/antkeeper/__init__.py:
    changes:
      - "Export public API symbols for clean user imports"

  src/antkeeper/__main__.py:
    new: true
    purpose: "Enable python -m antkeeper"

  LICENSE:
    new: true
    purpose: "MIT license file"
```

## Relevant Files

- `pyproject.toml` — dependencies, metadata, optional-dependencies, dependency-groups, scripts
- `src/antkeeper/__init__.py` — currently empty (docstring only); needs public API exports
- `src/antkeeper/cli.py` — sets `ANTKEEPER_AGENTS_FILE` env var (line 174); needs rename to `ANTKEEPER_HANDLERS_FILE`
- `src/antkeeper/server.py` — reads `ANTKEEPER_AGENTS_FILE` env var (line 15); needs rename to `ANTKEEPER_HANDLERS_FILE`
- `src/antkeeper/core/domain.py` — exports `State`, `Channel`, `WorkflowFailedError`
- `src/antkeeper/core/app.py` — exports `App`, `run_workflow`
- `src/antkeeper/core/runner.py` — exports `Runner`
- `src/antkeeper/channels/cli.py` — exports `CliChannel`
- `src/antkeeper/channels/api.py` — exports `ApiChannel`
- `src/antkeeper/channels/slack.py` — exports `SlackChannel`
- `src/antkeeper/git/__init__.py` — exports `Worktree`, `git_worktree`
- `README.md` — references `ANTKEEPER_AGENTS_FILE` env var; needs update
- `app_docs/http_server.md` — references `ANTKEEPER_AGENTS_FILE`; needs update

### New Files

- `LICENSE` — MIT license text at repo root
- `src/antkeeper/__main__.py` — enables `python -m antkeeper`

## Workflow

### Step 1: Update pyproject.toml

- Replace `description` with `"Workflow engine with handler registration, channel-based I/O, and remote execution"`
- Set `license = "MIT"`
- Set `authors = [{ name = "Adrian Mowat" }]`
- Add `classifiers` list (Alpha, Python 3.12, FastAPI)
- Add `[project.urls]` section (Homepage, Repository)
- Change `dependencies` to `["python-dotenv"]` only
- Add `[project.optional-dependencies]` with `server`, `slack`, and `all` extras
- Update `[dependency-groups]` dev to include `["pytest", "httpx", "ruff", "ty"]`

### Step 2: Create LICENSE file

- Create `LICENSE` at repo root with MIT license text, copyright holder "Adrian Mowat"

### Step 3: Export public API from `src/antkeeper/__init__.py`

- Import and re-export: `App`, `Runner`, `run_workflow`, `State`, `Channel`, `WorkflowFailedError`, `CliChannel`, `ApiChannel`, `SlackChannel`, `Worktree`, `git_worktree`
- Use lazy imports for optional dependencies (`ApiChannel` depends on `fastapi` via server, `SlackChannel` depends on `httpx`) — but since these are just class imports (no module-level side effects that fail), standard imports are fine. The imports will only fail at runtime if the user actually uses those classes without the extras installed, which is acceptable.
- Set `__all__` to list all exported symbols

### Step 4: Create `src/antkeeper/__main__.py`

- Content: `from antkeeper.cli import main` then `main()`
- Enables `python -m antkeeper run <workflow>` and `python -m antkeeper server`

### Step 5: Rename env var to `ANTKEEPER_HANDLERS_FILE`

- In `src/antkeeper/cli.py` line 174: change `"ANTKEEPER_AGENTS_FILE"` to `"ANTKEEPER_HANDLERS_FILE"`
- In `src/antkeeper/server.py` line 15: change `"ANTKEEPER_AGENTS_FILE"` to `"ANTKEEPER_HANDLERS_FILE"` in the `os.environ.get()` call
- In `README.md`: update the env var reference from `ANTKEEPER_AGENTS_FILE` to `ANTKEEPER_HANDLERS_FILE`
- In `app_docs/http_server.md`: update any references

### Step 6: Run validation commands

- Run `uv sync` to verify dependency resolution
- Run `just` (lint + typecheck + test) to verify zero errors

## Testing Strategy

### Unit Tests

No new unit tests required. This is a packaging/metadata chore. The existing test suite validates that all framework functionality works. The env var rename is covered by running the existing test suite (tests already exercise the CLI and server paths).

### Integration

- Verify `uv sync` resolves dependencies correctly
- Verify `just` (ruff + ty + pytest) passes with zero errors

### Edge Cases

- Ensure `from antkeeper import App, Runner, CliChannel` works after `__init__.py` changes
- Ensure `python -m antkeeper` invokes the CLI correctly

## Acceptance Criteria

- `pip install antkeeper` (or `uv pip install .`) installs only `python-dotenv` as a dependency
- `pip install antkeeper[server]` additionally installs `fastapi` and `uvicorn`
- `pip install antkeeper[slack]` additionally installs `httpx`
- `pip install antkeeper[all]` installs everything
- `from antkeeper import App, Runner, run_workflow, CliChannel, State` works
- `python -m antkeeper` prints CLI help
- `LICENSE` file exists at repo root
- No references to `ANTKEEPER_AGENTS_FILE` remain in source code (only `ANTKEEPER_HANDLERS_FILE`)
- `uv sync` succeeds
- `just` (lint + typecheck + test) passes with zero errors and zero warnings

### Validation Commands

```bash
uv sync
just
python -c "from antkeeper import App, Runner, run_workflow, CliChannel, State, Channel, WorkflowFailedError, ApiChannel, SlackChannel, Worktree, git_worktree; print('All imports OK')"
uv run python -m antkeeper
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- The env var rename from `ANTKEEPER_AGENTS_FILE` to `ANTKEEPER_HANDLERS_FILE` is a **breaking change** for anyone using the env var. Since the package has not been released yet (pre-0.1.0), this is acceptable.
- `ruff` and `ty` are dev tools only — they must not be in production `dependencies`. They are currently listed there and must be moved.
- `httpx` appears in both `[dependency-groups] dev` (for test HTTP mocking via `TestClient`) and `[project.optional-dependencies] slack` (for `SlackChannel`). This is correct — dev needs it for tests regardless of extras.
- The `__init__.py` exports include `ApiChannel` and `SlackChannel` even though they depend on optional extras. This follows standard Python practice — the import will succeed (they're just class definitions), but using them without the extras installed will fail at runtime when they try to import `fastapi` or `httpx`. This is the expected behavior.

## Report

Report after implementation:

- Files changed: `pyproject.toml`, `src/antkeeper/__init__.py`, `src/antkeeper/cli.py`, `src/antkeeper/server.py`, `README.md`, `app_docs/http_server.md`
- Files created: `LICENSE`, `src/antkeeper/__main__.py`
- Tests added: none (existing suite validates functionality)
- Validations: `uv sync`, `just` (ruff + ty + pytest), import smoke test, `python -m antkeeper` invocation
