"""JSON extraction from LLM responses."""

import json as _json


def extract_json(text: str) -> dict:
    """Extract and parse a JSON object from text that may contain markdown fencing or prose.

    Finds the first '{' and last '}' in the text, extracts the substring between
    them (inclusive), and parses it as JSON.

    Args:
        text: Raw text potentially containing a JSON object wrapped in
              markdown code fences or surrounding prose.

    Returns:
        The parsed JSON object as a dictionary.

    Raises:
        ValueError: If no braces are found or the extracted text is not valid JSON.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"No JSON object found in text: {text!r}")
    candidate = text[start : end + 1]
    try:
        return _json.loads(candidate)
    except _json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}") from e
