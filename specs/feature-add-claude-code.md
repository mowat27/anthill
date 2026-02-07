# feature: Add Claude Code LLM integration

- Add `ClaudeCodeAgent` in new `llm` package to execute prompts via `claude -p` subprocess.
- Update CLI: rename positional to `workflow_name`, add `--prompt` and `--model` optional args merged into initial state. BREAKING CHANGE.
- Add `specify`, `branch`, `implement`, `document` handlers that read `.claude/commands/*.md` and delegate to `ClaudeCodeAgent`.

## Solution Design

### External Interface Change

After this change, the CLI accepts an optional prompt and model that are merged into `initial_state`. Handlers can read `state["prompt"]` and `state.get("model")` to drive LLM interactions.

**BREAKING CHANGE**: Ignore backwards compatibility. The CLI positional arg is renamed from `prompt` to `workflow_name`. Existing demo handlers in `handlers.py` are replaced with LLM-backed handlers.

**CLI usage:**
```
antkeeper run [--agents-file=handlers.py] [--initial-state key=val ...] [--prompt PROMPT] [--model MODEL] WORKFLOW_NAME
```

Where `WORKFLOW_NAME` is the handler to execute (e.g., `specify`), `--prompt` is the user's request text, and `--model` is the LLM model name.

**Handler example (how handlers use the new state keys):**
```python
@app.handler
def specify(runner: Runner, state: State) -> State:
    agent = ClaudeCodeAgent(model=state.get("model"))
    command_text = Path(".claude/commands/specify.md").read_text()
    combined = f"{command_text}\n\n{state['prompt']}"
    result = agent.prompt(combined)
    return {**state, "result": result}
```

**Other channel examples (future, not in scope):**
```python
# A Slack channel could populate state["prompt"] from a Slack message
# A GitHub channel could populate state["prompt"] from an issue body
# Each channel owns how it builds initial_state; handlers are channel-agnostic
```

### Architectural Schema Changes

```yaml
types:
  Agent:
    kind: protocol
    location: src/antkeeper/llm/__init__.py
    methods:
      - prompt(self, prompt: str) -> str

  AgentExecutionError:
    kind: exception
    location: src/antkeeper/llm/errors.py
    parent: Exception
    note: Message-only. Subprocess details included in message string.

  ClaudeCodeAgent:
    kind: class
    location: src/antkeeper/llm/claude_code.py
    constructor:
      - model: str | None  # default None
    implements: Agent
    methods:
      - prompt(self, prompt: str) -> str  # calls claude -p via subprocess

  CliChannel:
    kind: class
    location: src/antkeeper/channels/cli.py
    note: No changes. Already accepts arbitrary initial_state dict.
```

## Relevant Files

- `src/antkeeper/cli.py` — Rename positional arg from `prompt` to `workflow_name`. Add `--prompt` and `--model` optional args. Merge into initial state before constructing CliChannel.
- `src/antkeeper/core/domain.py` — No changes. Agent protocol does not belong in core.
- `src/antkeeper/core/runner.py` — No changes.
- `src/antkeeper/channels/cli.py` — No changes. Already accepts arbitrary `initial_state`.
- `handlers.py` — Replace all demo handlers with `specify`, `branch`, `implement`, `document`.
- `.claude/commands/specify.md` — Read-only. Template for specify handler prompt.
- `.claude/commands/branch.md` — Read-only. Template for branch handler prompt.
- `.claude/commands/implement.md` — Read-only. Template for implement handler prompt.
- `.claude/commands/document.md` — Read-only. Template for document handler prompt.
- `tests/test_cli.py` — Update for new CLI arg structure.
- `tests/test_workflows.py` — Existing tests reference demo handlers; they must still pass (they define their own handlers in-test, so no changes expected).

### New Files

- `src/antkeeper/llm/__init__.py` — Package init. Defines `Agent` protocol.
- `src/antkeeper/llm/errors.py` — `AgentExecutionError` exception class.
- `src/antkeeper/llm/claude_code.py` — `ClaudeCodeAgent` class.
- `tests/test_claude_code_agent.py` — Tests for ClaudeCodeAgent.

## Workflow

### Step 1: Create `llm` package with Agent protocol

- Create `src/antkeeper/llm/__init__.py` with the `Agent` protocol:
  ```python
  class Agent(Protocol):
      def prompt(self, prompt: str) -> str: ...
  ```
- The protocol lives here (not in core) because it is an LLM-layer concept. Core knows nothing about agents or prompts.

### Step 2: Create AgentExecutionError

- Create `src/antkeeper/llm/errors.py` with a simple exception:
  ```python
  class AgentExecutionError(Exception):
      """Raised when an agent fails to execute a prompt."""
  ```
- Message-only. No `returncode` or `stderr` fields — include subprocess details in the message string. This keeps the error generic enough for any Agent implementation.

### Step 3: Create ClaudeCodeAgent

- Create `src/antkeeper/llm/claude_code.py`.
- Constructor: `__init__(self, model: str | None = None)`.
- `prompt(self, prompt: str) -> str` method:
  - Build command: `["claude", "-p", prompt]`. If `self.model`, insert `"--model", self.model`.
  - Call `subprocess.run(cmd, capture_output=True, text=True)`.
  - On non-zero returncode: raise `AgentExecutionError(f"claude exited with code {result.returncode}: {result.stderr}")`.
  - On success: return `result.stdout`.
- Catch `FileNotFoundError` from subprocess and re-raise as `AgentExecutionError("claude binary not found")`.
- No retry logic, no streaming, no timeout. Keep minimal.

### Step 4: Update CLI

- In `src/antkeeper/cli.py`, rename the positional argument from `prompt` to `workflow_name`:
  ```python
  run_parser.add_argument("workflow_name")
  ```
- Add two optional arguments:
  ```python
  run_parser.add_argument("--prompt", default=None)
  run_parser.add_argument("--model", default=None)
  ```
- After parsing `--initial-state` pairs into `state` dict, merge prompt and model if provided:
  ```python
  if args.prompt is not None:
      state["prompt"] = args.prompt
  if args.model is not None:
      state["model"] = args.model
  ```
- Update CliChannel construction:
  ```python
  channel = CliChannel(workflow_name=args.workflow_name, initial_state=state)
  ```
- This is a **BREAKING CHANGE**. No backwards compatibility shims.

### Step 5: Replace handlers in handlers.py

- Remove all existing demo handlers (`init_state`, `plus_1`, `times_2`, `simulate_failure`, `plus_1_times_2`, `plus_1_times_2_times_2`).
- Remove the `run_workflow` import (no longer needed).
- Add imports for `Path`, `ClaudeCodeAgent`.
- Add four new handlers, each following this pattern:
  1. Read the corresponding `.claude/commands/<name>.md` file using `Path`.
  2. Get prompt from `state["prompt"]` (KeyError propagates if missing — this is a handler error per design philosophy).
  3. Construct `ClaudeCodeAgent(model=state.get("model"))`.
  4. Combine command template with user prompt.
  5. Call `agent.prompt(combined)`.
  6. Return `{**state, "result": response}`.
- The four handlers: `specify`, `branch`, `implement`, `document`.
- `AgentExecutionError` propagates to the runner naturally. No try/except in handlers.

### Step 6: Write tests

- See Testing Strategy below.

### Step 7: Run validation commands

- Run all tests, type checks, and linting.
- Verify CLI help works with new arg structure.
- Verify end-to-end with a mock workflow (since `claude` binary may not be available in CI).

## Testing Strategy

### Unit Tests

**ClaudeCodeAgent tests** (`tests/test_claude_code_agent.py`):

- `test_successful_prompt_returns_stdout` — Patch `subprocess.run` to return `CompletedProcess(returncode=0, stdout="answer", stderr="")`. Create `ClaudeCodeAgent()`, call `agent.prompt("hello")`. Assert returns `"answer"`.
- `test_failed_prompt_raises_agent_execution_error` — Patch `subprocess.run` to return `CompletedProcess(returncode=1, stdout="", stderr="boom")`. Assert `agent.prompt("hello")` raises `AgentExecutionError`.
- `test_model_passed_to_subprocess` — Patch `subprocess.run`. Create `ClaudeCodeAgent(model="opus")`, call `agent.prompt("hello")`. Assert `subprocess.run` was called with args containing `"--model"` and `"opus"`.
- `test_no_model_omits_flag` — Patch `subprocess.run`. Create `ClaudeCodeAgent()`, call `agent.prompt("hello")`. Assert `"--model"` not in the args.

**CLI tests** (update `tests/test_cli.py`):

- `test_parse_run_with_workflow_name` — Verify `antkeeper run my_handler` parses `workflow_name="my_handler"`.
- `test_parse_run_with_prompt_flag` — Verify `--prompt "build a widget"` is parsed.
- `test_parse_run_with_model_flag` — Verify `--model opus` is parsed.
- `test_prompt_and_model_merged_into_state` — End-to-end: create temp agents file with handler that returns state, invoke `main()`, verify state contains `prompt` and `model` keys.

### Integration

- `test_handler_using_mock_agent_in_runner` — Define a handler that creates a fake agent (plain object with `prompt` method returning canned string), register it with an `App`, run through `Runner` with `TestChannel`. Verify final state contains the canned response. This exercises the full pipeline without subprocess.
- `test_agent_execution_error_propagates` — Define a handler that raises `AgentExecutionError`. Run through `Runner`. Assert `AgentExecutionError` propagates up.

### Edge Cases

- `ClaudeCodeAgent` when `claude` binary not on PATH — raises `AgentExecutionError` (not `FileNotFoundError`).
- Handler called without `prompt` in state — `KeyError` propagates (expected; design philosophy says handler errors propagate).
- Empty string prompt — passed through to subprocess as-is.

## Acceptance Criteria

- `antkeeper run --help` shows `workflow_name` positional, `--prompt`, `--model`, `--initial-state`, `--agents-file`.
- `antkeeper run --prompt "describe the system" --model sonnet specify` invokes the specify handler with prompt and model in state.
- `ClaudeCodeAgent` calls `subprocess.run(["claude", "-p", ...])` and returns stdout.
- `ClaudeCodeAgent` raises `AgentExecutionError` on non-zero exit or missing binary.
- `Agent` protocol defined in `src/antkeeper/llm/__init__.py` with single `prompt(str) -> str` method.
- `handlers.py` contains `specify`, `branch`, `implement`, `document` handlers.
- No changes to `src/antkeeper/core/domain.py`, `src/antkeeper/core/runner.py`, or `src/antkeeper/core/app.py`.
- All existing workflow tests pass unchanged (they define their own handlers).
- All new tests pass.

### Validation Commands

```bash
# Run all tests
uv run -m pytest tests/ -v

# Type check
uv run -m ty check

# Lint
uv run -m ruff check

# Verify CLI help shows new args
uv run antkeeper run --help
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this feature.

## Notes

- **BREAKING CHANGE**: The CLI positional arg is renamed from `prompt` to `workflow_name`. Existing invocations like `antkeeper run plus_1` still work syntactically but the demo handlers they reference are removed.
- The `Agent` protocol and `AgentExecutionError` live in the `llm` package, not in `core`. This preserves core genericity — the core knows nothing about agents, prompts, or LLMs.
- `AgentExecutionError` is a simple `Exception` subclass with message only. Subprocess details (returncode, stderr) are included in the message string, keeping the error generic for future non-subprocess Agent implementations.
- Handlers read `.claude/commands/*.md` at call time. These are application-level files, not framework resources. If missing, `FileNotFoundError` propagates naturally.
- The `--prompt` and `--model` CLI flags are convenience shortcuts. The same effect is achievable via `--initial-state prompt=... --initial-state model=...`. The flags exist for ergonomics since these are the most common state keys for LLM workflows.
- No changes to the `Channel` protocol, `Runner`, or `App`. The feature is purely additive to the outer layers.

## Report

Files changed: `src/antkeeper/cli.py` (rename positional, add --prompt/--model flags), `handlers.py` (replace demo handlers with LLM-backed handlers), `tests/test_cli.py` (update for new args). Files created: `src/antkeeper/llm/__init__.py` (Agent protocol), `src/antkeeper/llm/errors.py` (AgentExecutionError), `src/antkeeper/llm/claude_code.py` (ClaudeCodeAgent), `tests/test_claude_code_agent.py`. Tests added: 4 ClaudeCodeAgent unit tests, 4 CLI tests, 2 integration tests. Validations: pytest, ty check, ruff check, CLI help verification.
