"""LLM-backed workflow handlers for the Anthill framework.

Each handler runs a slash command via ClaudeCodeAgent, extracts structured
data from the response, and threads it through state for downstream steps.
"""

from anthill.core.runner import Runner
from anthill.core.domain import State
from anthill.core.app import App, run_workflow
from anthill.helpers.json import extract_json
from anthill.llm.claude_code import ClaudeCodeAgent

app = App()


@app.handler
def specify(runner: Runner, state: State) -> State:
    """Generate a specification and extract spec_file and slug from the response."""
    runner.report_progress("Running /specify")
    agent = ClaudeCodeAgent(model=state.get("model"))
    prompt = (
        f'/specify {state["prompt"]}\n\n'
        "After running the command, return ONLY a JSON object with the spec file path "
        'and slug: {"spec_file": "<path>", "slug": "<slug>"}'
    )
    runner.logger.info(f"specify prompt: {prompt}")
    response = agent.prompt(prompt)
    runner.logger.info(f"specify response: {response}")
    parsed = extract_json(response)
    runner.report_progress("/specify complete")
    return {**state, "spec_file": parsed["spec_file"], "slug": parsed["slug"]}


@app.handler
def branch(runner: Runner, state: State) -> State:
    """Create a feature branch and extract the branch name from the response."""
    runner.report_progress("Running /branch")
    agent = ClaudeCodeAgent(model=state.get("model"))
    prompt = (
        f'/branch {state["spec_file"]}\n\n'
        "After running the command, return ONLY a JSON object with the branch name: "
        '{"branch_name": "<branch>"}'
    )
    runner.logger.info(f"branch prompt: {prompt}")
    response = agent.prompt(prompt)
    runner.logger.info(f"branch response: {response}")
    parsed = extract_json(response)
    runner.report_progress("/branch complete")
    return {**state, "branch_name": parsed["branch_name"]}


@app.handler
def implement(runner: Runner, state: State) -> State:
    """Implement a feature from a spec/plan."""
    runner.report_progress("Running /implement")
    agent = ClaudeCodeAgent(model=state.get("model"))
    prompt = f'/implement {state["spec_file"]}'
    runner.logger.info(f"implement prompt: {prompt}")
    response = agent.prompt(prompt)
    runner.logger.info(f"implement response length: {len(response)} chars")
    runner.report_progress("/implement complete")
    return {**state, "implement_status": "complete"}


@app.handler
def document(runner: Runner, state: State) -> State:
    """Update documentation for completed work on the current branch."""
    runner.report_progress("Running /document")
    agent = ClaudeCodeAgent(model=state.get("model"))
    prompt = "/document Update documentation for the changes on this branch."
    runner.logger.info(f"document prompt: {prompt}")
    response = agent.prompt(prompt)
    runner.logger.info(f"document response length: {len(response)} chars")
    runner.report_progress("/document complete")
    return {**state, "document_status": "complete"}


SDLC_STEPS = [specify, branch, implement, document]


@app.handler
def sdlc(runner: Runner, state: State) -> State:
    """Run the full SDLC workflow: specify -> branch -> implement -> document."""
    return run_workflow(runner, state, SDLC_STEPS)


@app.handler
def specify_and_branch(runner: Runner, state: State) -> State:
    """Run the full SDLC workflow: specify -> branch -> implement -> document."""
    return run_workflow(runner, state, SDLC_STEPS[0:2])
