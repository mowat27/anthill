"""Tests for extract_json helper."""

import pytest

from antkeeper.helpers.json import extract_json


def test_clean_json():
    """Test extraction of clean JSON object without surrounding text."""
    text = '{"spec_file": "specs/foo.md", "slug": "foo"}'
    result = extract_json(text)
    assert result == {"spec_file": "specs/foo.md", "slug": "foo"}


def test_markdown_fenced_json():
    """Test extraction of JSON from markdown code fence."""
    text = '```json\n{"spec_file": "specs/bar.md", "slug": "bar"}\n```'
    result = extract_json(text)
    assert result == {"spec_file": "specs/bar.md", "slug": "bar"}


def test_prose_surrounding_json():
    """Test extraction of JSON object embedded in prose text."""
    text = 'Here is the result:\n{"spec_file": "specs/baz.md", "slug": "baz"}\nDone.'
    result = extract_json(text)
    assert result == {"spec_file": "specs/baz.md", "slug": "baz"}


def test_no_braces_raises_value_error():
    """Test that text without JSON braces raises ValueError."""
    with pytest.raises(ValueError, match="No JSON object found"):
        extract_json("no json here")


def test_invalid_json_raises_value_error():
    """Test that malformed JSON syntax raises ValueError."""
    with pytest.raises(ValueError, match="Invalid JSON"):
        extract_json("some text { not: valid json } more text")


def test_empty_string_raises_value_error():
    """Test that empty string raises ValueError."""
    with pytest.raises(ValueError, match="No JSON object found"):
        extract_json("")


def test_nested_json_objects():
    """Test extraction of nested JSON object structures."""
    text = '{"outer": {"inner": "value"}, "key": "val"}'
    result = extract_json(text)
    assert result == {"outer": {"inner": "value"}, "key": "val"}
