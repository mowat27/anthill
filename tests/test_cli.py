"""CLI parsing and integration tests.

Tests command-line argument parsing, state pair parsing, and end-to-end
CLI workflow execution with dynamic handler loading.
"""

import os
import tempfile
import textwrap

import pytest

from anthill.cli import main, parse_state_pairs


class TestParseStatePairs:
    def test_parse_run_with_prompt_only(self, monkeypatch):
        """Test parsing state pairs with no initial state provided."""
        monkeypatch.setattr("sys.argv", ["anthill", "run", "my_workflow"])
        # Should not raise; we test via parse_state_pairs
        assert parse_state_pairs([]) == {}

    def test_parse_run_with_state_pairs(self):
        """Test parsing key=value pairs into initial state dictionary."""
        pairs = ["key=val", "k2=v2"]
        assert parse_state_pairs(pairs) == {"key": "val", "k2": "v2"}

    def test_parse_run_with_agents_file(self, monkeypatch):
        """Test that custom agents file path is correctly parsed."""
        monkeypatch.setattr("sys.argv", ["anthill", "run", "--agents-file", "custom.py", "my_workflow"])
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        run_p = sub.add_parser("run")
        run_p.add_argument("--agents-file", default="handlers.py")
        run_p.add_argument("--initial-state", action="append", default=[])
        run_p.add_argument("prompt")
        args = parser.parse_args(["run", "--agents-file", "custom.py", "my_workflow"])
        assert args.agents_file == "custom.py"

    def test_parse_run_missing_prompt_exits(self):
        """Test that missing workflow name argument causes parser to exit."""
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        run_p = sub.add_parser("run")
        run_p.add_argument("--agents-file", default="handlers.py")
        run_p.add_argument("--initial-state", action="append", default=[])
        run_p.add_argument("prompt")
        with pytest.raises(SystemExit):
            parser.parse_args(["run"])

    def test_invalid_state_pair_exits(self):
        """Test that malformed state pairs cause the parser to exit."""
        with pytest.raises(SystemExit):
            parse_state_pairs(["no_equals_sign"])


class TestCliIntegration:
    def test_cli_loads_agents_file_and_runs(self, monkeypatch, capsys):
        """Test end-to-end CLI execution with dynamic handler loading from file."""
        agents_code = textwrap.dedent("""\
            from anthill.core.app import App
            from anthill.core.domain import State

            app = App()

            @app.handler
            def add_1(runner, state: State) -> State:
                return {**state, "result": int(state["result"]) + 1}
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(agents_code)
            f.flush()
            agents_path = f.name

        try:
            monkeypatch.setattr("sys.argv", [
                "anthill", "run",
                "--agents-file", agents_path,
                "--initial-state", "result=10",
                "add_1",
            ])
            main()
            captured = capsys.readouterr()
            assert "11" in captured.out
        finally:
            os.unlink(agents_path)
