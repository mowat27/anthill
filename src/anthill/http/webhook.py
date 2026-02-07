"""Webhook endpoint for Anthill workflow triggers.

Extracted from server.py to allow modular route registration.
"""
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel

from anthill.channels.api import ApiChannel
from anthill.core.app import App
from anthill.core.runner import Runner


class WebhookRequest(BaseModel):
    workflow_name: str
    initial_state: dict[str, Any] = {}


class WebhookResponse(BaseModel):
    run_id: str


def setup_webhook_routes(api: FastAPI, anthill_app: App) -> None:
    from anthill.server import _run_workflow

    @api.post("/webhook", response_model=WebhookResponse)
    async def webhook(request: WebhookRequest, background_tasks: BackgroundTasks) -> WebhookResponse:
        try:
            anthill_app.get_handler(request.workflow_name)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Unknown workflow: {request.workflow_name}")

        channel = ApiChannel(request.workflow_name, request.initial_state)
        runner = Runner(anthill_app, channel)
        background_tasks.add_task(_run_workflow, runner)
        return WebhookResponse(run_id=runner.id)
