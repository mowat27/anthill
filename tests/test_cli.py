"""CLI parsing and integration tests.

Tests command-line argument parsing, state pair parsing, and end-to-end
CLI workflow execution with dynamic handler loading.
"""

import argparse
import io
import os
import tempfile
import textwrap

import pytest

from antkeeper.cli import main, parse_state_pairs


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
        """Build and configure argument parser for testing.

        Returns:
            argparse.ArgumentParser: Configured parser with run subcommand.
        """
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        run_p = sub.add_parser("run")
        run_p.add_argument("--agents-file", default="handlers.py")
        run_p.add_argument("--initial-state", action="append", default=[])
        run_p.add_argument("--model", default=None)
        run_p.add_argument("workflow_name")
        run_p.add_argument("prompt_files", nargs="*")
        return parser

    def test_parse_run_with_workflow_name(self):
        """Test that workflow_name positional argument is parsed."""
        args = self._build_parser().parse_args(["run", "my_handler"])
        assert args.workflow_name == "my_handler"

    def test_parse_run_with_model_flag(self):
        """Test that --model flag is parsed."""
        args = self._build_parser().parse_args(["run", "--model", "opus", "my_handler"])
        assert args.model == "opus"

    def test_parse_run_with_agents_file(self):
        """Test that custom agents file path is correctly parsed."""
        args = self._build_parser().parse_args(["run", "--agents-file", "custom.py", "my_handler"])
        assert args.agents_file == "custom.py"

    def test_parse_run_with_prompt_files(self):
        """Test that positional file args are captured in args.prompt_files."""
        args = self._build_parser().parse_args(["run", "my_handler", "file1.md", "file2.md"])
        assert args.prompt_files == ["file1.md", "file2.md"]

    def test_parse_run_missing_workflow_name_exits(self):
        """Test that missing workflow name argument causes parser to exit."""
        with pytest.raises(SystemExit):
            self._build_parser().parse_args(["run"])


class TestInitArgParsing:
    """Test suite for init subcommand argument parsing."""

    def _build_parser(self):
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        init_p = sub.add_parser("init")
        init_p.add_argument("path", nargs="?", default=".")
        return parser

    def test_parse_init_defaults_path_to_dot(self):
        """Test that init command defaults path to current directory."""
        args = self._build_parser().parse_args(["init"])
        assert args.command == "init"
        assert args.path == "."

    def test_parse_init_with_explicit_path(self):
        """Test that init command accepts explicit path argument."""
        args = self._build_parser().parse_args(["init", "my_project"])
        assert args.path == "my_project"


class TestInitIntegration:
    """Integration tests for the init subcommand."""

    def test_init_creates_handlers_file(self, monkeypatch, capsys):
        """Test that init command creates handlers.py file with boilerplate."""
        tmpdir = tempfile.mkdtemp()
        try:
            monkeypatch.setattr("sys.argv", ["antkeeper", "init", tmpdir])
            main()
            target = os.path.join(tmpdir, "handlers.py")
            assert os.path.exists(target)
            content = open(target).read()
            assert "app = App()" in content
            assert "def healthcheck" in content
        finally:
            handlers = os.path.join(tmpdir, "handlers.py")
            if os.path.exists(handlers):
                os.unlink(handlers)
            os.rmdir(tmpdir)

    def test_init_prints_env_info(self, monkeypatch, capsys):
        """Test that init command prints environment variable information."""
        tmpdir = tempfile.mkdtemp()
        try:
            monkeypatch.setattr("sys.argv", ["antkeeper", "init", tmpdir])
            main()
            captured = capsys.readouterr()
            assert "Created handlers.py" in captured.out
            assert "ANTKEEPER_HANDLERS_FILE" in captured.out
        finally:
            handlers = os.path.join(tmpdir, "handlers.py")
            if os.path.exists(handlers):
                os.unlink(handlers)
            os.rmdir(tmpdir)

    def test_init_errors_if_handlers_exists(self, monkeypatch, capsys):
        """Test that init command exits with error if handlers.py already exists."""
        tmpdir = tempfile.mkdtemp()
        handlers = os.path.join(tmpdir, "handlers.py")
        try:
            with open(handlers, "w") as f:
                f.write("# existing\n")
            monkeypatch.setattr("sys.argv", ["antkeeper", "init", tmpdir])
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "already exists" in captured.err
        finally:
            if os.path.exists(handlers):
                os.unlink(handlers)
            os.rmdir(tmpdir)

    def test_init_default_path_uses_cwd(self, monkeypatch, capsys):
        """Test that init command without path argument uses current working directory."""
        tmpdir = tempfile.mkdtemp()
        try:
            monkeypatch.chdir(tmpdir)
            monkeypatch.setattr("sys.argv", ["antkeeper", "init"])
            main()
            target = os.path.join(tmpdir, "handlers.py")
            assert os.path.exists(target)
        finally:
            handlers = os.path.join(tmpdir, "handlers.py")
            if os.path.exists(handlers):
                os.unlink(handlers)
            os.rmdir(tmpdir)

    def test_init_errors_if_directory_missing(self, monkeypatch, capsys):
        """Test that init command exits with error if target directory doesn't exist."""
        tmpdir = tempfile.mkdtemp()
        os.rmdir(tmpdir)
        monkeypatch.setattr("sys.argv", ["antkeeper", "init", tmpdir])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "does not exist" in captured.err


class TestCliIntegration:
    """Integration tests for end-to-end CLI workflow execution."""

    def test_cli_loads_agents_file_and_runs(self, monkeypatch, capsys):
        """Test end-to-end CLI execution with dynamic handler loading from file."""
        log_dir = tempfile.mkdtemp()
        agents_code = textwrap.dedent(f"""\
            from antkeeper.core.app import App
            from antkeeper.core.domain import State

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
            monkeypatch.setattr("sys.stdin.isatty", lambda: True)
            monkeypatch.setattr("sys.argv", [
                "antkeeper", "run",
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
        """Test that a positional file arg reads contents into state['prompt']."""
        log_dir = tempfile.mkdtemp()
        agents_code = textwrap.dedent(f"""\
            from antkeeper.core.app import App
            from antkeeper.core.domain import State

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
                "antkeeper", "run",
                "--agents-file", agents_path,
                "echo", prompt_path,
            ])
            main()
            captured = capsys.readouterr()
            assert "prompt=hello from file" in captured.out
        finally:
            os.unlink(agents_path)
            os.unlink(prompt_path)

    def test_prompt_file_not_found_exits(self, monkeypatch, capsys):
        """Test that a nonexistent positional file path prints error and exits 1."""
        log_dir = tempfile.mkdtemp()
        agents_code = textwrap.dedent(f"""\
            from antkeeper.core.app import App
            from antkeeper.core.domain import State

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
                "antkeeper", "run",
                "--agents-file", agents_path,
                "echo", "/nonexistent/path.md",
            ])
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "file not found" in captured.err.lower()
        finally:
            os.unlink(agents_path)

    def test_prompt_and_model_merged_into_state(self, monkeypatch, capsys):
        """Test that positional file and --model flag are merged into handler state."""
        log_dir = tempfile.mkdtemp()
        agents_code = textwrap.dedent(f"""\
            from antkeeper.core.app import App
            from antkeeper.core.domain import State

            app = App(log_dir="{log_dir}")

            @app.handler
            def echo(runner, state: State) -> State:
                return {{**state, "result": f"prompt={{state['prompt']}},model={{state['model']}}"}}
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(agents_code)
            f.flush()
            agents_path = f.name

        prompt_content = "hello world"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as pf:
            pf.write(prompt_content)
            pf.flush()
            prompt_path = pf.name

        try:
            monkeypatch.setattr("sys.argv", [
                "antkeeper", "run",
                "--agents-file", agents_path,
                "--model", "opus",
                "echo", prompt_path,
            ])
            main()
            captured = capsys.readouterr()
            assert "prompt=hello world" in captured.out
            assert "model=opus" in captured.out
        finally:
            os.unlink(agents_path)
            os.unlink(prompt_path)

    def test_multiple_files_concatenated(self, monkeypatch, capsys):
        """Test that multiple positional files are concatenated into state['prompt']."""
        log_dir = tempfile.mkdtemp()
        agents_code = textwrap.dedent(f"""\
            from antkeeper.core.app import App
            from antkeeper.core.domain import State

            app = App(log_dir="{log_dir}")

            @app.handler
            def echo(runner, state: State) -> State:
                return {{**state, "result": f"prompt={{state['prompt']}}"}}
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(agents_code)
            f.flush()
            agents_path = f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f1:
            f1.write("hello\n")
            f1.flush()
            path1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f2:
            f2.write("world\n")
            f2.flush()
            path2 = f2.name

        try:
            monkeypatch.setattr("sys.argv", [
                "antkeeper", "run",
                "--agents-file", agents_path,
                "echo", path1, path2,
            ])
            main()
            captured = capsys.readouterr()
            assert "prompt=hello\\nworld\\n" in captured.out
        finally:
            os.unlink(agents_path)
            os.unlink(path1)
            os.unlink(path2)

    def test_stdin_read_as_prompt(self, monkeypatch, capsys):
        """Test that piped stdin content becomes state['prompt'] when no files provided."""
        log_dir = tempfile.mkdtemp()
        agents_code = textwrap.dedent(f"""\
            from antkeeper.core.app import App
            from antkeeper.core.domain import State

            app = App(log_dir="{log_dir}")

            @app.handler
            def echo(runner, state: State) -> State:
                return {{**state, "result": f"prompt={{state['prompt']}}"}}
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(agents_code)
            f.flush()
            agents_path = f.name

        try:
            monkeypatch.setattr("sys.stdin", io.StringIO("from stdin"))
            monkeypatch.setattr("sys.stdin.isatty", lambda: False)
            monkeypatch.setattr("sys.argv", [
                "antkeeper", "run",
                "--agents-file", agents_path,
                "echo",
            ])
            main()
            captured = capsys.readouterr()
            assert "prompt=from stdin" in captured.out
        finally:
            os.unlink(agents_path)

    def test_run_command_catches_workflow_failed_error(self, monkeypatch, capsys):
        """Test that CLI run catches WorkflowFailedError, prints to stderr, exits 1."""
        log_dir = tempfile.mkdtemp()
        agents_code = textwrap.dedent(f"""\
            from antkeeper.core.app import App
            from antkeeper.core.domain import State

            app = App(log_dir="{log_dir}")

            @app.handler
            def blow_up(runner, state: State) -> State:
                runner.fail("something went wrong")
                return state
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(agents_code)
            f.flush()
            agents_path = f.name

        try:
            monkeypatch.setattr("sys.stdin.isatty", lambda: True)
            monkeypatch.setattr("sys.argv", [
                "antkeeper", "run",
                "--agents-file", agents_path,
                "blow_up",
            ])
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "something went wrong" in captured.err
        finally:
            os.unlink(agents_path)
