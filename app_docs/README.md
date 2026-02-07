# Application Documentation Index

This directory contains policy and pattern documentation for the Anthill workflow framework.

## Files

- **testing_policy.md** - Testing approach, fixture management, and test structure rules. Covers how to write tests for the framework core, not application handlers.

- **instrumentation.md** - Progress reporting, error handling, run identification, and state persistence patterns. Explains the Channel interface for I/O and how handlers communicate status.

## Usage

These docs describe **how the framework works** and **policies for extending it**, not how to use it as a library. For usage documentation, see the main [README.md](../README.md).

If you're writing framework code (in `src/anthill/core/`, `src/anthill/channels/`, or `src/anthill/llm/`), read these docs.

If you're writing application handlers, see the "Writing Handlers" section in the main README.
