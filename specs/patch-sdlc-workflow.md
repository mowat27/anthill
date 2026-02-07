# patch: Compose SDLC workflow in handlers

- Chain `specify -> branch -> implement -> document` as a single composite workflow via `run_workflow`.
- Extract structured data (spec path, slug, branch) from LLM responses using JSON-extracting prompts; store in state instead of raw responses.
- Log LLM prompts and responses via `runner.logger`; add `extract_json` helper in new `src/anthill/helpers/` package to strip markdown fencing from JSON in LLM output.

## Solution Design

### Architectural Schema Changes

```yaml
types:
  # No framework types change. All changes are in handlers.py (application layer).
  # State keys used by the SDLC workflow:
  SDLCStateKeys:
    kind: convention
    fields:
      - prompt: str          # Input: user prompt (existing)
      - model: str | None    # Input: optional model (existing)
      - spec_file: str       # Output from specify step
      - slug: str            # Output from specify step
      - branch_name: str     # Output from branch step
```

## Relevant Files

- `handlers.py` — Contains all current handlers (`specify`, `branch`, `implement`, `document`) and the `_run_command` helper.
- `src/anthill/core/app.py` — Provides `run_workflow` used to compose the SDLC pipeline. Read-only reference.
- `src/anthill/core/runner.py` — Provides `runner.logger` for logging. Read-only reference.
- `src/anthill/llm/claude_code.py` — `ClaudeCodeAgent` used by handlers. Read-only reference.
- `tests/core/test_workflows.py` — Existing workflow tests. Read-only reference for test patterns.
- `app_docs/testing_policy.md` — Testing policy docs. Needs update to reference `tests/helpers/`.

### New Files

- `src/anthill/helpers/__init__.py` — Package init, exports `extract_json`.
- `src/anthill/helpers/json.py` — Contains `extract_json(text: str) -> dict` helper.
- `tests/helpers/__init__.py` — Test package init.
- `tests/helpers/test_extract_json.py` — Unit tests for `extract_json`.

## Workflow

### Step 1: Add `extract_json` helper in `src/anthill/helpers/`

- Create `src/anthill/helpers/__init__.py` that exports `extract_json` from the `json` module.
- Create `src/anthill/helpers/json.py` with a function `extract_json(text: str) -> dict` that:
  - Finds the first `{` and last `}` in the text
  - Returns the substring between them (inclusive)
  - Parses it with `json.loads()`
  - Raises `ValueError` with a clear message if no braces found or JSON is invalid — no recovery attempts
- This handles LLM responses wrapped in markdown code fences or surrounded by prose

### Step 2: Refactor individual handlers to use structured prompts and logging

- **`specify` handler**: Instead of `/{name} {prompt}`, send a prompt that instructs the LLM to run `/specify {prompt}` and then extract the spec file path and slug as JSON. Specifically, the prompt should ask the LLM to return a JSON object like `{"spec_file": "...", "slug": "..."}`. Log the full LLM prompt and response via `runner.logger`. Parse the response with `extract_json()`. Return state with `spec_file` and `slug` keys (not `result`).
- **`branch` handler**: Send a prompt instructing the LLM to run `/branch {spec_file}` and return `{"branch_name": "..."}`. Log via `runner.logger`. Parse with `extract_json()`. Return state with `branch_name` key.
- **`implement` handler**: Send a prompt instructing the LLM to run `/implement {spec_file}`. Log via `runner.logger`. No JSON extraction needed — this is a side-effect step. Return state unchanged (or with a simple completion marker).
- **`document` handler**: Send a prompt instructing the LLM to document the changes on the current branch. Log via `runner.logger`. No JSON extraction needed. Return state unchanged (or with a simple completion marker).
- Remove the generic `_run_command` helper since each handler now has distinct prompt construction and response parsing logic.

### Step 3: Add `sdlc` composite handler

- Add an `sdlc` handler decorated with `@app.handler` that calls `run_workflow(runner, state, [specify, branch, implement, document])`.
- This composes the full lifecycle: the output state of each step feeds into the next.

### Step 4: Write tests for `extract_json`

- Add `tests/helpers/__init__.py` and `tests/helpers/test_extract_json.py` with tests for:
  - Clean JSON input (no fencing)
  - JSON wrapped in markdown code fences
  - JSON with surrounding prose text
  - Invalid input with no braces — asserts `ValueError`
  - Invalid JSON between braces — asserts `ValueError`

### Step 5: Update testing policy docs

- Add `tests/helpers/` to the test organization tree in `app_docs/testing_policy.md` to reflect the new `helpers` package:
  ```
  tests/
  ├── core/              # Tests for src/anthill/core/
  ├── channels/          # Tests for src/anthill/channels/
  ├── helpers/           # Tests for src/anthill/helpers/
  ├── llm/               # Tests for src/anthill/llm/
  └── test_cli.py        # Tests for src/anthill/cli.py
  ```

### Step 6: Run validation commands

- Run all validation commands and fix any issues.

## Testing Strategy

### Unit Tests

- **`extract_json` — clean JSON**: Pass `'{"spec_file": "specs/foo.md", "slug": "foo"}'`, assert returns the expected dict.
- **`extract_json` — markdown fenced**: Pass text with `` ```json\n{...}\n``` `` wrapping, assert returns the expected dict.
- **`extract_json` — prose surrounding**: Pass text like `"Here is the result:\n{...}\nDone."`, assert returns the expected dict.
- **`extract_json` — no braces**: Pass `"no json here"`, assert raises `ValueError`.
- **`extract_json` — invalid JSON**: Pass `"some text { not: valid json } more text"`, assert raises `ValueError`.

### Edge Cases

- LLM returns JSON with nested objects (braces within braces) — `extract_json` finds outermost pair, which is correct.
- LLM returns multiple JSON blocks — `extract_json` takes from first `{` to last `}`, which captures the outermost object. This is the intended behavior.
- Empty string input — raises `ValueError` (no braces found).

## Acceptance Criteria

- `handlers.py` contains refactored `specify`, `branch`, `implement`, `document` handlers, and a new `sdlc` composite handler.
- `specify` handler stores `spec_file` and `slug` in state (not `result`).
- `branch` handler stores `branch_name` in state (not `result`).
- `implement` and `document` handlers do not store raw LLM responses in state.
- All handlers log prompts and responses via `runner.logger`.
- `extract_json` in `src/anthill/helpers/json.py` strips markdown fencing and surrounding text, parses JSON, and raises `ValueError` on failure.
- `tests/helpers/test_extract_json.py` passes with tests for `extract_json`.
- `app_docs/testing_policy.md` updated with `tests/helpers/` in the test organization tree.

### Validation Commands

```bash
uv run -m pytest tests/ -v
just ruff
just ty
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- The `sdlc` handler is the entry point for the full lifecycle. Individual handlers remain registered and usable standalone.
- The JSON extraction prompt pattern wraps the real slash command inside a meta-prompt. Example for specify: `Run "/specify patch sdlc-workflow ..." and extract the spec file path and slug. Return ONLY a JSON object: {"spec_file": "<path>", "slug": "<slug>"}`.
- `implement` and `document` are side-effect steps. They don't need JSON extraction — just logging. They can store a simple status string in state if desired, but must not store the full LLM response.
- The only framework change is the new `src/anthill/helpers/` package. No changes to existing framework modules (`core/`, `channels/`, `llm/`).

## Report

Files changed: `handlers.py` (refactored all handlers, added `sdlc` composite handler), `app_docs/testing_policy.md` (added `tests/helpers/` to tree). Files added: `src/anthill/helpers/__init__.py`, `src/anthill/helpers/json.py` (`extract_json` helper), `tests/helpers/__init__.py`, `tests/helpers/test_extract_json.py`. Validations: `pytest`, `ruff`, `ty`. Key design decision: `extract_json` lives in the framework as a reusable helper since it's general-purpose LLM response parsing, not handler-specific logic. Each handler constructs its own prompt with JSON extraction instructions rather than using a generic wrapper, because each step extracts different fields.
