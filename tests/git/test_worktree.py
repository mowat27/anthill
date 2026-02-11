"""Tests for the Worktree class.

Verifies Worktree functionality including:
- Path construction from base_dir and name
- Worktree creation with optional branch specification
- Base directory creation
- Worktree removal
- Error handling for duplicate and non-existent worktrees
"""

import os
import subprocess

import pytest

from antkeeper.git.worktrees import Worktree, WorktreeError


class TestWorktree:
    """Test suite for Worktree class operations."""

    def test_path_is_absolute_join_of_base_dir_and_name(self, git_repo):
        """Test that Worktree.path is the absolute path of base_dir joined with name."""
        base = os.path.join(git_repo, "trees")
        wt = Worktree(base_dir=base, name="my-tree")
        assert wt.path == os.path.realpath(os.path.join(base, "my-tree"))

    def test_exists_false_when_not_created(self, git_repo):
        """Test that Worktree.exists returns False for non-existent worktree."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="nope")
        assert wt.exists is False

    def test_create_makes_worktree_on_disk(self, git_repo):
        """Test that Worktree.create() creates worktree on disk."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="wt1")
        wt.create()
        assert wt.exists is True

    def test_create_with_branch(self, git_repo):
        """Test that Worktree.create() with branch parameter creates specified branch."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="wt-branch")
        wt.create(branch="feat-x")
        result = subprocess.run(
            ["git", "-C", wt.path, "branch", "--show-current"],
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "feat-x"

    def test_create_makes_base_dir(self, git_repo):
        """Test that Worktree.create() creates base directory if it doesn't exist."""
        base = os.path.join(git_repo, "deep", "nested", "trees")
        wt = Worktree(base_dir=base, name="wt-nested")
        assert not os.path.isdir(base)
        wt.create()
        assert os.path.isdir(base)

    def test_create_raises_worktree_error_on_failure(self, git_repo):
        """Test that Worktree.create() raises WorktreeError when git worktree add fails."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="wt-dup")
        wt.create()
        wt2 = Worktree(base_dir=os.path.join(git_repo, "trees"), name="wt-dup2")
        with pytest.raises(WorktreeError):
            wt2.create(branch="main")

    def test_remove_deletes_worktree(self, git_repo):
        """Test that Worktree.remove() deletes existing worktree."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="wt-rm")
        wt.create()
        assert wt.exists is True
        wt.remove()
        assert wt.exists is False

    def test_remove_nonexistent_raises_worktree_error(self, git_repo):
        """Test that Worktree.remove() raises WorktreeError for non-existent worktree."""
        wt = Worktree(base_dir=os.path.join(git_repo, "trees"), name="ghost")
        with pytest.raises(WorktreeError):
            wt.remove()
