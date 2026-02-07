"""Command-line interface for Anthill workflow framework.

Provides the main entry point for running Anthill workflows from the command line.
"""
import argparse
import importlib.util
import sys

from anthill.channels.cli import CliChannel
from anthill.core.runner import Runner


def load_app(path: str):
    """Dynamically load an Anthill app from a Python file.

    Args:
        path: File path to the Python module containing the app.

    Returns:
        The app object from the loaded module.

    Raises:
        FileNotFoundError: If the file cannot be found or loaded.
    """
    spec = importlib.util.spec_from_file_location("agents", path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def parse_state_pairs(pairs: list[str]) -> dict[str, str]:
    """Parse command-line state pairs into a dictionary.

    Args:
        pairs: List of strings in "key=value" format.

    Returns:
        Dictionary mapping keys to values.

    Raises:
        SystemExit: If any pair is not in "key=value" format.
    """
    state = {}
    for pair in pairs:
        if "=" not in pair:
            print(f"Error: invalid --initial-state value (expected key=val): {pair}", file=sys.stderr)
            sys.exit(1)
        key, val = pair.split("=", 1)
        state[key] = val
    return state


def main():
    """Main entry point for the Anthill CLI.

    Parses command-line arguments and executes the requested workflow.
    Supports the 'run' command with the following options:
    - --agents-file: Path to Python file containing the app (default: handlers.py)
    - --initial-state: Key=value pairs for initial workflow state (repeatable)
    - --prompt: User prompt to pass to the workflow
    - --model: Model identifier to use for LLM operations
    - workflow_name: Name of the workflow to execute

    Exits with status 0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(prog="anthill")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--agents-file", default="handlers.py")
    run_parser.add_argument("--initial-state", action="append", default=[])
    run_parser.add_argument("--prompt", default=None)
    run_parser.add_argument("--model", default=None)
    run_parser.add_argument("workflow_name")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "run":
        agents_file = args.agents_file
        try:
            app = load_app(agents_file)
        except FileNotFoundError:
            print(f"Error: agents file not found: {agents_file}", file=sys.stderr)
            sys.exit(1)
        except AttributeError:
            print(f"Error: {agents_file} has no 'app' attribute", file=sys.stderr)
            sys.exit(1)

        state = parse_state_pairs(args.initial_state)
        if args.prompt is not None:
            state["prompt"] = args.prompt
        if args.model is not None:
            state["model"] = args.model
        channel = CliChannel(workflow_name=args.workflow_name, initial_state=state)
        runner = Runner(app, channel)
        result = runner.run()
        print(result)


if __name__ == "__main__":
    main()
