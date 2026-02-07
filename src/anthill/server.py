"""FastAPI server for Anthill workflow webhooks.

This module provides a FastAPI server that exposes Anthill workflows via
HTTP endpoints. Workflows are triggered asynchronously via POST requests
to /webhook and run in the background.
"""
import os
import sys
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from anthill.channels.api import ApiChannel
from anthill.cli import load_app
from anthill.core.domain import WorkflowFailedError
from anthill.core.runner import Runner


class WebhookRequest(BaseModel):
    """Request model for webhook endpoint.

    Attributes:
        workflow_name: Name of the workflow to execute.
        initial_state: Initial state dictionary for the workflow. Defaults to empty dict.
    """
    workflow_name: str
    initial_state: dict[str, Any] = {}


class WebhookResponse(BaseModel):
    """Response model for webhook endpoint.

    Attributes:
        run_id: Unique identifier for the workflow run.
    """
    run_id: str


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
    server with a /webhook endpoint for triggering workflows asynchronously.

    Args:
        agents_file: Path to Python file containing the Anthill app.
            Defaults to ANTHILL_AGENTS_FILE env var or "handlers.py".

    Returns:
        Configured FastAPI application instance.
    """
    anthill_app = load_app(agents_file)
    api = FastAPI()

    @api.post("/webhook", response_model=WebhookResponse)
    async def webhook(request: WebhookRequest, background_tasks: BackgroundTasks) -> WebhookResponse:
        """Webhook endpoint for triggering workflows asynchronously.

        Validates the workflow exists, creates a runner, and schedules the
        workflow to run in the background. Returns immediately with a run_id
        for tracking the execution.

        Args:
            request: Webhook request containing workflow_name and initial_state.
            background_tasks: FastAPI background tasks manager.

        Returns:
            WebhookResponse containing the unique run_id.

        Raises:
            HTTPException: 404 if the workflow_name is not found.
        """
        try:
            anthill_app.get_handler(request.workflow_name)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Unknown workflow: {request.workflow_name}")

        channel = ApiChannel(request.workflow_name, request.initial_state)
        runner = Runner(anthill_app, channel)
        background_tasks.add_task(_run_workflow, runner)
        return WebhookResponse(run_id=runner.id)

    return api


app = create_app()
