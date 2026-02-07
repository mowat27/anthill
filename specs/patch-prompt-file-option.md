# patch: Add --prompt-file option to CLI run command

- Add `--prompt-file` flag to `antkeeper run`, mutually exclusive with `--prompt`
- Load file contents and inject into state as `prompt`, identical to `--prompt`
- Fail with clear error if file not found or both flags provided

## Solution Design

### External Interface Change

The CLI `run` command gains a new `--prompt-file <path>` option. It is mutually exclusive with `--prompt`. When provided, the file at `<path>` is read and its contents are used as `state["prompt"]`.

```bash
# Existing (unchanged)
antkeeper run --prompt "describe this project" --model sonnet specify

# New
antkeeper run --prompt-file prompts/describe.md --model sonnet specify
```

Both channels (CLI and any future channels) are unaffected — the file is resolved in `cli.py` before the state reaches `CliChannel`.

## Relevant Files

- `src/antkeeper/cli.py` — CLI entry point where `--prompt` is currently parsed and injected into state. Add `--prompt-file` here with mutual exclusion and file loading.
- `tests/test_cli.py` — CLI tests. Add argument parsing tests and integration tests for `--prompt-file`.

## Workflow

### Step 1: Add mutually exclusive group and file loading to CLI

- In `src/antkeeper/cli.py`, replace the standalone `--prompt` argument with an `argparse` mutually exclusive group containing `--prompt` and `--prompt-file`.
- After argument parsing, in the `run` command block, add logic: if `args.prompt_file` is not `None`, read the file with `pathlib.Path(args.prompt_file).read_text()` and assign the contents to `state["prompt"]`. Let `FileNotFoundError` and other OS errors propagate naturally (consistent with how `load_app` handles missing files — print to stderr, exit 1).
- The existing `if args.prompt is not None: state["prompt"] = args.prompt` line remains unchanged; only one of the two can be set due to the mutually exclusive group.

### Step 2: Update argument parsing tests

- In `tests/test_cli.py`, update `TestArgParsing._build_parser()` to mirror the new mutually exclusive group so parsing tests remain valid.
- Add a test that `--prompt-file` is parsed correctly.
- Add a test that providing both `--prompt` and `--prompt-file` causes argparse to exit (mutual exclusion).

### Step 3: Add integration test for --prompt-file

- In `TestCliIntegration`, add a test that writes a prompt to a temp file, invokes `main()` with `--prompt-file <temp_file>`, and asserts the prompt content appears in the handler's state.
- Add a test that `--prompt-file` with a nonexistent path prints an error to stderr and exits 1.

### Step 4: Validate

- Run validation commands below.

## Testing Strategy

### Unit Tests

- `TestArgParsing.test_parse_run_with_prompt_file_flag` — parse `["run", "--prompt-file", "foo.txt", "my_handler"]` and assert `args.prompt_file == "foo.txt"`.
- `TestArgParsing.test_prompt_and_prompt_file_mutually_exclusive` — parse `["run", "--prompt", "x", "--prompt-file", "y", "my_handler"]` and assert `SystemExit`.

### Integration

- `TestCliIntegration.test_prompt_file_loaded_into_state` — write a temp file with known content, invoke `main()` with `--prompt-file`, assert content appears in output state.
- `TestCliIntegration.test_prompt_file_not_found_exits` — invoke `main()` with `--prompt-file /nonexistent/path`, assert exit code 1 and error on stderr.

### Edge Cases

- Mutual exclusion enforced by argparse (both flags provided).
- File not found produces a clear error and exit 1.
- Empty file is valid — loads empty string as prompt (no special handling needed).

## Acceptance Criteria

- `antkeeper run --prompt-file <path> <workflow>` reads the file and injects contents as `state["prompt"]`
- `antkeeper run --prompt "x" --prompt-file "y" <workflow>` is rejected by argparse
- Missing file prints error to stderr and exits 1
- All existing tests continue to pass
- New tests cover parsing, mutual exclusion, file loading, and file-not-found

### Validation Commands

```bash
uv run -m pytest tests/ -v
just ruff
just ty
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- `argparse` mutually exclusive groups handle the `--prompt` / `--prompt-file` conflict automatically with a clear error message — no custom validation needed.
- Use `pathlib.Path.read_text()` for file reading — it's stdlib, concise, and raises `FileNotFoundError` naturally.
- The file-not-found handling follows the same pattern as the existing `load_app` error handling (print to stderr, exit 1).

## Report

Report: files changed, tests added, validation results. Include the prompt-file path used in integration tests to confirm end-to-end behavior. Max 200 words.
