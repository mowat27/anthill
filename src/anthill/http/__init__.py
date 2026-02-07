"""HTTP package for Anthill server.

Provides shared utilities for HTTP route handlers.
"""
import sys

from anthill.core.domain import WorkflowFailedError
from anthill.core.runner import Runner


def run_workflow_background(runner: Runner) -> None:
    """Execute a workflow in the background, handling errors gracefully.

    This function is designed to run as a background task. It catches
    WorkflowFailedError silently (as it's expected) and logs unexpected
    errors to stderr.

    Args:
        runner: The Runner instance to execute.
    """
    try:
        runner.run()
    except WorkflowFailedError:
        pass
    except Exception as e:
        print(f"Unexpected error in workflow: {e}", file=sys.stderr)
