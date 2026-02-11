"""Tests for the git_worktree context manager.

Verifies that the git_worktree context manager correctly:
- Creates and enters worktrees with optional branch creation
- Restores the current working directory on exit (normal and exception paths)
- Optionally removes worktrees on exit
- Raises appropriate errors for non-existent worktrees
"""

import os
import subprocess

import pytest

from antkeeper.git.worktrees import Worktree, WorktreeError, git_worktree


class TestGitWorktreeContextManager:
    """Test suite for git_worktree context manager behavior."""

    def test_creates_worktree_when_create_true(self, git_repo):
        """Test that context manager creates worktree when create=True."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="ctx-create")
        with git_worktree(wt, create=True):
            assert wt.exists is True

    def test_creates_with_branch(self, git_repo):
        """Test that context manager creates worktree with specified branch."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="ctx-branch")
        with git_worktree(wt, create=True, branch="feat"):
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
            )
            assert result.stdout.strip() == "feat"

    def test_changes_cwd_to_worktree(self, git_repo):
        """Test that context manager changes working directory to worktree path."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="ctx-cwd")
        with git_worktree(wt, create=True):
            assert os.getcwd() == wt.path

    def test_yields_worktree_instance(self, git_repo):
        """Test that context manager yields the Worktree instance."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="ctx-yield")
        with git_worktree(wt, create=True) as result:
            assert result is wt

    def test_enters_existing_worktree(self, git_repo):
        """Test that context manager can enter existing worktree without create flag."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="ctx-exist")
        wt.create()
        with git_worktree(wt):
            assert os.getcwd() == wt.path

    def test_raises_worktree_error_when_not_exists_and_create_false(self, git_repo):
        """Test that WorktreeError is raised when worktree doesn't exist and create=False."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="ctx-missing")
        with pytest.raises(WorktreeError):
            with git_worktree(wt):
                pass

    def test_restores_cwd_on_normal_exit(self, git_repo):
        """Test that context manager restores original working directory on normal exit."""
        original = os.getcwd()
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="ctx-restore")
        with git_worktree(wt, create=True):
            pass
        assert os.getcwd() == original

    def test_restores_cwd_on_exception(self, git_repo):
        """Test that context manager restores working directory even when exception is raised."""
        original = os.getcwd()
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="ctx-exc")
        with pytest.raises(RuntimeError):
            with git_worktree(wt, create=True):
                raise RuntimeError("boom")
        assert os.getcwd() == original

    def test_removes_when_remove_true(self, git_repo):
        """Test that context manager removes worktree on exit when remove=True."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="ctx-rm")
        with git_worktree(wt, create=True, remove=True):
            assert wt.exists is True
        assert wt.exists is False

    def test_keeps_when_remove_false(self, git_repo):
        """Test that context manager preserves worktree on exit when remove=False."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="ctx-keep")
        with git_worktree(wt, create=True, remove=False):
            pass
        assert wt.exists is True
