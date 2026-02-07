"""Command-line interface for Anthill workflow framework.

This module provides the CLI entry point for executing Anthill workflows.
It handles argument parsing, app loading from Python files, initial state
configuration, and runner setup.

The CLI supports a 'run' command that loads an app from a Python file,
configures initial state from command-line arguments, and executes the
requested workflow through a CliChannel.
"""
import argparse
import importlib.util
import logging
import os
import sys
from pathlib import Path

from anthill.channels.cli import CliChannel
from anthill.core.domain import WorkflowFailedError
from anthill.core.runner import Runner

logger = logging.getLogger("anthill.cli")


def load_app(path: str):
    """Dynamically load an Anthill app from a Python file.

    Uses importlib to dynamically import a Python module and extract its
    'app' attribute, which should be an instance of anthill.core.app.App.

    Args:
        path: File path to the Python module containing the app.

    Returns:
        The app object from the loaded module.

    Raises:
        FileNotFoundError: If the file cannot be found or the module spec
            cannot be created.
        AttributeError: If the loaded module does not have an 'app' attribute.
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


def main() -> None:
    """Main entry point for the Anthill CLI.

    Parses command-line arguments and executes the requested workflow.

    Commands:
        run: Execute a workflow with the following options:
            --agents-file: Path to Python file containing the app
                (default: handlers.py)
            --initial-state: Key=value pairs for initial workflow state
                (repeatable)
            --prompt: User prompt to pass to the workflow
                (mutually exclusive with --prompt-file)
            --prompt-file: Path to file containing user prompt
                (mutually exclusive with --prompt)
            --model: Model identifier to use for LLM operations
            workflow_name: Name of the workflow to execute (positional)

        server: Start the FastAPI server with the following options:
            --host: Host address to bind (default: 127.0.0.1)
            --port: Port number to bind (default: 8000)
            --reload: Enable auto-reload on code changes
            --agents-file: Path to Python file containing the app
                (default: handlers.py)

    Raises:
        SystemExit: Exit code 0 for success, 1 for errors (file not found,
            invalid arguments, workflow failure).

    Examples:
        anthill run my_workflow
        anthill run --agents-file=my_handlers.py --prompt="Hello" my_workflow
        anthill run --prompt-file=prompt.md my_workflow
        anthill run --initial-state key1=val1 --initial-state key2=val2 my_workflow
        anthill server --host 0.0.0.0 --port 8000
    """
    parser = argparse.ArgumentParser(prog="anthill")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--agents-file", default="handlers.py")
    run_parser.add_argument("--initial-state", action="append", default=[])
    prompt_group = run_parser.add_mutually_exclusive_group()
    prompt_group.add_argument("--prompt", default=None)
    prompt_group.add_argument("--prompt-file", default=None)
    run_parser.add_argument("--model", default=None)
    run_parser.add_argument("workflow_name")

    server_parser = subparsers.add_parser("server")
    server_parser.add_argument("--host", default="127.0.0.1")
    server_parser.add_argument("--port", type=int, default=8000)
    server_parser.add_argument("--reload", action="store_true")
    server_parser.add_argument("--agents-file", default="handlers.py")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    logger.debug(f"CLI args parsed: command={args.command}")

    if args.command == "run":
        agents_file = args.agents_file
        try:
            app = load_app(agents_file)
        except FileNotFoundError:
            logger.error(f"Agents file not found: {agents_file}")
            print(f"Error: agents file not found: {agents_file}", file=sys.stderr)
            sys.exit(1)
        except AttributeError:
            logger.error(f"{agents_file} has no 'app' attribute")
            print(f"Error: {agents_file} has no 'app' attribute", file=sys.stderr)
            sys.exit(1)

        logger.info(f"App loaded from {agents_file}")
        state = parse_state_pairs(args.initial_state)
        if args.prompt is not None:
            state["prompt"] = args.prompt
        if args.prompt_file is not None:
            try:
                state["prompt"] = Path(args.prompt_file).read_text()
            except FileNotFoundError:
                logger.error(f"Prompt file not found: {args.prompt_file}")
                print(f"Error: prompt file not found: {args.prompt_file}", file=sys.stderr)
                sys.exit(1)
        if args.model is not None:
            state["model"] = args.model
        channel = CliChannel(workflow_name=args.workflow_name, initial_state=state)
        runner = Runner(app, channel)
        logger.info(f"Runner created: run_id={runner.id}")
        try:
            result = runner.run()
        except WorkflowFailedError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        logger.info("Workflow run complete")
        print(result)

    elif args.command == "server":
        import uvicorn

        os.environ["ANTHILL_AGENTS_FILE"] = args.agents_file
        uvicorn.run("anthill.server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
