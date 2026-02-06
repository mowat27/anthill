---
description: Builds a feature based on a spec/plan
model: opus
argument-hint: [plan-file]
allowed-tools: Read, Write, Edit, Bash(*), Glob, Grep, Task, TodoWrite
---

# Implement Plan

Follow the `Instructions` to implement the `Plan` then `Report` the completed work.

## Variables

* PLAN_FILE: $1

**Variable Resolution:**
- If `PLAN_FILE` is empty, unset, or literally `$1`, search for a recent plan file in `specs/` (preferably uncommitted)
- If no plan file can be found, STOP and ask the user for the plan file path

### Additional Prompts

$ARGUMENTS

## Instructions
- Read the PLAN_FILE and `Additional Prompts`, think hard about the plan and implement the plan.

## Plan
$ARGUMENTS

## Report
- Summarize the work you've just done in a concise bullet point list.
- Report the files and total lines changed with `git diff --stat`
