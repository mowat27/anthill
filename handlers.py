"""LLM-backed workflow handlers for the Antkeeper framework.

Each handler runs a slash command via ClaudeCodeAgent, extracts structured
data from the response, and threads it through state for downstream steps.
"""

from datetime import datetime

from antkeeper.core.runner import Runner
from antkeeper.core.domain import State
from antkeeper.core.app import App, run_workflow
from antkeeper.git.worktrees import Worktree, git_worktree
from antkeeper.helpers.json import extract_json
from antkeeper.llm.claude_code import ClaudeCodeAgent

app = App()


# --- Steps ---


@app.handler
def healthcheck(runner: Runner, state: State) -> State:
    """Verify the agent pipeline is working by asking Claude to write a short poem."""
    runner.report_progress("Running healthcheck")
    agent = ClaudeCodeAgent(model=state.get("model"))
    response = agent.prompt("Write a short poem about agentic coding")
    runner.logger.info(f"healthcheck response: {response}")
    runner.report_progress("Healthcheck complete")
    runner.report_progress(response)
    return {**state, "poem": response}


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


@app.handler
def derive_feature(runner: Runner, state: State) -> State:
    """Derive feature type and slug from a prompt via LLM."""
    runner.report_progress("Deriving feature metadata")
    agent = ClaudeCodeAgent(model=state.get("model"))
    prompt = (
        f'/derive_feature {state["prompt"]}\n\n'
        "After running the command, return ONLY a JSON object: "
        '{"feature_type": "<type>", "slug": "<slug>"}'
    )
    runner.logger.info(f"derive_feature prompt: {prompt}")
    response = agent.prompt(prompt)
    runner.logger.info(f"derive_feature response: {response}")
    parsed = extract_json(response)
    runner.report_progress("Feature metadata derived")
    return {**state, "feature_type": parsed["feature_type"], "slug": parsed["slug"]}


# --- Shared workflow constants ---


SDLC_STEPS = [specify, branch, implement, document]


# --- Workflows ---


@app.handler
def sdlc(runner: Runner, state: State) -> State:
    """Run the full SDLC workflow: specify -> branch -> implement -> document."""
    return run_workflow(runner, state, SDLC_STEPS)


@app.handler
def specify_and_branch(runner: Runner, state: State) -> State:
    """Run partial SDLC workflow: specify -> branch."""
    return run_workflow(runner, state, SDLC_STEPS[0:2])


@app.handler
def sdlc_iso(runner: Runner, state: State) -> State:
    """Run SDLC workflow inside an isolated git worktree."""
    state = derive_feature(runner, state)
    worktree_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{runner.id}"
    branch_name = f"{state['feature_type']}/{state['slug']}"
    wt = Worktree(base_dir=runner.app.worktree_dir, name=worktree_name)
    with git_worktree(wt, create=True, branch=branch_name, remove=False):
        state = run_workflow(runner, state, [specify, implement, document])
    return {**state, "worktree_path": wt.path, "branch_name": branch_name}
