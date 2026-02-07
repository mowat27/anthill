"""FastAPI server for Anthill workflows.

Defines all routes and delegates to library modules for implementation.
"""
import os

import dotenv
from fastapi import BackgroundTasks, FastAPI, Request

from anthill.cli import load_app
from anthill.http.webhook import WebhookRequest, WebhookResponse, handle_webhook
from anthill.http.slack_events import SlackEventProcessor


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
    slack = SlackEventProcessor(anthill_app)

    @api.post("/webhook", response_model=WebhookResponse)
    async def webhook(request: WebhookRequest, background_tasks: BackgroundTasks):
        """Webhook endpoint for triggering Anthill workflows via HTTP POST.

        Args:
            request: Webhook request with workflow name and initial state.
            background_tasks: FastAPI background tasks for async execution.

        Returns:
            WebhookResponse with unique run ID for the triggered workflow.
        """
        return await handle_webhook(request, background_tasks, anthill_app)

    @api.post("/slack_event")
    async def slack_event(request: Request):
        """Slack event endpoint for receiving and processing Slack events.

        Receives Slack event payloads, handles URL verification challenges,
        and dispatches message events to appropriate workflow handlers.

        Args:
            request: FastAPI Request object containing Slack event JSON payload.

        Returns:
            JSON response for Slack event processing (challenge response or acknowledgment).
        """
        body = await request.json()
        return await slack.handle_event(body)

    return api


app = create_app()
"""FastAPI application instance configured with Anthill workflow routes.

This is the ASGI application instance that should be passed to uvicorn or
other ASGI servers. It is created by calling create_app() with default
parameters (reading from ANTHILL_AGENTS_FILE environment variable or
using "handlers.py" as the default agents file).
"""
