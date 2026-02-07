"""FastAPI server for Anthill workflows.

Orchestrates route registration for webhook and Slack event endpoints.
"""
import os
import sys

import dotenv
from fastapi import FastAPI

from anthill.cli import load_app
from anthill.core.domain import WorkflowFailedError
from anthill.core.runner import Runner
from anthill.http.webhook import setup_webhook_routes
from anthill.http.slack_events import setup_slack_routes


def _run_workflow(runner: Runner) -> None:
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


def create_app(agents_file: str = os.environ.get("ANTHILL_AGENTS_FILE", "handlers.py")) -> FastAPI:
    """Create and configure a FastAPI application for Anthill workflows.

    Loads an Anthill app from the specified Python file and creates a FastAPI
    server with /webhook and /slack_event endpoints.

    Args:
        agents_file: Path to Python file containing the Anthill app.
            Defaults to ANTHILL_AGENTS_FILE env var or "handlers.py".

    Returns:
        Configured FastAPI application instance.
    """
    dotenv.load_dotenv()
    anthill_app = load_app(agents_file)
    api = FastAPI()
    setup_webhook_routes(api, anthill_app)
    setup_slack_routes(api, anthill_app)
    return api


app = create_app()
