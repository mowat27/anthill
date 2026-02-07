"""LLM agent abstractions for Anthill workflows.

This module defines the Agent protocol that all LLM implementations must follow.
Agents provide a uniform interface for executing prompts regardless of the
underlying LLM provider (Claude Code CLI, OpenAI, etc.).
"""

from typing import Protocol


class Agent(Protocol):
    """Protocol for LLM agents that execute prompts.

    Implementations must provide a prompt() method that accepts a string
    and returns the LLM's response. The protocol allows for dependency
    injection and easy testing via mock agents.

    Example:
        >>> class MockAgent:
        ...     def prompt(self, prompt: str) -> str:
        ...         return "mock response"
        >>> agent = MockAgent()
        >>> agent.prompt("test")
        'mock response'
    """

    def prompt(self, prompt: str) -> str:
        """Execute a prompt and return the response.

        Args:
            prompt: The prompt string to send to the LLM.

        Returns:
            The LLM's response as a string.

        Raises:
            AgentExecutionError: If the agent fails to execute the prompt.
        """
        ...
