"""State persistence tests.

Tests for JSON state file creation and content in Runner and run_workflow.
"""

import glob
import json
import os
import re

from antkeeper.core.app import run_workflow
from antkeeper.core.domain import State


class TestRunnerStatePersistence:
    """Test suite for state persistence functionality in Runner."""

    def test_runner_creates_state_directory(self, app, runner_factory):
        """Test that Runner creates the state directory during initialization."""
        runner, _ = runner_factory(app, "test")
        assert os.path.isdir(app.state_dir)

    def test_runner_creates_state_file_on_run(self, app, runner_factory):
        """Test that Runner creates a state file with correct naming format."""
        @app.handler
        def noop(runner, state: State) -> State:
            return state

        runner, _ = runner_factory(app, "noop")
        runner.run()
        files = glob.glob(os.path.join(app.state_dir, "*.json"))
        assert len(files) == 1
        filename = os.path.basename(files[0])
        assert re.match(r"^\d{14}-[a-f0-9]{8}\.json$", filename)
        assert runner.id in filename

    def test_state_file_contains_initial_state_keys(self, app, runner_factory):
        """Test that persisted state file includes run_id and workflow_name."""
        @app.handler
        def noop(runner, state: State) -> State:
            return state

        runner, _ = runner_factory(app, "noop")
        runner.run()
        files = glob.glob(os.path.join(app.state_dir, "*.json"))
        with open(files[0]) as f:
            data = json.load(f)
        assert "run_id" in data
        assert "workflow_name" in data

    def test_state_file_reflects_handler_changes(self, app, runner_factory):
        """Test that state modifications by handlers are persisted to the file."""
        @app.handler
        def add_key(runner, state: State) -> State:
            return {**state, "added": True}

        runner, _ = runner_factory(app, "add_key")
        runner.run()
        files = glob.glob(os.path.join(app.state_dir, "*.json"))
        with open(files[0]) as f:
            data = json.load(f)
        assert data["added"] is True

    def test_state_file_updated_after_each_run_workflow_step(self, app, runner_factory):
        """Test that run_workflow persists state after each step completes."""
        @app.handler
        def step1(runner, state: State) -> State:
            return {**state, "step1": True}

        @app.handler
        def step2(runner, state: State) -> State:
            # Read the persisted state to verify step1 was already written
            with open(runner._state_path) as f:
                persisted = json.load(f)
            assert persisted["step1"] is True
            return {**state, "step2": True}

        @app.handler
        def pipeline(runner, state: State) -> State:
            return run_workflow(runner, state, [step1, step2])

        runner, _ = runner_factory(app, "pipeline")
        runner.run()

    def test_state_file_name_matches_log_file_name(self, app, runner_factory):
        """Test that state file and log file share the same base filename."""
        @app.handler
        def noop(runner, state: State) -> State:
            return state

        runner, _ = runner_factory(app, "noop")
        runner.run()
        log_files = glob.glob(os.path.join(app.log_dir, "*.log"))
        state_files = glob.glob(os.path.join(app.state_dir, "*.json"))
        log_stem = os.path.splitext(os.path.basename(log_files[0]))[0]
        state_stem = os.path.splitext(os.path.basename(state_files[0]))[0]
        assert log_stem == state_stem
