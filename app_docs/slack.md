# Slack Integration

Anthill integrates with Slack via the Events API. When a user @mentions the bot in a channel, Anthill collects the message (and any follow-up edits or thread replies within a cooldown window), then dispatches a workflow and posts results back to the originating thread.

## Slack App Configuration

### Required Bot Token Scopes

| Scope | Purpose |
|---|---|
| `app_mentions:read` | Receive events when the bot is @mentioned. |
| `channels:history` | Read messages in public channels the bot is in. |
| `chat:write` | Post messages and replies to channels. |
| `reactions:write` | Add thumbsup reaction to acknowledge received messages. |

### Event Subscriptions

Enable **Event Subscriptions** in the Slack app settings. Set the Request URL to:

```
https://<your-host>/slack_event
```

Subscribe to the following bot events:

- `app_mention` -- triggered when a user @mentions the bot.
- `message.channels` -- triggered on messages in public channels the bot is in (needed for edits, deletes, and thread replies).

### URL Verification

Slack sends a `url_verification` challenge when you first set the Request URL. The `/slack_event` endpoint handles this automatically by returning `{"challenge": "<value>"}`.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | (empty string) | Bot User OAuth Token from Slack app settings (starts with `xoxb-`). Used for all Slack API calls. |
| `SLACK_BOT_USER_ID` | (empty string) | The Slack user ID of the bot (e.g. `U07ABC123`). Used to detect @mentions in message text. Find this under the bot's profile in Slack. |
| `SLACK_COOLDOWN_SECONDS` | `30` | Number of seconds to wait after the last interaction before dispatching the workflow. Resets on edits and thread replies. |

### .env File Support

The server calls `dotenv.load_dotenv()` at startup (in `create_app()`), so all three variables can be placed in a `.env` file in the working directory:

```
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_BOT_USER_ID=U07ABC123
SLACK_COOLDOWN_SECONDS=30
```

## Runtime Behaviour Flow

1. **User @mentions the bot** in a channel message, e.g. `@AntBot review fix the login bug`.
2. The `/slack_event` endpoint receives the event from Slack.
3. **Bot self-filter**: if the event has a `bot_id` field, it is ignored (prevents the bot from responding to its own messages).
4. **Thumbsup reaction**: the bot adds a thumbsup reaction to the message to acknowledge receipt.
5. **Cooldown timer starts**: a debounce timer of `SLACK_COOLDOWN_SECONDS` begins.
6. **Edits and thread replies accumulate**: if the user edits the original message or posts thread replies before the timer fires, the timer resets and the new content is folded into the pending message.
7. **Timer fires**: once the cooldown elapses with no further interaction:
   - The bot posts "Processing your request..." in the thread.
   - The workflow name is looked up in the App's handler registry.
   - A `SlackChannel` and `Runner` are created.
   - The workflow executes via `asyncio.to_thread(_run_workflow, runner)`.
8. **Workflow results** are posted back to the same thread via the `SlackChannel`.

## Workflow Name Extraction

The workflow name is the first word of the message text after stripping the @mention:

```
@AntBot review fix the login bug
        ^^^^^^
        workflow_name = "review"
```

The @mention prefix (e.g. `<@U07ABC123>`) is stripped using a regex. The remaining text is split on whitespace and the first token becomes the workflow name. The full stripped text (including the workflow name) is passed as the `prompt` field in the initial state.

## Event Routing

The `/slack_event` endpoint processes events in the following order:

| Step | Condition | Action |
|---|---|---|
| 1. URL verification | `body.type == "url_verification"` | Return `{"challenge": body.challenge}`. |
| 2. Empty event | No `event` field in body | Return `{"ok": true}`. |
| 3. Bot self-filter | `event.bot_id` is present | Return `{"ok": true}`. |
| 4. Thread reply | `event.thread_ts` exists and differs from `event.ts` | If the parent message is pending: cancel timer, append reply text and files, restart timer, add thumbsup. |
| 5. Message edit | `event.subtype == "message_changed"` | If the original message is pending: cancel timer, replace text with edited content, restart timer. |
| 6. Message delete | `event.subtype == "message_deleted"` | If the deleted message is pending: cancel timer, remove from pending store. |
| 7. Bot mention | Event type is `app_mention` or `message`, subtype is `None` or `file_share`, and text contains `<@BOT_USER_ID>` | Create `PendingMessage`, add thumbsup, start cooldown timer. |
| 8. All other events | Anything else | Return `{"ok": true}`. |

Thread replies and message edits are checked before bot mentions. This ensures that follow-up interactions on an already-pending message reset the timer rather than creating a duplicate entry.

## Debounce Mechanism

The debounce system prevents premature dispatch when users are still composing their request across multiple messages or edits.

### PendingMessage

Each tracked message is stored as a `PendingMessage` dataclass:

| Field | Type | Description |
|---|---|---|
| `channel_id` | `str` | Slack channel where the message was posted. |
| `ts` | `str` | Slack message timestamp (used as unique identifier). |
| `user` | `str` | Slack user ID of the message author. |
| `text` | `str` | Accumulated message text. Updated on edits; appended on thread replies. |
| `files` | `list[dict]` | File attachments from the original message and thread replies. |
| `workflow_name` | `str` | Extracted workflow name (first word after stripping @mention). |
| `timer_task` | `asyncio.Task or None` | The active cooldown timer task. |

Pending messages are keyed by `(channel_id, ts)` in an in-memory dictionary.

### Timer Reset Behaviour

- **On new @mention**: a new `PendingMessage` is created and a timer task is started.
- **On thread reply** to a pending message: the existing timer is cancelled, reply text is appended (`\n` separator), files are extended, and a new timer is started.
- **On message edit** of a pending message: the existing timer is cancelled, text is replaced with the edited content (re-stripped of @mention), and a new timer is started.
- **On message delete** of a pending message: the timer is cancelled and the entry is removed. No workflow is dispatched.

The default cooldown is 30 seconds, configurable via `SLACK_COOLDOWN_SECONDS`.

## SlackChannel

`SlackChannel` (in `src/anthill/channels/slack.py`) is the I/O boundary that posts workflow output back to the originating Slack thread.

### Construction

When the debounce timer fires, a `SlackChannel` is created with:

```python
SlackChannel(
    workflow_name=entry.workflow_name,
    initial_state={"prompt": entry.text, "slack_user": entry.user},
    slack_token=token,
    channel_id=entry.channel_id,
    thread_ts=entry.ts,
)
```

If the message included file attachments, `initial_state["files"]` is also set.

### How It Posts to Slack

`SlackChannel` uses **synchronous** `httpx.Client` to call the Slack `chat.postMessage` API. This is intentional: handler code runs in a background thread (via `asyncio.to_thread`), so synchronous HTTP is appropriate and avoids mixing sync/async concerns.

The `_post_to_thread()` method posts to the channel and thread identified at construction time. Both `report_progress()` and `report_error()` delegate to this method, formatting messages with the workflow name and run ID:

- Progress: `[workflow_name, run_id] message`
- Error: `[workflow_name, run_id] [ERROR] message`

### Error Handling

HTTP failures in `_post_to_thread()` are caught (`httpx.HTTPError`) and logged but not propagated. This prevents a transient Slack API failure from crashing the running workflow.

## Error Handling

| Scenario | Behaviour |
|---|---|
| Unknown workflow name | After the timer fires, the bot posts `"Unknown workflow: <name>"` to the thread. No Runner is created. |
| HTTP failure posting to Slack (in SlackChannel) | Caught as `httpx.HTTPError`, logged via `logger.error()`, not propagated to the workflow. |
| `WorkflowFailedError` during execution | Caught silently by `_run_workflow()`. This is the standard signal for a workflow step failure. |
| Unexpected exception during execution | Printed to stderr by `_run_workflow()`. Does not crash the server. |
