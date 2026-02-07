"""LLM agent abstractions for Anthill workflows.

Defines the Agent protocol for LLM interactions.
"""

from typing import Protocol


class Agent(Protocol):
    """Protocol for LLM agents that execute prompts."""

    def prompt(self, prompt: str) -> str:
        """Execute a prompt and return the response.

        Args:
            prompt: The prompt string to send to the LLM.

        Returns:
            The LLM's response as a string.
        """
        ...
