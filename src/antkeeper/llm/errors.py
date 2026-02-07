"""LLM agent error types.

This module defines custom exceptions for LLM agent operations. These
exceptions provide structured error handling for agent execution failures.
"""


class AgentExecutionError(Exception):
    """Raised when an agent fails to execute a prompt.

    This exception is raised when the Claude Code CLI cannot be found,
    returns a non-zero exit code, or encounters other execution failures.

    Example:
        >>> raise AgentExecutionError("claude binary not found")
        Traceback (most recent call last):
        ...
        AgentExecutionError: claude binary not found

    """

    pass
