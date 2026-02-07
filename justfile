default: check

check: ruff ty test

ruff:
  uv run ruff check

ty:
  uv run ty check

test:
  uv run pytest

server:
  uv run anthill server

check_api host="127.0.0.1" port="8000":
  curl -s -X POST http://{{host}}:{{port}}/webhook \
    -H "Content-Type: application/json" \
    -d '{"workflow_name": "healthcheck"}' | python3 -m json.tool

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
