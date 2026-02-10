# fix: Validate Slack env vars on /slack_event

- Return HTTP 422 from `/slack_event` when `SLACK_BOT_TOKEN` and/or `SLACK_BOT_USER_ID` are missing or empty
- Preserve `url_verification` handshake regardless of env var state
- Include diagnostic message naming which variables are missing

## Solution Design

### REST Changes

- `POST /slack_event` -- returns `422 Unprocessable Entity` with `{"detail": "Missing required environment variables: SLACK_BOT_TOKEN, SLACK_BOT_USER_ID"}` (listing only the missing vars) when `SLACK_BOT_TOKEN` and/or `SLACK_BOT_USER_ID` are absent or empty string. `url_verification` requests are exempt and pass through to the processor unchanged.

## Relevant Files

- `src/antkeeper/server.py` -- contains the `/slack_event` route handler where the env var guard will be added (lines 46-61)
- `src/antkeeper/http/slack_events.py` -- `SlackEventProcessor` class; NOT modified, but referenced for understanding the existing `url_verification` handling and env var reads
- `tests/test_slack_server.py` -- existing Slack endpoint tests; new validation tests will be added here

## Workflow

### Step 1: Add env var validation to the route handler

- In `src/antkeeper/server.py`, modify the `slack_event` route handler (inside `create_app()`)
- After `body = await request.json()`, add a guard: if `body.get("type") != "url_verification"`, check env vars
- Build a list of missing vars by checking `os.environ.get("SLACK_BOT_TOKEN", "")` and `os.environ.get("SLACK_BOT_USER_ID", "")` for falsy values
- If the list is non-empty, `raise HTTPException(status_code=422, detail=f"Missing required environment variables: {', '.join(missing)}")`
- Otherwise, delegate to `await slack.handle_event(body)` as before
- `HTTPException` is already imported via the `from fastapi import ...` line; add it to that import if not already present

### Step 2: Add tests for env var validation

- In `tests/test_slack_server.py`, add a `slack_client_no_env` fixture that creates a `TestClient` without `SLACK_BOT_TOKEN` or `SLACK_BOT_USER_ID` in the environment (only set `SLACK_COOLDOWN_SECONDS`). Explicitly pop both Slack vars from `os.environ` after starting the env patch, to handle cases where they are set in the real environment or loaded by `dotenv.load_dotenv()` in `create_app()`
- Add four tests (see Testing Strategy below)

### Step 3: Run validation commands

- Run all tests, typechecks, and lint with `just`
- Verify zero errors, zero warnings

## Testing Strategy

### Unit Tests

Add tests to `TestSlackEventEndpoint` in `tests/test_slack_server.py` using a new `slack_client_no_env` fixture:

1. `test_missing_both_env_vars_returns_422` -- neither var set, send an `event_callback` event, assert status 422 and `detail` contains both var names
2. `test_missing_slack_bot_token_returns_422` -- only `SLACK_BOT_USER_ID` set via `patch.dict`, send event, assert 422 and `detail` contains `SLACK_BOT_TOKEN` but not `SLACK_BOT_USER_ID`
3. `test_missing_slack_bot_user_id_returns_422` -- only `SLACK_BOT_TOKEN` set via `patch.dict`, send event, assert 422 and `detail` contains `SLACK_BOT_USER_ID` but not `SLACK_BOT_TOKEN`
4. `test_url_verification_works_without_env_vars` -- neither var set, send `url_verification`, assert status 200 and challenge returned

### Edge Cases

- Empty string value for env var treated as missing (consistent with existing `os.environ.get(..., "")` pattern in `SlackEventProcessor`)
- `url_verification` passes through even with no env vars configured (Slack sends this during initial app setup before tokens may exist)

## Acceptance Criteria

- `POST /slack_event` with a non-`url_verification` body returns HTTP 422 when `SLACK_BOT_TOKEN` is missing/empty
- `POST /slack_event` with a non-`url_verification` body returns HTTP 422 when `SLACK_BOT_USER_ID` is missing/empty
- `POST /slack_event` with a non-`url_verification` body returns HTTP 422 when both are missing, and the detail message names both
- `POST /slack_event` with `url_verification` body returns HTTP 200 with challenge regardless of env var state
- `POST /slack_event` with both env vars set continues to work as before (existing tests pass)
- Uses `HTTPException` consistent with the webhook endpoint pattern
- No changes to `SlackEventProcessor` or any core module

### Validation Commands

```bash
just
```

IMPORTANT: If any of the checks above fail you must investigate and fix the error. It is not acceptable to simply explain away the problem. You must reach zero errors, zero warnings before you move on. This includes pre-existing issues and other issues that you don't think are related to this bugfix.

## Notes

- The `url_verification` check in `SlackEventProcessor.handle_event()` (line 139) becomes unreachable for `url_verification` events since the route handler now returns early for that case. This is acceptable -- removing it from the processor would create fragile coupling where the processor depends on the caller always pre-filtering.
- The `HTTPException` approach produces `{"detail": "..."}` which matches the webhook endpoint's error response shape.
- 422 was chosen per the change request. While 503 could be argued as more semantically correct for server misconfiguration, 422 communicates "I cannot process this entity given the current configuration" and is what was specified.

## Report

- **Files changed**: `src/antkeeper/server.py` (env var guard in route handler), `tests/test_slack_server.py` (4 new tests + fixture)
- **Tests added**: 4 new tests covering both-missing, token-missing, user-id-missing, and url-verification-passthrough
- **Validations**: `just` (lint + typecheck + test)
