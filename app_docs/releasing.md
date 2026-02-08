# Releasing to PyPI

This document covers the packaging structure, dependency management, and release process for publishing antkeeper to PyPI.

## Package Structure

Antkeeper uses a split dependency model to minimize the installation footprint for users who don't need all features:

### Core Dependencies

The base package (`pip install antkeeper`) requires:
- `python-dotenv` - Environment variable loading
- `httpx` - HTTP client for Slack integration

Slack functionality is first-class (not optional), ensuring reliable thread-based workflow dispatch for all users.

### Optional Dependencies

Server features are installed via extras:

```bash
pip install antkeeper[server]  # Adds FastAPI + uvicorn
pip install antkeeper[all]     # Installs all extras (equivalent to [server])
```

Defined in `pyproject.toml`:

```toml
[project.optional-dependencies]
server = ["fastapi", "uvicorn[standard]"]
all = ["antkeeper[server]"]
```

### Development Dependencies

Development tools (linters, type checkers, test framework) are defined in `[dependency-groups]` and installed via `uv sync`:

```toml
[dependency-groups]
dev = ["pytest", "fastapi", "uvicorn[standard]", "ruff", "ty"]
```

`httpx` is now a core dependency, available in both production and dev environments.

## Public API

The package exports a clean public API from `src/antkeeper/__init__.py`:

```python
from antkeeper import (
    App,
    Runner,
    run_workflow,
    State,
    Channel,
    WorkflowFailedError,
    CliChannel,
    ApiChannel,
    SlackChannel,
    Worktree,
    git_worktree,
)
```

Classes that depend on optional dependencies (`ApiChannel`) are included in the public API. They import successfully (they're just class definitions), but attempting to use them without the corresponding extras installed will fail at runtime when they try to import `fastapi`. `SlackChannel` is always available since `httpx` is a core dependency.

## Entry Points

The package provides two entry points:

### CLI Script

```bash
antkeeper run --agents-file handlers.py my_workflow
```

Defined in `pyproject.toml`:

```toml
[project.scripts]
antkeeper = "antkeeper.cli:main"
```

### Python Module

```bash
python -m antkeeper run my_workflow
```

Enabled by `src/antkeeper/__main__.py`:

```python
from antkeeper.cli import main

main()
```

## Environment Variables

### ANTKEEPER_HANDLERS_FILE

The `ANTKEEPER_HANDLERS_FILE` environment variable specifies the Python file containing the `app` object (an `antkeeper.core.app.App` instance).

**Default**: `handlers.py`

**Usage**:

- **CLI**: The `--agents-file` flag sets this env var before invoking the workflow
- **Server**: The `create_app()` factory reads this env var at import time
- **uvicorn**: Set directly when starting the server: `ANTKEEPER_HANDLERS_FILE=handlers.py uvicorn antkeeper.server:app`

**Breaking Change**: This variable was previously named `ANTKEEPER_AGENTS_FILE`. All references were updated in version 0.1.0.

## Metadata

Package metadata is defined in `pyproject.toml`:

```toml
[project]
name = "antkeeper"
version = "0.1.0"
description = "Workflow engine with handler registration, channel-based I/O, and remote execution"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [{ name = "Adrian Mowat" }]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.12",
    "Framework :: FastAPI",
]

[project.urls]
Homepage = "https://github.com/mowat27/antkeeper"
Repository = "https://github.com/mowat27/antkeeper"
```

The MIT license text is provided in the `LICENSE` file at the repository root.

## Build System

Antkeeper uses `uv_build` as its build backend:

```toml
[build-system]
requires = ["uv_build>=0.7.2,<0.8"]
build-backend = "uv_build"
```

### Building the Package

```bash
uv build
```

This creates wheel and source distributions in `dist/`:
- `antkeeper-0.1.0-py3-none-any.whl`
- `antkeeper-0.1.0.tar.gz`

### Installing Locally

```bash
uv pip install .              # Core only
uv pip install ".[server]"    # With server support
uv pip install ".[all]"       # All extras
```

Or using pip:

```bash
pip install .
pip install ".[server]"
pip install ".[all]"
```

## Release Checklist

Before publishing to PyPI:

1. **Update version** in `pyproject.toml`
2. **Run quality checks**: `just` (lint + typecheck + test)
3. **Verify imports**: `python -c "from antkeeper import App, Runner, run_workflow, CliChannel, State, Channel, WorkflowFailedError, ApiChannel, SlackChannel, Worktree, git_worktree; print('All imports OK')"`
4. **Test CLI invocation**: `python -m antkeeper` (should print help), `antkeeper init` (should scaffold handlers.py)
5. **Build package**: `uv build`
6. **Test installation**: `uv pip install dist/antkeeper-*.whl` in a fresh venv
7. **Test extras**: Install with `[server]` extra, verify API server starts
8. **Commit and tag**: `git tag v0.1.0 && git push --tags`
9. **Publish to PyPI**: `uv publish` (requires PyPI credentials)

## Publishing to PyPI

```bash
uv publish --token <pypi_token>
```

Or configure credentials in `~/.pypirc` and run:

```bash
uv publish
```

For test releases, use TestPyPI:

```bash
uv publish --repository testpypi --token <testpypi_token>
```

## Post-Release Verification

After publishing, verify the package is installable from PyPI:

```bash
# Test in a fresh environment
uv venv test-env
source test-env/bin/activate
pip install antkeeper
python -c "from antkeeper import App, SlackChannel; print('Core install OK')"

pip install antkeeper[server]
python -c "from antkeeper import ApiChannel; print('Server extras OK')"

# Test init subcommand
antkeeper init test-project
test -f test-project/handlers.py && echo "Scaffolding OK"
```

## Version Numbering

Antkeeper follows semantic versioning:

- **0.x.y**: Pre-1.0 releases (API may change)
- **x.0.0**: Major version (breaking changes)
- **x.y.0**: Minor version (new features, backward compatible)
- **x.y.z**: Patch version (bug fixes, backward compatible)

Breaking changes in pre-1.0 releases (like the `ANTKEEPER_AGENTS_FILE` → `ANTKEEPER_HANDLERS_FILE` rename) are documented in release notes but don't require a major version bump until 1.0.0.
