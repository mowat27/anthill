---
description: Update codebase documentation
model: sonnet
argument-hint: [focus]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(*), WebFetch, WebSearch
---

# Document

Review and update the codebase's documentation

## Variables

FOCUS: Git commit(s), files, directories, experts etc. Default to whole system.

## Instructions

* Use standard python documentataion standards for python files
* Update experts by asking them to self-improve

## Workflow

* Find all python files in the focus area using the appropriate method (`git`, `ls` etc) but do not read them
* Spawn up to 5 **Documenter** agents (blocking Tasks, subagent_type: general-purpose). Each reads a batch of files, updates the python docs and returns a concise summary. Do NOT spawn it in the background.
* Ask the `design-expert` skill to "self improve"
* Update the readme with developer instructions to navigate the codebase - ask the design-expert skill about how it works

## Report

Bullet point summary of the changes made.  Include a list of all files changed including expertise documents owned by skills (`.claude/skills/*/expertise.yaml`)
