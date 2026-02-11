"""Git integration for the Antkeeper framework.

This module provides git worktree management functionality for isolated workflow
execution. Worktrees allow multiple working directories for the same repository,
enabling parallel workflow execution without conflicts.

Exports:
    Worktree: Class representing a git worktree on disk.
    WorktreeError: Exception raised when worktree operations fail.
    git_worktree: Context manager for creating, entering, and cleaning up worktrees.
"""

from antkeeper.git.worktrees import Worktree, WorktreeError, git_worktree

__all__ = ["Worktree", "WorktreeError", "git_worktree"]
