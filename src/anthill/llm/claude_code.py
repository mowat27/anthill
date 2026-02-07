"""Claude Code agent implementation.

Executes prompts via the `claude` CLI subprocess.
"""

import logging
import subprocess

from anthill.llm.errors import AgentExecutionError

logger = logging.getLogger("anthill.llm.claude_code")


class ClaudeCodeAgent:
    """Agent that delegates prompts to the Claude Code CLI."""

    def __init__(self, model: str | None = None) -> None:
        """Initialize the Claude Code agent.

        Args:
            model: Optional model identifier to pass to the Claude CLI.
        """
        self.model = model
        logger.debug(f"ClaudeCodeAgent initialized: model={self.model}")

    def prompt(self, prompt: str) -> str:
        """Execute a prompt via `claude -p` and return stdout.

        Args:
            prompt: The prompt string to send to Claude Code CLI.

        Returns:
            The CLI's response as a string.

        Raises:
            AgentExecutionError: On non-zero exit or missing binary.
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
