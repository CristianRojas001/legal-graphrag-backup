# PROMPT_CONTRACT

This file is intended to be pasted into Claude.md or used as the system contract for any optimizer agent.

## Primary objective
Follow the North Star and pass AUTOMATED_EVAL_RULES.

## Allowed changes
- Improve retrieval logic
- Improve prompt and formatting
- Improve ranking and chunk selection
- Improve abstention and clarifying questions
- Improve citation mapping and formatting
- Improve tests and harness code, but do not change expected behavior labels without human approval

## Forbidden behavior
- Do not reduce hallucinations by always refusing.
- Do not pass citation tests by attaching fake citations.
- Do not change the frozen eval set semantics to make failing tests pass.

## Required debug output (for each failing case)
- What violated which rule
- What sources were retrieved
- What change you propose
- How you will validate the fix
