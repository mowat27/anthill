"""Claude Code agent implementation.

This module provides a concrete Agent implementation that executes prompts
by delegating to the `claude` CLI subprocess. The agent wraps subprocess
calls and handles command construction, error reporting, and response parsing.
"""

import logging
import subprocess

from antkeeper.llm.errors import AgentExecutionError

logger = logging.getLogger("antkeeper.llm.claude_code")


class ClaudeCodeAgent:
    """Agent that delegates prompts to the Claude Code CLI.

    This agent implementation shells out to the `claude` binary installed
    on the system. It constructs appropriate command-line arguments, handles
    subprocess execution, and converts CLI errors into AgentExecutionErrors.

    Attributes:
        model: Optional model identifier passed to the Claude CLI via --model flag.

    Example:
        >>> agent = ClaudeCodeAgent(model="claude-opus-4")
        >>> response = agent.prompt("What is 2+2?")

    """

    def __init__(self, model: str | None = None) -> None:
        """Initialize the Claude Code agent.

        Args:
            model: Optional model identifier to pass to the Claude CLI
                via the --model flag. If None, uses the CLI's default model.

        """
        self.model = model
        logger.debug(f"ClaudeCodeAgent initialized: model={self.model}")

    def prompt(self, prompt: str) -> str:
        """Execute a prompt via `claude -p` and return stdout.

        Constructs a subprocess call to the Claude CLI with the -p flag for
        prompt execution. If a model was specified during initialization, adds
        the --model flag. Logs all prompt activity and responses.

        Args:
            prompt: The prompt string to send to Claude Code CLI.

        Returns:
            The CLI's response as a string (stdout).

        Raises:
            AgentExecutionError: If the claude binary is not found or if the
                subprocess exits with a non-zero status code.

        """
        cmd = ["claude", "-p", prompt]
        if self.model:
            cmd[1:1] = ["--model", self.model]
        logger.info(f"LLM prompt submitted (length={len(prompt)} chars)")
        logger.debug(f"LLM prompt content: {prompt}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            logger.error("claude binary not found")
            raise AgentExecutionError("claude binary not found")
        logger.debug(f"LLM subprocess command: {cmd}")
        if result.returncode != 0:
            logger.error(f"claude exited with code {result.returncode}: {result.stderr}")
            raise AgentExecutionError(
                f"claude exited with code {result.returncode}: {result.stderr}"
            )
        logger.info(f"LLM response received (length={len(result.stdout)} chars)")
        logger.debug(f"LLM response content: {result.stdout}")
        return result.stdout
