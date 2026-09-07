# AI Resilience skill

A skill for coding agents that protects the business value of an AI workflow
when models, streams, tools, retrieval, networks, or state fail. It starts from
what must never happen, not from what the API returned.

```text
business value -> unacceptable outcome -> invariant -> fault -> recovery -> proof
```

Instead of asking whether a call succeeded, the skill asks whether the business
invariant still holds: a refund cannot exceed the policy limit; retrying cannot
charge twice; a partial stream cannot become a final decision; stale evidence
cannot authorize a regulated action; failure becomes an explicit degraded state,
never fabricated success. The method is tool-agnostic. faultkit is the optional
way to prove the result.

## Modes

| Mode | When | What it does |
| --- | --- | --- |
| Review | Assess, explain, or plan | Maps value, boundaries, silent failures, invariants, and residual risk. Changes no code. |
| Harden | Build or fix a workflow | Adds the smallest deterministic guard at the action boundary and the test that locks it. |
| Run | Explicitly requested fault injection | Selects or generates a faultkit scenario, writes the gate test if missing, obtains faultkit, runs it locally, reports the proof state. |

Run is opt-in. Ordinary use of the skill neither installs tools nor
injects faults. Review and Harden end by asking whether to run it and wait
for the answer. Add `--auto` to any command to run the whole chain without
stopping at the questions; the safety gate still runs first and a production
signal still stops the chain.

## Install in Claude Code

```text
/plugin marketplace add faultkit/skills
/plugin install faultkit@faultkit
```

Then `/faultkit:review`, `/faultkit:harden`, and
`/faultkit:run` are available. The first two also trigger on their
own when a conversation turns to resilience; `run` runs only when you
invoke it.

## Install for other agents

Copy the `faultkit/` directory into your repository as
`.agents/skills/faultkit/` and add one line to your `AGENTS.md`:

```markdown
For AI workflow changes, read `.agents/skills/faultkit/SKILL.md` and follow it.
```

This repository is itself a working installation.

## Example prompts

```text
Use the AI Resilience skill to review this refund agent. Identify the business
value, unacceptable outcomes, silent failures, deterministic invariants, and the
smallest recovery design. Do not change code.
```

```text
Use the AI Resilience skill to harden this shipment-planning workflow. A partial
model stream must never dispatch a route. Add deterministic tests.
```

```text
/faultkit:run a paid invoice is never sent to collections -- pytest -q
```

## The proof condition

A run counts as evidence only when

```text
faults fired > 0 AND business invariant held
```

A run in which no fault fired is invalid evidence even if the target exited
successfully; a green run that injected nothing is the most dangerous result.
The helper `faultkit/scripts/run_faultkit.py` asks faultkit for a JSON
report, counts fired events, and exits with faultkit's own code so shells and
CI can branch on it. It obtains faultkit from an explicit path, `$FAULTKIT`,
`PATH`, a local source tree, or a checksum-verified download of a pinned
release, in that order. It never resolves "latest".

Runs stay in local, test, or explicitly authorized environments, with real
irreversible side effects replaced by fakes.

## Layout

- `faultkit/SKILL.md`: the skill, with its three modes
- `faultkit/references/`: the method, the silent-failure catalog, the
  faultkit scenario mapping, execution and gotchas
- `faultkit/scripts/run_faultkit.py`: the verified runner
- `skills/`: Claude Code plugin wrappers
- `evals/`: prompts and assertions the skill is tested against

faultkit is open source under Apache 2.0: [faultkit.dev](https://faultkit.dev/),
[github.com/faultkit/faultkit](https://github.com/faultkit/faultkit). This
skill is under the same licence.
