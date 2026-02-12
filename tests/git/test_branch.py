"""Tests for antkeeper.git.branch module.

This module contains unit tests for the branch-related functionality in the
antkeeper.git.branch module, specifically testing the current() function which
retrieves the current Git branch name.

Tests are performed using a temporary Git repository provided by the git_repo fixture.
"""

import subprocess

from antkeeper.git.branch import current


class TestCurrent:
    """Test suite for the current() function in antkeeper.git.branch.

    Tests the behavior of retrieving the current Git branch name across different
    Git repository states including normal branches, newly created branches, and
    detached HEAD states.
    """

    def test_current_returns_default_branch(self, git_repo):
        """Test that current() returns the default branch name.

        Verifies that the current() function correctly identifies and returns the
        name of the default branch (typically 'main' or 'master') by comparing it
        with the output of git rev-parse --abbrev-ref HEAD.

        Args:
            git_repo: Pytest fixture providing a temporary Git repository.
        """
        expected = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert current() == expected

    def test_current_returns_switched_branch(self, git_repo):
        """Test that current() returns the name of a newly created and switched branch.

        Creates a new feature branch and verifies that current() correctly identifies
        the branch after switching to it via git checkout -b.

        Args:
            git_repo: Pytest fixture providing a temporary Git repository.
        """
        subprocess.run(
            ["git", "checkout", "-b", "feat/test-branch"],
            capture_output=True,
            check=True,
        )
        assert current() == "feat/test-branch"

    def test_current_on_detached_head(self, git_repo):
        """Test that current() returns 'HEAD' when in detached HEAD state.

        Puts the repository into a detached HEAD state and verifies that current()
        returns 'HEAD' as the branch name, which is the expected behavior when no
        branch is currently checked out.

        Args:
            git_repo: Pytest fixture providing a temporary Git repository.
        """
        subprocess.run(
            ["git", "checkout", "--detach"],
            capture_output=True,
            check=True,
        )
        assert current() == "HEAD"
