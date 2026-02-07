"""Antkeeper core framework components.

This module provides the core building blocks for creating workflow-based
applications with handlers, runners, and state management.

The core framework consists of:
- App: Handler registry and decorator-based workflow registration
- Runner: Workflow execution engine with logging and state persistence
- State: Type alias for workflow data (dict[str, Any])
- Channel: Protocol for I/O boundaries and workflow configuration
- WorkflowFailedError: Exception for signaling workflow failures

Typical usage:
    from antkeeper.core import App, Runner

    app = App()

    @app.handler
    def my_workflow(runner, state):
        runner.report_progress("Working...")
        return {**state, "result": "done"}

    channel = CliChannel(workflow_name="my_workflow", initial_state={})
    runner = Runner(app, channel)
    final_state = runner.run()
"""
