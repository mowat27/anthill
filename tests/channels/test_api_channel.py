"""Tests for the API channel implementation.

Tests the ApiChannel's type, state handling, and output reporting capabilities.
"""

import pytest

from anthill.channels.api import ApiChannel


class TestApiChannel:
    """Test suite for ApiChannel class."""
    def test_api_channel_type(self):
        """Test that ApiChannel returns correct channel type."""
        channel = ApiChannel("wf")
        assert channel.type == "api"

    @pytest.mark.parametrize("initial_state,expected", [
        ({"k": "v"}, {"k": "v"}),
        (None, {}),
    ])
    def test_api_channel_initial_state(self, initial_state, expected):
        """Test that ApiChannel handles initial state correctly, defaulting to empty dict."""
        channel = ApiChannel("wf", initial_state)
        assert channel.initial_state == expected

    def test_report_progress_prints_to_stdout(self, capsys):
        """Test that progress messages are formatted and printed to stdout."""
        channel = ApiChannel("my_wf")
        channel.report_progress("abc123", "step done")
        captured = capsys.readouterr()
        assert captured.out == "[my_wf, abc123] step done\n"

    def test_report_error_prints_to_stderr(self, capsys):
        """Test that error messages are formatted and printed to stderr."""
        channel = ApiChannel("my_wf")
        channel.report_error("abc123", "something broke")
        captured = capsys.readouterr()
        assert captured.err == "[my_wf, abc123] something broke\n"
