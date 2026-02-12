"""Tests for antkeeper.git.core module.

This module contains unit tests for the core Git functionality in the
antkeeper.git.core module, specifically testing the execute() function which
runs Git commands and handles their output and errors.

Tests are performed using a temporary Git repository provided by the git_repo fixture.
"""

import pytest

from antkeeper.git.core import GitCommandError, execute


class TestExecute:
    """Test suite for the execute() function in antkeeper.git.core.

    Tests the behavior of the execute() function which runs Git commands,
    including successful command execution, error handling, and output capture
    across various Git operations.
    """

    def test_execute_returns_stdout(self, git_repo):
        """Test that execute() returns stdout output from successful Git commands.

        Verifies that the execute() function captures and returns the standard output
        from a Git command (git log --oneline) as a non-empty string.

        Args:
            git_repo: Pytest fixture providing a temporary Git repository.
        """
        result = execute(["git", "log", "--oneline"])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_execute_raises_git_command_error_on_failure(self, git_repo):
        """Test that execute() raises GitCommandError when Git command fails.

        Verifies that the execute() function properly raises a GitCommandError
        exception when attempting to execute a Git command that fails (such as
        checking out a non-existent branch).

        Args:
            git_repo: Pytest fixture providing a temporary Git repository.
        """
        with pytest.raises(GitCommandError):
            execute(["git", "checkout", "nonexistent-branch"])

    def test_execute_returns_empty_string_for_silent_command(self, git_repo):
        """Test that execute() returns empty string for commands with no output.

        Verifies that the execute() function returns an empty string when executing
        Git commands that produce no output (such as git tag -l with no tags).

        Args:
            git_repo: Pytest fixture providing a temporary Git repository.
        """
        result = execute(["git", "tag", "-l"])
        assert result == ""

    def test_execute_prepends_git_when_not_present(self, git_repo):
        """Test that execute() auto-prepends 'git' when not present in command.

        Args:
            git_repo: Pytest fixture providing a temporary Git repository.
        """
        result = execute(["log", "--oneline"])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_execute_without_git_prefix_raises_on_failure(self, git_repo):
        """Test that execute() raises GitCommandError without 'git' prefix.

        Args:
            git_repo: Pytest fixture providing a temporary Git repository.
        """
        with pytest.raises(GitCommandError):
            execute(["checkout", "nonexistent-branch"])

    def test_execute_without_git_prefix_returns_empty_string(self, git_repo):
        """Test that execute() returns empty string without 'git' prefix.

        Args:
            git_repo: Pytest fixture providing a temporary Git repository.
        """
        result = execute(["tag", "-l"])
        assert result == ""
