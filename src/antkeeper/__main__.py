"""Entry point module for executing Antkeeper as a Python module.

This module enables running Antkeeper via `python -m antkeeper`, which
delegates to the CLI main function.
"""

from antkeeper.cli import main

if __name__ == "__main__":
    main()
