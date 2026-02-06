import argparse
import importlib.util
import sys

from anthill.channels.cli import CliChannel
from anthill.core.runner import Runner


def load_app(path: str):
    spec = importlib.util.spec_from_file_location("agents", path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def parse_state_pairs(pairs: list[str]) -> dict[str, str]:
    state = {}
    for pair in pairs:
        if "=" not in pair:
            print(f"Error: invalid --initial-state value (expected key=val): {pair}", file=sys.stderr)
            sys.exit(1)
        key, val = pair.split("=", 1)
        state[key] = val
    return state


def main():
    parser = argparse.ArgumentParser(prog="anthill")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--agents-file", default="handlers.py")
    run_parser.add_argument("--initial-state", action="append", default=[])
    run_parser.add_argument("prompt")

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
        channel = CliChannel(workflow_name=args.prompt, initial_state=state)
        runner = Runner(app, channel)
        result = runner.run()
        print(result)


if __name__ == "__main__":
    main()
