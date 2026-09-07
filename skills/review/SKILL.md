---
name: review
description: Use when asked to assess, review, audit, or explain the resilience of an AI or LLM workflow, agent, or tool loop; when someone mentions silent failures, business invariants, what happens when the model is wrong, retries or fallbacks hiding outages, stale or partial tool data, truncated output, or wants a plan before hardening. Read-only.
argument-hint: "[--auto] [path or description of the workflow]"
---

Read `${CLAUDE_PLUGIN_ROOT}/faultkit/SKILL.md` and follow its **Review** mode for: $ARGUMENTS

Do not edit code in this mode. End by showing the report and asking whether to run faultkit against the proof plan, then wait for the answer.

If `$ARGUMENTS` contains `--auto`, do not ask: continue into Run at once. The safety gate still runs first.
