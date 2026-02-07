"""LLM-backed workflow handlers for the Anthill framework.

Each handler runs a slash command via ClaudeCodeAgent with the user prompt.
"""

from anthill.core.runner import Runner
from anthill.core.domain import State
from anthill.core.app import App
from anthill.llm.claude_code import ClaudeCodeAgent

app = App()


def _run_command(name: str, runner: Runner, state: State) -> State:
    """Run a Claude Code slash command via ClaudeCodeAgent.

    Args:
        name: The slash command name (e.g., 'specify', 'branch').
        runner: The Runner instance managing the workflow.
        state: Current workflow state containing 'prompt' and optional 'model'.

    Returns:
        Updated state dictionary with 'result' key containing agent response.
    """
    runner.report_progress(f"Running /{name}")
    agent = ClaudeCodeAgent(model=state.get("model"))
    response = agent.prompt(f"/{name} {state['prompt']}")
    runner.report_progress(f"/{name} complete")
    return {**state, "result": response}


@app.handler
def specify(runner: Runner, state: State) -> State:
    """Generate a specification from a user prompt.

    Args:
        runner: The Runner instance managing the workflow.
        state: Current workflow state containing 'prompt' and optional 'model'.

    Returns:
        Updated state with specification in 'result' key.
    """
    return _run_command("specify", runner, state)


@app.handler
def branch(runner: Runner, state: State) -> State:
    """Create a feature branch from a plan file.

    Args:
        runner: The Runner instance managing the workflow.
        state: Current workflow state containing 'prompt' and optional 'model'.

    Returns:
        Updated state with branch creation result in 'result' key.
    """
    return _run_command("branch", runner, state)


@app.handler
def implement(runner: Runner, state: State) -> State:
    """Implement a feature from a spec/plan.

    Args:
        runner: The Runner instance managing the workflow.
        state: Current workflow state containing 'prompt' and optional 'model'.

    Returns:
        Updated state with implementation result in 'result' key.
    """
    return _run_command("implement", runner, state)


@app.handler
def document(runner: Runner, state: State) -> State:
    """Update documentation for completed work.

    Args:
        runner: The Runner instance managing the workflow.
        state: Current workflow state containing 'prompt' and optional 'model'.

    Returns:
        Updated state with documentation update result in 'result' key.
    """
    return _run_command("document", runner, state)
