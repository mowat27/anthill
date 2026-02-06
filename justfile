default: check

check: ruff ty test

ruff:
  uv run ruff check

ty:
  uv run ty check

test:
  uv run pytest
