default: check

check: ruff ty test

ruff:
  uv run ruff check

ty:
  uv run ty check

test:
  uv run pytest

sdlc prompt model="opus":
  uv run anthill run sdlc --model {{model}} --prompt "{{prompt}}"
