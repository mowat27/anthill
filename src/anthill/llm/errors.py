"""LLM agent error types."""


class AgentExecutionError(Exception):
    """Raised when an agent fails to execute a prompt.

    This exception is raised when the Claude Code CLI cannot be found,
    returns a non-zero exit code, or encounters other execution failures.
    """
