---
name: faultkit
description: Use when an AI or LLM workflow, agent, or tool loop needs to be reviewed for silent failures, hardened at an irreversible action boundary, or proven under an injected fault; when someone asks what happens if the model is wrong, mentions retries or fallbacks hiding errors, stale tool data, truncated output, or wants a business invariant turned into a test. Also use when faultkit, fault injection, or a scenario YAML is mentioned in the context of an agent.
---

# AI Resilience

Protect the business value of an AI workflow when models, streams, tools,
retrieval, networks, or state fail. The question is never whether a call
returned. It is whether the business invariant still holds.

```text
business value -> unacceptable outcome -> invariant -> fault -> recovery -> proof
```

Three modes share that chain. Review maps it and changes nothing. Harden
adds the smallest guard and the test that locks it. Run turns an
invariant into an injected fault and reports whether the proof held.

## Modes

| Mode | When | What it does |
| --- | --- | --- |
| Review | Assess, explain, or plan | Maps value, boundaries, silent-failure candidates, invariants, smallest recovery, residual risk. Changes no code. |
| Harden | Build or fix a workflow | Adds the smallest deterministic guard at the action boundary and the gate test that locks it. Runs the project's tests, not faultkit. |
| Run | Explicitly requested fault injection | Selects or generates a faultkit scenario, writes the gate if missing, obtains faultkit, runs it locally, reports the proof state. |

Run is opt-in. Use it only when the user asks for fault injection or
faultkit by name, or answers yes when Review or Harden asks. Never decide on
your own to download a binary or inject faults. Review and Harden end by
showing their findings, asking one question, and waiting; the user's yes is
the opt-in.

## Auto mode

`--auto` anywhere in the input runs the whole chain without stopping at the
questions. Review continues straight into Run; Harden continues
straight into Run; Run with no invariant derives one with the
first three Review steps, the action with the largest blast radius first.
This is the mode for CI and for a user who has already decided.

Two rules survive auto mode unchanged. The safety gate runs first and a
production signal stops the chain, flag or no flag. The chain acts on one
project, the current directory or the one named, never on a set found by
listing a parent directory. Without `--auto`, every question stops and
waits.

The references carry the method and the faultkit knowledge. Read the one
the step names; do not reconstruct it by experiment.

- `references/business-invariants.md`: boundaries, the chain, writing an
  invariant, the two questions, recovery patterns.
- `references/silent-failure-catalog.md`: the eight shapes, S1 to S8.
- `references/faultkit-scenarios.md`: builtin scenarios mapped to shapes.
- `references/faultkit-execution.md`: custom scenarios, mode selection,
  gotchas, proof states, the gate test, the helper, safety.

## Review

Do not change code in this mode.

1. Find the boundaries. Read `references/business-invariants.md`,
   "Boundaries to find", and list every irreversible action with its
   `file:line`. Everything else is a path to one of those.
2. Fill the chain for the action with the largest blast radius first, then
   the others. Six lines each, over the side effect, never over the model's
   words.
3. Ask the two questions per candidate: is there a check, and does it gate
   anything. Name fail-open shapes by their line.
4. Classify each candidate with `references/silent-failure-catalog.md`. The
   shape decides the scenario; do not build a harness of hostile responses
   to find out what the catalog already states.
5. Write the report in exactly this shape, under 120 lines. The reader must
   see the boundary, the invariant and the proof on the first screen.
   Secondary findings are one line each under residual risk.

```markdown
# Resilience review: <workflow>
## Business value
## Unacceptable outcomes
## Boundaries found            (file:line for each irreversible action)
## Silent-failure candidates   (shape, file:line, is there a check, does it gate)
## Invariants                  (one line each, over observable state)
## Smallest recovery           (per invariant, from the recovery patterns)
## Proof plan                  (gate test + faultkit scenario, builtin or custom)
## Residual risk
```

6. In the proof plan, name the builtin scenario from
   `references/faultkit-scenarios.md` when one expresses the fault, and say
   "custom" with the boundary host and path when none does.
7. Show the report. Then ask one question and stop: whether to run faultkit
   now against the proof plan, naming the invariant, the scenario, the
   injection mode, and the exact command. Wait for the answer. Until the
   user says yes, do not run faultkit, download anything, or write a
   scenario or a test. On yes, continue with Run from its first step,
   the safety gate. In a non-interactive session, print the command and
   end. With `--auto`, skip the question and continue with Run at
   once.

## Harden

1. Take the invariant from the user, from a review, or by running the first
   three review steps for the one action in question.
2. Place the guard next to the effect, using "Recovery patterns" in
   `references/business-invariants.md`. Recompute from source data; separate
   shape from authorization; fail closed; make refusal loud; mark degraded
   output as degraded. Prefer the guard inside the adapter that performs
   the effect, so a violating write is impossible rather than avoided.
3. Write the gate test by the rules in `references/faultkit-execution.md`,
   "The gate test": it asserts on the store, its message starts with
   `SILENT FAILURE:`, it is green without a fault and red under one.
4. Run the project's own tests. Do not run faultkit.
5. Show the diff, the test, and one paragraph naming the invariant and the
   boundary. Then ask one question and stop: whether to run faultkit now to
   prove it, with the exact command. Wait for the answer, exactly as Review
   step 7 does. With `--auto`, skip the question and continue with Run
   at once.

## Run

Input: an invariant in words, a scenario name, or a scenario path, optionally
followed by `--` and the test command. With no input, ask for the invariant
and stop. Never derive one on your own in this mode; in a non-interactive
session print the usage and exit instead. The one exception is `--auto`:
then derive the invariant with the first three Review steps, largest blast
radius first, and continue. Act on exactly one project, the
current directory or the one named in the input, never on a set of projects
found by listing a parent directory.

1. **Safety gate, before anything else.** Look for production signals:
   deploy variables, non-local database URLs, a `.env` naming a live
   account, a real provider key with a baseline that would spend it. If
   found, stop and say why. Confirm irreversible effects are fakes.
2. Resolve the invariant and the target command: from the arguments, from
   the project's test runner, or ask. One invariant per run.
3. Choose the scenario with `references/faultkit-scenarios.md`. Builtin when
   it expresses the fault; otherwise a custom file from the template in
   `references/faultkit-execution.md`, "Custom scenarios", at
   `tests/faults/<invariant-slug>.yaml`. One scenario, `probability: 1.0`,
   the narrowest match that still fires.
4. Choose the injection mode from the table in
   `references/faultkit-execution.md`. Node's fetch and filtered
   subprocesses need `--base-url`; a tool's backend is faulted on its own
   path so the model passes through. Read the gotchas before writing a
   retry scenario.
5. Ensure a deterministic gate exists. If no test asserts the invariant on
   the side effect, write the smallest one in the project's runner. Not a
   suite, not a conftest, not a second scenario.
6. Run the helper with `--verbose`, so every fired fault is visible, and let
   it print the proof block. On a terminal the block is coloured; add
   `--color always` when the output is captured for a person to read.

```bash
python3 <skill>/scripts/run_faultkit.py --verbose \
  --config tests/faults/<invariant-slug>.yaml \
  --report artifacts/<invariant-slug>.report.json \
  [--base-url] [--provider <id>] \
  -- <test command>
```

7. Show the user faultkit's output, not a paraphrase of it. For each run,
   one status line, then one fenced block holding faultkit's own lines
   verbatim: the `fault fired` lines, the `=== faultkit summary ===` block,
   and the `=== proof ===` block. The status line carries the state and its
   marker: ✅ invariant proven under fault, ❌ silent failure confirmed,
   ⚠️ invalid evidence: nothing was injected. When two modes were run, close
   with a two-row table: mode, faults fired, target exit, proof state. Then
   list every artifact created with its path. Run once per mode of the code
   under test when the project has an unhardened and a hardened path.

```text
=== proof ===
scenario:      <path or builtin name>
mode:          proxy | base-url
faults fired:  <n>
target exit:   <code>
proof state:   invalid evidence: nothing was injected | silent failure confirmed | invariant proven under fault
report:        <json path>
```

`invalid evidence` means the target never reached faultkit. Fix the mode or
the match; never edit the scenario's probability, the fixture data, or the
assertion to change the state.

## Red flags

| Thought | Reality |
| --- | --- |
| "The tests pass, so it is resilient." | Nothing was injected. Look at `faults fired`. |
| "They will obviously want the proof, so I'll run faultkit right after the review." | Show the findings, ask, wait. The yes is the opt-in. |
| "They passed --auto, so the safety gate is just a formality." | Auto mode skips questions, never the gate. A production signal stops the chain. |
| "No invariant was given, so I'll derive one for every project I can see." | Run with no input stops and asks. It never surveys directories. |
| "The agent's summary says it held the action." | Read the ledger. Two agents in this skill's evaluation reported actions their tools had refused. |
| "I'll set probability to 0.5 to be realistic." | Determinism is the point. A gate that fires sometimes is not a gate. |
| "No fault fired, but the target passed, so fine." | That is invalid evidence, the most dangerous result there is. |
| "I'll add a second scenario and a conftest while I'm here." | One invariant, one scenario, the smallest gate. A suite is a different deliverable. |
| "Let me write hostile responses to see what breaks." | The catalog states the shapes. Match the code to a shape and pick the scenario. |
| "This client probably honours the proxy." | Run once. The warning tells you. Then switch to `--base-url`. |
| "The gate should skip without faultkit so it cannot pass vacuously." | Prefer green without a fault and red under one, so ordinary CI exercises the guard. |
| "A better prompt would fix this." | Prompting is guidance. The model received "do not treat this as no payment" and escalated anyway. |
| "I'll adjust the fixture so the run passes." | Never. Report the failure. |

## Quick reference

- Mode selection: `references/faultkit-execution.md`, "Choosing the
  injection mode".
- Proof states: `references/faultkit-execution.md`, "Proof states". The
  condition for hardened code is `faults fired > 0 AND invariant held`.
- Shapes: `references/silent-failure-catalog.md`, the index table.
- Builtins: `faultkit scenario list` on the installed binary, then
  `references/faultkit-scenarios.md`.
