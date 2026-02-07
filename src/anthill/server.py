"""FastAPI server for Anthill workflows.

This module provides the FastAPI application server for executing Anthill
workflows via HTTP endpoints. It orchestrates route registration for:
- /webhook: Generic webhook endpoint for triggering workflows
- /slack_event: Slack Events API endpoint for handling Slack interactions

The server loads an Anthill app from a Python file and creates a FastAPI
instance with configured routes. Workflows run as background tasks to
ensure non-blocking HTTP responses.

Environment Variables:
    ANTHILL_AGENTS_FILE: Path to Python file containing the app
        (default: handlers.py)

Example:
    Start the server via CLI:
        anthill server --host 0.0.0.0 --port 8000 --agents-file handlers.py

    Or run directly with uvicorn:
        uvicorn anthill.server:app --host 0.0.0.0 --port 8000
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
"""FastAPI application instance configured with Anthill workflow routes.

This is the ASGI application instance that should be passed to uvicorn or
other ASGI servers. It is created by calling create_app() with default
parameters (reading from ANTHILL_AGENTS_FILE environment variable or
using "handlers.py" as the default agents file).
"""
