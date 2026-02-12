# patch: Replace --prompt/--prompt-file with positional files and stdin

- BREAKING CHANGE: Remove `--prompt` and `--prompt-file` flags from CLI `run` command
- Positional args after `workflow_name` are file paths read and concatenated into `state["prompt"]`
- If no files provided and stdin is piped, read stdin as prompt

**BREAKING CHANGE**: Ignore backwards compatibility. Remove the old flags entirely with no deprecation path.

## Solution Design

### External Interface Change

The CLI `run` command changes from flag-based prompt injection to positional files + stdin:

```bash
# Before (REMOVED)
antkeeper run --prompt "describe this project" --model sonnet specify
antkeeper run --prompt-file prompts/describe.md --model sonnet specify

# After — file args
antkeeper run --model sonnet specify prompts/describe.md
antkeeper run --model sonnet specify file1.md file2.md file3.md

# After — stdin
echo "describe this project" | antkeeper run --model sonnet specify

# After — no prompt (unchanged)
antkeeper run healthcheck
```

Multiple files are read in order and concatenated (no separator — files naturally end with newlines).

Stdin is only read when no files are provided AND stdin is not a TTY (`not sys.stdin.isatty()`). This prevents blocking on interactive terminals when no prompt is needed.

## Relevant Files

- `src/antkeeper/cli.py` — CLI entry point. Remove `--prompt`/`--prompt-file` argparse setup, add `prompt_files` positional `nargs="*"`, replace prompt-loading logic with file reading + stdin fallback.
- `tests/test_cli.py` — CLI tests. Delete flag-specific tests, update `_build_parser()`, rewrite integration tests to use positional files and stdin.
- `justfile` — `sdlc` and `sdlc_iso` recipes use `--prompt-file` and `--prompt`. Update to new positional syntax.
- `README.md` — Documents `--prompt` and `--prompt-file` flags in multiple places. Update CLI examples, command reference, and codebase navigation section.

## Workflow

### Step 1: Update argparse in cli.py

- Remove the `prompt_group` mutually exclusive group and its `--prompt` / `--prompt-file` arguments
- Add `run_parser.add_argument("prompt_files", nargs="*")` after the `workflow_name` positional arg
- Remove the `--prompt` and `--prompt-file` references from the `main()` docstring and update with new usage examples

### Step 2: Update prompt-loading logic in cli.py

Replace the existing prompt/prompt-file handling block:

```python
if args.prompt is not None:
    state["prompt"] = args.prompt
if args.prompt_file is not None:
    try:
        state["prompt"] = Path(args.prompt_file).read_text()
    except FileNotFoundError:
        ...
```

With:

```python
if args.prompt_files:
    parts = []
    for path in args.prompt_files:
        try:
            parts.append(Path(path).read_text())
        except FileNotFoundError:
            logger.error(f"File not found: {path}")
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
    state["prompt"] = "".join(parts)
elif not sys.stdin.isatty():
    state["prompt"] = sys.stdin.read()
```

### Step 3: Update tests in test_cli.py

**Delete these tests** (flags no longer exist):
- `test_parse_run_with_prompt_flag`
- `test_parse_run_with_prompt_file_flag`
- `test_prompt_and_prompt_file_mutually_exclusive`

**Update `_build_parser()`** in `TestArgParsing`:
- Remove the `prompt_group` mutually exclusive group and its arguments
- Add `run_p.add_argument("prompt_files", nargs="*")`

**Add `test_parse_run_with_prompt_files`** in `TestArgParsing`:
- Parse `["run", "my_handler", "file1.md", "file2.md"]`
- Assert `args.prompt_files == ["file1.md", "file2.md"]`

**Rewrite `test_prompt_file_loaded_into_state`**:
- Write prompt content to a temp file
- Invoke `main()` with `["antkeeper", "run", "--agents-file", agents_path, "echo", prompt_path]`
- Assert prompt content appears in output

**Rewrite `test_prompt_file_not_found_exits`**:
- Invoke `main()` with `["antkeeper", "run", "--agents-file", agents_path, "echo", "/nonexistent/path.md"]`
- Assert exit code 1 and "file not found" in stderr

**Rewrite `test_prompt_and_model_merged_into_state`**:
- Write prompt to a temp file
- Invoke `main()` with `["antkeeper", "run", "--agents-file", agents_path, "--model", "opus", "echo", prompt_path]`
- Assert both prompt content and model appear in output

**Add `test_multiple_files_concatenated`** in `TestCliIntegration`:
- Write two temp files with distinct content (e.g. `"hello\n"` and `"world\n"`)
- Invoke `main()` with both file paths as positional args after the handler name
- Assert concatenated content (`"hello\nworld\n"`) appears in state

**Add `test_stdin_read_as_prompt`** in `TestCliIntegration`:
- Use `monkeypatch.setattr("sys.stdin", io.StringIO("from stdin"))` to mock stdin
- Also `monkeypatch.setattr("sys.stdin.isatty", lambda: False)` to ensure not-a-TTY detection
- Invoke `main()` with no prompt files
- Assert `"from stdin"` appears in output

### Step 4: Update justfile

Replace the `sdlc` and `sdlc_iso` recipes:

```justfile
sdlc prompt model="opus":
  #!/usr/bin/env bash
  if [ -f "{{prompt}}" ]; then
    uv run antkeeper run --model {{model}} sdlc "{{prompt}}"
  else
    echo "{{prompt}}" | uv run antkeeper run --model {{model}} sdlc
  fi

sdlc_iso prompt model="opus":
  #!/usr/bin/env bash
  if [ -f "{{prompt}}" ]; then
    uv run antkeeper run --model {{model}} sdlc_iso "{{prompt}}"
  else
    echo "{{prompt}}" | uv run antkeeper run --model {{model}} sdlc_iso
  fi
```

### Step 5: Update README.md

- Update the Quickstart examples to use positional files and stdin piping instead of `--prompt`/`--prompt-file`
- Update the "CLI Commands" → "antkeeper run" section: remove `--prompt` and `--prompt-file` bullet points, add description of positional file args and stdin behavior
- Update the "Navigating the Codebase" → CLI paragraph to remove mention of `--prompt` and `--prompt-file`

### Step 6: Run validation commands

Run all checks described in Validation Commands below.

## Testing Strategy

### Unit Tests

**`test_parse_run_with_prompt_files`** — Verify positional file args are captured in `args.prompt_files`.

### Integration

**`test_prompt_file_loaded_into_state`** (rewritten) — Single file positional arg flows through to `state["prompt"]`.

**`test_prompt_file_not_found_exits`** (rewritten) — Nonexistent file path prints error and exits 1.

**`test_prompt_and_model_merged_into_state`** (rewritten) — Positional file + `--model` flag both appear in state.

**`test_multiple_files_concatenated`** — Two files concatenated in order into `state["prompt"]`.

**`test_stdin_read_as_prompt`** — Piped stdin content becomes `state["prompt"]` when no files provided.

### Edge Cases

- No files and stdin is a TTY → prompt not set in state (covered by existing `test_cli_loads_agents_file_and_runs` which has no prompt)
- Empty file → empty string contributes to prompt (allowed, no special handling)

## Acceptance Criteria

- `--prompt` and `--prompt-file` flags are completely removed from argparse and main()
- `antkeeper run handler file1.md file2.md` reads both files and concatenates into `state["prompt"]`
- `echo "text" | antkeeper run handler` reads stdin into `state["prompt"]`
- `antkeeper run handler` with interactive TTY and no files does not set prompt and does not block
- Nonexistent file path prints error to stderr and exits 1
- `--model` and `--initial-state` continue to work unchanged
- All tests pass, linter clean, type checker clean
- `justfile` recipes work with both file paths and string prompts

### Validation Commands

```bash
uv run pytest tests/ -v
uv run ruff check src/ tests/
uv run ty check src/
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- The `sys.stdin.isatty()` check is the standard Unix idiom for detecting piped input. When stdin is a TTY (interactive terminal), we skip reading to avoid blocking. This means `antkeeper run healthcheck` continues to work without requiring a prompt.
- File concatenation uses `"".join(parts)` with no explicit separator. Text files conventionally end with a newline, so files will naturally be separated. This avoids injecting artificial separators.
- The `io` module import is only needed in tests (for `io.StringIO` stdin mock). No new imports needed in `cli.py` — `sys` and `Path` are already imported.

## Report

Report: files changed, tests added/removed/rewritten, validation results. Confirm that both `just sdlc "some prompt" opus` and `just sdlc path/to/file.md opus` still work with the new syntax.
