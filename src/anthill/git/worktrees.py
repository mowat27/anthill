"""Git worktree management for isolated workflow execution."""

import logging
import os
import subprocess
from collections.abc import Generator
from contextlib import contextmanager

logger = logging.getLogger("anthill.git.worktrees")


class WorktreeError(Exception):
    """Raised when a git worktree operation fails.

    This exception is raised when git worktree commands (add, remove) fail
    or when attempting to use a non-existent worktree.
    """


class Worktree:
    """Represents a git worktree on disk.

    Wraps git worktree subprocess operations for creating and removing
    worktrees. The path is always stored as an absolute path.

    Attributes:
        base_dir (str): Absolute path to the directory containing worktrees.
        name (str): Name of the worktree (used as subdirectory name).
        path (str): Absolute path to the worktree (base_dir/name).
    """

    def __init__(self, base_dir: str, name: str) -> None:
        """Initialize a Worktree instance.

        Args:
            base_dir (str): Directory where the worktree will be created.
            name (str): Name for the worktree subdirectory.
        """
        self.base_dir = os.path.realpath(base_dir)
        self.name = name
        self.path = os.path.realpath(os.path.join(base_dir, name))

    @property
    def exists(self) -> bool:
        """Check if the worktree directory exists on disk.

        Returns:
            bool: True if the worktree path exists as a directory, False otherwise.
        """
        return os.path.isdir(self.path)

    def create(self, branch: str | None = None) -> None:
        """Create the worktree using git worktree add.

        Creates the base directory if it doesn't exist. If branch is provided,
        creates a new branch with that name for the worktree.

        Args:
            branch (str | None): Optional name for a new branch to create. If None,
                uses the current HEAD.

        Raises:
            WorktreeError: If the git worktree add command fails.
        """
        os.makedirs(self.base_dir, exist_ok=True)
        cmd = ["git", "worktree", "add"]
        if branch:
            cmd += ["-b", branch]
        cmd.append(self.path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise WorktreeError(result.stderr.strip())
        logger.info(f"Worktree created: {self.path}")

    def remove(self) -> None:
        """Remove the worktree using git worktree remove.

        Raises:
            WorktreeError: If the git worktree remove command fails.
        """
        result = subprocess.run(
            ["git", "worktree", "remove", self.path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise WorktreeError(result.stderr.strip())
        logger.info(f"Worktree removed: {self.path}")


@contextmanager
def git_worktree(
    worktree: Worktree,
    *,
    create: bool = False,
    branch: str | None = None,
    remove: bool = False,
) -> Generator[Worktree, None, None]:
    """Context manager that enters a git worktree directory.

    Guarantees cwd restoration via try/finally. Optionally creates and/or
    removes the worktree.

    Args:
        worktree (Worktree): The Worktree instance to enter.
        create (bool): If True, create the worktree before entering. Defaults to False.
        branch (str | None): Optional branch name to create with the worktree. Only
            used when create=True.
        remove (bool): If True, remove the worktree on exit. Defaults to False.

    Yields:
        Worktree: The worktree instance that was entered.

    Raises:
        WorktreeError: If create=False and the worktree doesn't exist, or if
            git operations fail.

    Example:
        >>> wt = Worktree(base_dir="trees", name="feature-branch")
        >>> with git_worktree(wt, create=True, branch="feat", remove=True):
        ...     # Work in the worktree
        ...     pass  # Worktree is automatically cleaned up
    """
    if create:
        worktree.create(branch=branch)
    elif not worktree.exists:
        raise WorktreeError(f"Worktree does not exist: {worktree.path}")
    original_dir = os.getcwd()
    os.chdir(worktree.path)
    try:
        yield worktree
    finally:
        os.chdir(original_dir)
        if remove:
            worktree.remove()
