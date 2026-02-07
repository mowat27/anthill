"""Logging tests.

Tests for file-based logging in App and Runner: configuration, file creation,
log format, content, step logging, error logging, and stdout isolation.
"""

import glob
import os
import re

import pytest

from anthill.core.app import App, run_workflow
from anthill.core.domain import State


class TestAppConfiguration:
    def test_app_log_dir_defaults_to_agents_logs(self):
        """Test that App().log_dir defaults to 'agents/logs/'."""
        assert App().log_dir == "agents/logs/"

    def test_app_log_dir_accepts_custom_value(self):
        """Test that App(log_dir=...) stores the custom value."""
        assert App(log_dir="/tmp/custom").log_dir == "/tmp/custom"


class TestRunnerLogFileCreation:
    def test_runner_creates_log_directory(self, app, runner_factory):
        """Test that Runner creates the log directory if it doesn't exist."""
        runner, _ = runner_factory(app, "test")
        assert os.path.isdir(app.log_dir)

    def test_runner_creates_log_file_with_correct_name_format(self, app, runner_factory):
        """Test log file naming: {YYYYMMDDhhmmss}-{run_id}.log."""
        runner, _ = runner_factory(app, "test")
        logs = glob.glob(os.path.join(app.log_dir, "*.log"))
        assert len(logs) == 1
        filename = os.path.basename(logs[0])
        assert re.match(r"^\d{14}-[a-f0-9]{8}\.log$", filename)
        assert runner.id in filename


class TestLogContentAndFormat:
    def test_log_format_matches_expected_pattern(self, app, runner_factory):
        """Test that log lines match the expected timestamp/level/name format."""
        runner, _ = runner_factory(app, "test")
        log_file = glob.glob(os.path.join(app.log_dir, "*.log"))[0]
        with open(log_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    assert re.match(
                        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} \[\w+\] anthill\..+ - .+",
                        line,
                    )

    def test_runner_log_file_contains_initialization_message(self, app, runner_factory):
        """Test that log file contains INFO entry with runner ID."""
        runner, _ = runner_factory(app, "test")
        log_file = glob.glob(os.path.join(app.log_dir, "*.log"))[0]
        content = open(log_file).read()
        assert "[INFO]" in content
        assert runner.id in content

    def test_runner_logs_workflow_start_and_end(self, app, runner_factory):
        """Test that run() logs workflow start and completion at INFO."""
        @app.handler
        def noop(runner, state: State) -> State:
            return state

        runner, _ = runner_factory(app, "noop")
        runner.run()
        log_file = glob.glob(os.path.join(app.log_dir, "*.log"))[0]
        content = open(log_file).read()
        assert "Workflow started: noop" in content
        assert "Workflow completed: noop" in content

    def test_runner_logs_initial_and_final_state_at_debug(self, app, runner_factory):
        """Test that run() logs state contents at DEBUG level."""
        @app.handler
        def noop(runner, state: State) -> State:
            return {**state, "added": True}

        runner, _ = runner_factory(app, "noop", {"key": "val"})
        runner.run()
        log_file = glob.glob(os.path.join(app.log_dir, "*.log"))[0]
        content = open(log_file).read()
        assert "[DEBUG]" in content
        assert "Initial state:" in content
        assert "Final state:" in content


class TestStepLogging:
    def test_run_workflow_logs_steps(self, app, runner_factory):
        """Test that run_workflow logs INFO for each step and DEBUG for completion."""
        @app.handler
        def step_a(runner, state: State) -> State:
            return {**state, "a": True}

        @app.handler
        def step_b(runner, state: State) -> State:
            return {**state, "b": True}

        @app.handler
        def pipeline(runner, state: State) -> State:
            return run_workflow(runner, state, [step_a, step_b])

        runner, _ = runner_factory(app, "pipeline")
        runner.run()
        log_file = glob.glob(os.path.join(app.log_dir, "*.log"))[0]
        content = open(log_file).read()
        assert "Executing step: step_a" in content
        assert "Executing step: step_b" in content
        assert "Step completed: step_a" in content
        assert "Step completed: step_b" in content


class TestErrorLogging:
    def test_runner_logs_error_at_error_level(self, app, runner_factory):
        """Test that exceptions in handlers produce ERROR log entries."""
        @app.handler
        def explode(runner, state: State) -> State:
            raise RuntimeError("kaboom")

        runner, _ = runner_factory(app, "explode")
        with pytest.raises(RuntimeError):
            runner.run()
        log_file = glob.glob(os.path.join(app.log_dir, "*.log"))[0]
        content = open(log_file).read()
        assert "[ERROR]" in content
        assert "kaboom" in content


class TestLoggerIsolation:
    def test_anthill_logger_does_not_leak_to_stdout(self, app, runner_factory, capsys):
        """Test that log output does not appear in stdout/stderr."""
        @app.handler
        def noop(runner, state: State) -> State:
            runner.logger.info("should not appear on console")
            return state

        runner, _ = runner_factory(app, "noop")
        runner.run()
        captured = capsys.readouterr()
        assert "should not appear on console" not in captured.out
        assert "should not appear on console" not in captured.err
