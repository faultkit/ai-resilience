---
name: harden
description: Use when asked to make an AI or LLM workflow resilient, add a guard, policy check, or safety boundary around an irreversible action, prevent an agent from ever doing something, or fix a finding from a resilience review.
argument-hint: "[--auto] [invariant or finding] [path]"
---

Read `${CLAUDE_PLUGIN_ROOT}/faultkit/SKILL.md` and follow its **Harden** mode for: $ARGUMENTS

End by showing the change and the test, then ask whether to run faultkit to prove it, and wait for the answer.

If `$ARGUMENTS` contains `--auto`, do not ask: continue into Run at once. The safety gate still runs first.
