"""Claude Code agent implementation.

Executes prompts via the `claude` CLI subprocess.
"""

import subprocess

from anthill.llm.errors import AgentExecutionError


class ClaudeCodeAgent:
    """Agent that delegates prompts to the Claude Code CLI."""

    def __init__(self, model: str | None = None) -> None:
        """Initialize the Claude Code agent.

        Args:
            model: Optional model identifier to pass to the Claude CLI.
        """
        self.model = model

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
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            raise AgentExecutionError("claude binary not found")
        if result.returncode != 0:
            raise AgentExecutionError(
                f"claude exited with code {result.returncode}: {result.stderr}"
            )
        return result.stdout
