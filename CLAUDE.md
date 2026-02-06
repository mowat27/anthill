# Testing Rules

- **Test the framework, not the app.** Import from the library (`anthill.core.*`). If a test needs handlers, define them in the test suite — they exist to exercise the core machinery, not to replicate production logic.
- **Each test owns its setup.** Build the `App`, register handlers, and wire the `Mission` inside the test. No shared global state. This makes it obvious what each test is actually exercising.
- **Replace I/O at the boundary.** Swap sources/sinks that do I/O (print, stderr) with capturing doubles that collect into lists. Match the interface via duck typing.
- **One test per code path.** If two tests traverse the same core path with different data, they're the same test. A single-handler workflow is one path regardless of what the handler computes.
- **Run:** `uv run -m pytest tests/ -v`
