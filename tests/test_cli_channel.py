import pytest

from anthill.channels.cli import CliChannel


class TestCliChannel:
    @pytest.mark.parametrize("initial_state,expected", [
        ({"k": "v"}, {"k": "v"}),
        (None, {}),
    ])
    def test_cli_channel_initial_state(self, initial_state, expected):
        channel = CliChannel("wf", initial_state)
        assert channel.initial_state == expected

    def test_cli_channel_workflow_name(self):
        channel = CliChannel("my_workflow")
        assert channel.workflow_name == "my_workflow"
        assert channel.type == "cli"
