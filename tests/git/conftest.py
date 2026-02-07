"""Fixtures for git integration tests."""

import os
import subprocess
import tempfile

import pytest


@pytest.fixture
def git_repo():
    """Create a temporary git repository with an initial commit.

    Sets up a minimal git repository with user config and an initial commit
    containing init.txt. Changes cwd to the repo directory during the test.

    Yields:
        str: Absolute path to the temporary git repository.

    Note:
        Automatically restores the original working directory after the test.
    """
    repo_dir = tempfile.mkdtemp()
    subprocess.run(["git", "init", repo_dir], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", repo_dir, "config", "user.name", "Test"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo_dir, "config", "user.email", "test@test.com"],
        capture_output=True,
        check=True,
    )
    init_file = os.path.join(repo_dir, "init.txt")
    with open(init_file, "w") as f:
        f.write("init\n")
    subprocess.run(["git", "-C", repo_dir, "add", "."], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", repo_dir, "commit", "-m", "init"],
        capture_output=True,
        check=True,
    )
    original_dir = os.getcwd()
    os.chdir(repo_dir)
    yield repo_dir
    os.chdir(original_dir)
