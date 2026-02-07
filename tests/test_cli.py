"""CLI parsing and integration tests.

Tests command-line argument parsing, state pair parsing, and end-to-end
CLI workflow execution with dynamic handler loading.
"""

import argparse
import os
import tempfile
import textwrap

import pytest

from anthill.cli import main, parse_state_pairs


class TestParseStatePairs:
    """Test suite for parse_state_pairs function."""

    def test_parse_empty_pairs(self):
        """Test parsing state pairs with no initial state provided."""
        assert parse_state_pairs([]) == {}

    def test_parse_run_with_state_pairs(self):
        """Test parsing key=value pairs into initial state dictionary."""
        pairs = ["key=val", "k2=v2"]
        assert parse_state_pairs(pairs) == {"key": "val", "k2": "v2"}

    def test_invalid_state_pair_exits(self):
        """Test that malformed state pairs cause the parser to exit."""
        with pytest.raises(SystemExit):
            parse_state_pairs(["no_equals_sign"])


class TestArgParsing:
    """Test suite for command-line argument parsing."""

    def _build_parser(self):
        """Build and configure argument parser for testing CLI commands."""
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        run_p = sub.add_parser("run")
        run_p.add_argument("--agents-file", default="handlers.py")
        run_p.add_argument("--initial-state", action="append", default=[])
        prompt_group = run_p.add_mutually_exclusive_group()
        prompt_group.add_argument("--prompt", default=None)
        prompt_group.add_argument("--prompt-file", default=None)
        run_p.add_argument("--model", default=None)
        run_p.add_argument("workflow_name")
        return parser

    def test_parse_run_with_workflow_name(self):
        """Test that workflow_name positional argument is parsed."""
        args = self._build_parser().parse_args(["run", "my_handler"])
        assert args.workflow_name == "my_handler"

    def test_parse_run_with_prompt_flag(self):
        """Test that --prompt flag is parsed."""
        args = self._build_parser().parse_args(["run", "--prompt", "build a widget", "my_handler"])
        assert args.prompt == "build a widget"

    def test_parse_run_with_model_flag(self):
        """Test that --model flag is parsed."""
        args = self._build_parser().parse_args(["run", "--model", "opus", "my_handler"])
        assert args.model == "opus"

    def test_parse_run_with_agents_file(self):
        """Test that custom agents file path is correctly parsed."""
        args = self._build_parser().parse_args(["run", "--agents-file", "custom.py", "my_handler"])
        assert args.agents_file == "custom.py"

    def test_parse_run_with_prompt_file_flag(self):
        """Test that --prompt-file flag is parsed."""
        args = self._build_parser().parse_args(["run", "--prompt-file", "foo.txt", "my_handler"])
        assert args.prompt_file == "foo.txt"

    def test_prompt_and_prompt_file_mutually_exclusive(self):
        """Test that providing both --prompt and --prompt-file causes parser to exit."""
        with pytest.raises(SystemExit):
            self._build_parser().parse_args(["run", "--prompt", "x", "--prompt-file", "y", "my_handler"])

    def test_parse_run_missing_workflow_name_exits(self):
        """Test that missing workflow name argument causes parser to exit."""
        with pytest.raises(SystemExit):
            self._build_parser().parse_args(["run"])


class TestCliIntegration:
    """Integration tests for end-to-end CLI workflow execution."""

    def test_cli_loads_agents_file_and_runs(self, monkeypatch, capsys):
        """Test end-to-end CLI execution with dynamic handler loading from file."""
        log_dir = tempfile.mkdtemp()
        agents_code = textwrap.dedent(f"""\
            from anthill.core.app import App
            from anthill.core.domain import State

            app = App(log_dir="{log_dir}")

            @app.handler
            def add_1(runner, state: State) -> State:
                return {{**state, "result": int(state["result"]) + 1}}
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

    def test_prompt_file_loaded_into_state(self, monkeypatch, capsys):
        """Test that --prompt-file reads file contents into state['prompt']."""
        log_dir = tempfile.mkdtemp()
        agents_code = textwrap.dedent(f"""\
            from anthill.core.app import App
            from anthill.core.domain import State

            app = App(log_dir="{log_dir}")

            @app.handler
            def echo(runner, state: State) -> State:
                return {{**state, "result": f"prompt={{state['prompt']}}"}}
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(agents_code)
            f.flush()
            agents_path = f.name

        prompt_content = "hello from file"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as pf:
            pf.write(prompt_content)
            pf.flush()
            prompt_path = pf.name

        try:
            monkeypatch.setattr("sys.argv", [
                "anthill", "run",
                "--agents-file", agents_path,
                "--prompt-file", prompt_path,
                "echo",
            ])
            main()
            captured = capsys.readouterr()
            assert "prompt=hello from file" in captured.out
        finally:
            os.unlink(agents_path)
            os.unlink(prompt_path)

    def test_prompt_file_not_found_exits(self, monkeypatch, capsys):
        """Test that --prompt-file with nonexistent path prints error and exits 1."""
        log_dir = tempfile.mkdtemp()
        agents_code = textwrap.dedent(f"""\
            from anthill.core.app import App
            from anthill.core.domain import State

            app = App(log_dir="{log_dir}")

            @app.handler
            def echo(runner, state: State) -> State:
                return state
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(agents_code)
            f.flush()
            agents_path = f.name

        try:
            monkeypatch.setattr("sys.argv", [
                "anthill", "run",
                "--agents-file", agents_path,
                "--prompt-file", "/nonexistent/path/prompt.md",
                "echo",
            ])
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "prompt file not found" in captured.err.lower()
        finally:
            os.unlink(agents_path)

    def test_prompt_and_model_merged_into_state(self, monkeypatch, capsys):
        """Test that --prompt and --model flags are merged into handler state."""
        log_dir = tempfile.mkdtemp()
        agents_code = textwrap.dedent(f"""\
            from anthill.core.app import App
            from anthill.core.domain import State

            app = App(log_dir="{log_dir}")

            @app.handler
            def echo(runner, state: State) -> State:
                return {{**state, "result": f"prompt={{state['prompt']}},model={{state['model']}}"}}
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(agents_code)
            f.flush()
            agents_path = f.name

        try:
            monkeypatch.setattr("sys.argv", [
                "anthill", "run",
                "--agents-file", agents_path,
                "--prompt", "hello world",
                "--model", "opus",
                "echo",
            ])
            main()
            captured = capsys.readouterr()
            assert "prompt=hello world" in captured.out
            assert "model=opus" in captured.out
        finally:
            os.unlink(agents_path)
