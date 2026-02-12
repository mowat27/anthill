# feature: CLI options for ClaudeCodeAgent

- Add `yolo` bool param that passes `--dangerously-skip-permissions` to the `claude` CLI
- Add `opts` list param for arbitrary CLI args with precedence over convenience params
- Merge logic: convenience flags skipped when the same flag appears in `opts`

## Solution Design

### External Interface Change

Channels and handlers can now customise how `ClaudeCodeAgent` invokes the CLI:

```python
# Skip permissions (yolo mode)
agent = ClaudeCodeAgent(yolo=True)

# Pass arbitrary CLI args
agent = ClaudeCodeAgent(opts=["--verbose", "--max-tokens", "4096"])

# Opts override convenience params — this uses Opus, not sonnet
agent = ClaudeCodeAgent(model="sonnet", opts=["--model", "Opus"])

# Combined
agent = ClaudeCodeAgent(model="sonnet", yolo=True, opts=["--fast"])
```

### Architectural Schema Changes

```yaml
llm:
  ClaudeCodeAgent:
    implements: Agent
    constructor:
      model:
        type: "str | None"
        default: "None"
        description: "Convenience param: passed as --model flag"
      yolo:
        type: bool
        default: false
        description: "Convenience param: when true, passes --dangerously-skip-permissions"
      opts:
        type: "list[str] | None"
        default: "None"
        description: "Extra CLI args; override convenience params when flags conflict"
```

## Relevant Files

- `src/antkeeper/llm/claude_code.py` — `ClaudeCodeAgent` class. Constructor and `prompt()` method need updating.
- `tests/llm/test_claude_code_agent.py` — Unit tests for `ClaudeCodeAgent`. New test cases needed.

## Workflow

### Step 1: Update ClaudeCodeAgent constructor

- Add `yolo: bool = False` parameter after `model`
- Add `opts: list[str] | None = None` parameter after `yolo`
- Store both as instance attributes
- Update the debug log to include the new params

### Step 2: Update command building in prompt()

Replace the current command construction:

```python
cmd = ["claude", "-p", prompt]
if self.model:
    cmd[1:1] = ["--model", self.model]
```

With inline merge logic that builds the command in order — `["claude"]` + filtered convenience flags + opts + `["-p", prompt]`:

- Build `opts_list = self.opts or []`
- Add `["--model", self.model]` only if `self.model` and `"--model" not in opts_list`
- Add `"--dangerously-skip-permissions"` only if `self.yolo` and `"--dangerously-skip-permissions" not in opts_list`
- Extend with `opts_list`
- Append `["-p", prompt]`

This keeps command building inline in `prompt()` — no extracted private method needed.

### Step 3: Add unit tests

Add the following tests to `TestClaudeCodeAgent` in `tests/llm/test_claude_code_agent.py`. All tests follow the existing pattern: patch `subprocess.run`, call `agent.prompt()`, inspect `mock_run.call_args[0][0]`.

See Testing Strategy below.

### Step 4: Run validation commands

Run all checks described in Validation Commands below.

## Testing Strategy

### Unit Tests

**`test_yolo_adds_permissions_flag`**
- Setup: `ClaudeCodeAgent(yolo=True)`
- Call: `agent.prompt("hello")`
- Assert: command list contains `"--dangerously-skip-permissions"`

**`test_opts_passed_to_command`**
- Setup: `ClaudeCodeAgent(opts=["--verbose"])`
- Call: `agent.prompt("hello")`
- Assert: command list is `["claude", "--verbose", "-p", "hello"]`

**`test_opts_override_convenience_params`**
- Setup: `ClaudeCodeAgent(model="sonnet", yolo=True, opts=["--model", "opus", "--dangerously-skip-permissions"])`
- Call: `agent.prompt("hello")`
- Assert: `"sonnet"` not in command list. `"--model"` appears exactly once. `"--dangerously-skip-permissions"` appears exactly once. Final command is `["claude", "--model", "opus", "--dangerously-skip-permissions", "-p", "hello"]`

### Edge Cases

- Existing tests already cover `model=None` (no --model flag) and default constructor — these implicitly cover `yolo=False` and `opts=None` defaults, so no additional tests needed for those paths.

## Acceptance Criteria

- `ClaudeCodeAgent(yolo=True)` adds `--dangerously-skip-permissions` to the CLI command
- `ClaudeCodeAgent(opts=["--foo"])` passes `--foo` to the CLI command
- When `opts` contains a flag that matches a convenience param, the convenience version is suppressed and opts wins
- All new params have defaults so existing code is fully backwards compatible
- All existing tests continue to pass

### Validation Commands

```bash
uv run pytest tests/ -v
uv run ruff check src/ tests/
uv run ty check src/
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- The merge logic uses a simple `not in` check on the opts list. This works for the standard two-element format (`["--model", "opus"]`) used in the codebase. The `=` syntax (`["--model=opus"]`) is not explicitly handled — if a user passes `--model=opus` in opts while also setting `model="sonnet"`, both would appear in the command. This is acceptable; it can be addressed if needed later.
- No validation is performed on `opts` contents. Invalid flags will cause `claude` to exit non-zero, which is already caught and raised as `AgentExecutionError`. This follows the design philosophy of letting exceptions propagate.

## Report

Report: files changed, tests added, validation results. Include the final command structure for a combined example (model + yolo + opts) to confirm correctness.
