"""Webhook endpoint logic for Anthill workflow triggers."""
from typing import Any

from fastapi import BackgroundTasks, HTTPException
from pydantic import BaseModel

from anthill.channels.api import ApiChannel
from anthill.core.app import App
from anthill.core.runner import Runner
from anthill.http import run_workflow_background


class WebhookRequest(BaseModel):
    """Request model for webhook endpoint.

    Attributes:
        workflow_name: Name of the registered workflow handler to invoke.
        initial_state: Optional initial state dictionary to pass to the workflow.
    """
    workflow_name: str
    initial_state: dict[str, Any] = {}


class WebhookResponse(BaseModel):
    """Response model for webhook endpoint.

    Attributes:
        run_id: Unique identifier for the initiated workflow run.
    """
    run_id: str


async def handle_webhook(request: WebhookRequest, background_tasks: BackgroundTasks, anthill_app: App) -> WebhookResponse:
    try:
        anthill_app.get_handler(request.workflow_name)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown workflow: {request.workflow_name}")

    channel = ApiChannel(request.workflow_name, request.initial_state)
    runner = Runner(anthill_app, channel)
    background_tasks.add_task(run_workflow_background, runner)
    return WebhookResponse(run_id=runner.id)
