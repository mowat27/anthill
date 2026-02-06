---
description: Design expert skill. Use when asked a question about the design (schema, data flows, core functions etc), asked to comment on a design or asked to self-improve design expertise.
model: Opus
argument-hint: []
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(*), WebFetch, WebSearch
---

# Design Expert

Remember and apply design expertise to planning and coding tasks

## Variables

ARGUMENTS: $ARGUMENTS

## Instructions

* Read `ARGUMENTS` and classify the request as `REQUEST_TYPE` as follows:
  - `question` - task requires answering a question about the design of the system
  - `self-improve` - task requires updating your `EXPERTISE` based on the codebase
* User may ask for multiple categories - e.g. "design and then self-improve". In this case you should try to meet the user's request but consider using subagents to prevent context bloat and/or improve performance.

## Workflow

Based on `REQUEST_TYPE`:

when `question`:
  - load `question.md` from the skill directory
when `self-improve`:
  - load `self-improve.md` from the skill directory
else:
  - FAIL - explain why you could not process the request
  - It's OK to not try an fulfill an ambiguous or invalid request

## Relevant Files

See files in the skill's directory

## Report

Defer to the prompt loaded or explain why the request could not be processed.




