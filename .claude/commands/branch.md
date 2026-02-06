---
description: Create a feature branch for a plan file
model: Haiku
argument-hint: [plan-file]
allowed-tools: Read, Glob, Grep, Bash(*)
---

# Create Feature Branch

Read the plan file and create a git branch using the slug for the plan.

If no slug found then create one as a 1-3 word summary of the planned objective; words separated by `-`.

Make the result consistent with the name of the plan. e.g. `specs/feature-state-refactor.md` -> `feat/state-refactor`.

If no plan file provided look for a recent, preferrably not committed, one in the codebase.

If you can't find one then STOP.  It's OK not to know.

## Branch Naming

Format: `type/slug` e.g. `feat/add-button`, `chore/delete-unused-files`

Types: feat, bugfix, chore, docs etc
