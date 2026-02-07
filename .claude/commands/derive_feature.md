---
description: Derive feature type and slug from a prompt
model: Haiku
argument-hint: [feature-description]
allowed-tools:
---

# Derive Feature Metadata

Given the feature description below, determine the feature type and generate a kebab-case slug.

## Feature Description

$ARGUMENTS

## Instructions

1. Determine the feature type from: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`
2. Generate a kebab-case slug (1-3 words) summarizing the feature (e.g., `add-worktree-support`, `fix-login-bug`)

Return ONLY a JSON object with no other text:

```json
{"feature_type": "<type>", "slug": "<slug>"}
```
