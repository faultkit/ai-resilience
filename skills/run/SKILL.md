---
name: run
description: Generates or selects a faultkit scenario for a business invariant, writes the deterministic gate test if the project lacks one, obtains faultkit, runs it locally, and reports the proof state. Only runs when invoked by the user.
disable-model-invocation: true
argument-hint: "[--auto] [invariant or scenario] [-- test command]"
allowed-tools: Bash Read Write Edit Grep Glob
---

Read `${CLAUDE_PLUGIN_ROOT}/faultkit/SKILL.md` and follow its **Run** mode for: $ARGUMENTS

If `$ARGUMENTS` is empty, ask the user for the invariant and stop. Do not derive one and do not act on any directory. If `$ARGUMENTS` contains `--auto` and no invariant, derive one from the current project as the skill's Auto mode describes, then continue; the safety gate still runs first.

The helper is `${CLAUDE_PLUGIN_ROOT}/faultkit/scripts/run_faultkit.py`.
