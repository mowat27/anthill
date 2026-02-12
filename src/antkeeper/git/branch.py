"""Git branch utilities.

This module provides high-level utilities for working with git branches,
including operations to query branch information and manage branch state.
"""

from antkeeper.git.core import execute


def current() -> str:
    """Get the name of the current git branch.

    Returns:
        str: The current branch name, or "HEAD" if in detached HEAD state.

    Raises:
        GitCommandError: If the git command fails.
    """
    return execute(["rev-parse", "--abbrev-ref", "HEAD"])
