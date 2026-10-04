---
name: skill-template
description: >-
  Does one specific task and produces a concrete result, stated in the third
  person. Use when the user asks for that task, names the tool or file type it
  covers, or describes the situation it solves. Do not use for adjacent tasks a
  near-miss prompt might confuse with this one.
license: MIT
metadata:
  author: ddlaws0n
  version: "0.1.0"
---

# Skill template

Copy this directory to `skills/<verb>-<object>/`, rename every `skill-template`, and replace each section's guidance with the skill's own instructions. Delete sections the skill does not need, except Workflow.

## Workflow

1. Inspect the user's context before acting.
2. Do the task in the smallest number of verifiable steps.
3. Validate the result with a concrete check.
4. Report the result using the Output section.

## Gotchas

- Facts an agent would otherwise get wrong: non-obvious defaults, traps, and safety limits.

## Output

Describe the final response: what it contains and in which order.
