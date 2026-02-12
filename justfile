default: check

check: ruff ty test

ruff:
  uv run ruff check

ty:
  uv run ty check

test:
  uv run pytest

server:
  uv run antkeeper server

check_api host="127.0.0.1" port="8000":
  curl -s -X POST http://{{host}}:{{port}}/webhook \
    -H "Content-Type: application/json" \
    -d '{"workflow_name": "healthcheck"}' | python3 -m json.tool

sdlc prompt model="opus":
  #!/usr/bin/env bash
  if [ -f "{{prompt}}" ]; then
    uv run antkeeper run --model {{model}} sdlc "{{prompt}}"
  else
    echo "{{prompt}}" | uv run antkeeper run --model {{model}} sdlc
  fi

sdlc_iso prompt model="opus":
  #!/usr/bin/env bash
  if [ -f "{{prompt}}" ]; then
    uv run antkeeper run --model {{model}} sdlc_iso "{{prompt}}"
  else
    echo "{{prompt}}" | uv run antkeeper run --model {{model}} sdlc_iso
  fi
