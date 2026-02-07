default: check

check: ruff ty test

ruff:
  uv run ruff check

ty:
  uv run ty check

test:
  uv run pytest

sdlc prompt model="opus":
  #!/usr/bin/env bash
  if [ -f "{{prompt}}" ]; then
    uv run anthill run sdlc --model {{model}} --prompt-file "{{prompt}}"
  else
    uv run anthill run sdlc --model {{model}} --prompt "{{prompt}}"
  fi

sdlc_iso prompt model="opus":
  #!/usr/bin/env bash
  if [ -f "{{prompt}}" ]; then
    uv run anthill run sdlc_iso --model {{model}} --prompt-file "{{prompt}}"
  else
    uv run anthill run sdlc_iso --model {{model}} --prompt "{{prompt}}"
  fi
