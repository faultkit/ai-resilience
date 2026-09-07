# Baseline behaviour without the skill

The RED record: what general-purpose agents do on the three eval prompts
with no skill loaded, in their own words where it matters. The skill is
written against the gaps listed here and nothing else.

## Iteration 0: contaminated, kept for the record

The first baseline ran against the live `faultkit-agents` directories. All
three agents produced strong results: the review named the ledger as the
boundary and pointed at `agent.py:273`; the collections run chose
`host: "*"`, `path: /payments`, a stale replica body and gates on the
ledger; the Node run chose `--base-url`, the provider host and
`Retry-After: 1` while explaining why the builtin 30-second value would be
wrong.

They could, because every one of those answers is written in the
directories they were reviewing: the READMEs describe the exact failure,
the shipped `scenario.yaml` files show the match and the fault, and the
Node agent said so itself ("the shipped scenario.yaml / test/unsafe.test.mjs
already cover this failure"). That is not a baseline; it is reading the
answer key.

Two things survive from iteration 0 as findings about the review prompt:

- Without a fixed report shape the review ran to 332 lines and buried the
  invariant, the boundary and the fix under eight numbered sub-findings.
- Nothing in any run mentioned a proof plan unprompted: no gate test, no
  scenario choice, no builtin-versus-custom decision, even with a scenario
  file sitting in the directory.

Outputs are archived under
`ai-resilience-workspace/iteration-0-docs-present/` and are not used for
grading.

## Iteration 1: stripped fixtures

Each fixture is the committed agent code with `README.md`, `scenario.yaml`,
`run-faultkit.sh`, all tests and the walkthrough page removed, and the
virtualenv or `node_modules` linked in. The code still carries its own
docstrings and the `unsafe`/`guarded` mode switch; that is as far as
stripping goes without rewriting the agents. Eval prompts point at
`ai-resilience-workspace/fixtures/<agent>` and every run works in its own
copy.

### Eval 0: review coldchain-dispatch-agent

324 lines, 452 s, 88,523 tokens. The analysis is correct and the cost is the
problem.

What it did without help:

- Stated the invariant over the ledger write and said the model's tool call
  "is a proposal, never an authorization".
- Found `agent.py:273`, called it "a bypass, not a missing check", and gave
  the one-line fix plus the two-line loud-failure alternative.
- Verified the silent failure by running the real faultkit binary against
  the fixture, then wrote a sixteen-case hostile-response harness of its own
  to prove every structural failure is loud.
- Found three real secondary defects the demo authors had not listed: no HTTP
  timeout on the planner, a shared httpx client closed by `close()`, no
  idempotency key on the ledger.

What the skill must change:

- The report shape. The invariant appears at line 70 and the fix at line 239.
  A fixed template with the boundary, the invariant and the proof in the
  first screen is the single biggest improvement available.
- The harness. Sixteen hand-written hostile responses cost most of the budget
  and reproduced what a catalog of shapes states in a table. The skill
  should hand over the catalog and the builtin scenario list so the agent
  spends tokens on the codebase, not on rediscovering faultkit.
- Classification. Nothing names the shape, so the finding does not travel
  to the next codebase.
- Proof plan as a section. It ran faultkit to confirm the finding but never
  said which gate test plus which scenario would lock the invariant in CI.

### Eval 1: run on collections-agent

475 s, 119,434 tokens, the most expensive run. Correct at every decision
point and roughly three times larger than the smallest sufficient answer.

What it did without help:

- Chose forward-proxy mode with `host: "*"` and `path: /payments`, reasoning
  from `httpx` honouring `HTTP_PROXY` and loopback not being excluded.
- Wrote a stale replica body: 200, `source: replica`, `as_of` seven days
  old, the payment for INV-2207 absent, nothing invented.
- Asserted on the ledger, with a `SILENT FAILURE` message naming the paid
  invoice, and read exit 1 under fault as the gate catching it.
- Recorded three caveats worth keeping: a 503 makes the unsafe agent crash
  before writing, which is fail-closed by accident rather than the promised
  hold; the guarded agent's closing summary still claims it escalated, so
  "the ledger, not the narration, is what the tests trust"; a fresh primary
  response that omits the payment is indistinguishable from truth.

What the skill must change:

- Scope. It produced two scenarios, a conftest, four test files and a run
  script. The contract is one scenario for the invariant and the smallest
  gate that fails when it breaks. A suite is a different deliverable.
- Vocabulary. Exit codes were read correctly but described ad hoc. The
  proof-state names (invalid evidence, silent failure confirmed, invariant
  proven) must be fixed strings so CI and humans read the same thing.
- Time. Half the budget went to exploring how faultkit intercepts traffic.
  The mode-selection table and the scenario template exist to remove that
  exploration.

### Eval 2: run on support-triage-agent (Node)

261 s, 76,051 tokens, run twice: once with a comment in `demo.mjs` that
spelled out the `--base-url` command (archived as `without_skill_leaky`),
once with that comment removed. The second run made the same choices.

What it did without help:

- Chose `--base-url` and explained why: Node's fetch ignores `HTTPS_PROXY`,
  and base-URL mode still matches on the provider host. It found this in
  faultkit's own README and `run --help`, which were on disk.
- Wrote a raw 503 with `Retry-After: 1` and said the builtin's 30 seconds
  "would take minutes".
- Asserted on the stored record, with a message naming the queue, the
  priority, the SLA, the attempt count and the source of the classification.
- Made the gate skip when `OPENAI_BASE_URL` is unset "so it can't pass
  vacuously against the local mock".

What the skill must change:

- The vacuity decision. Skipping outside faultkit means the guard is never
  exercised by ordinary CI. The preferred gate is green without a fault and
  red under one; it asserts the invariant on the store and lets faultkit
  supply the fault. Skip only when the gate cannot run at all without one.
- Nothing else in substance. The mechanics were right. What differs from
  the contract is again shape, vocabulary and the absence of a safety gate
  and a proof block.

## What the skill must add, in order of measured value

1. A fixed report shape for review and a fixed proof block for run, so
   the boundary, the invariant, the fired count and the proof state are the
   first things on screen. Every baseline buried them.
2. The catalog of shapes and the faultkit references, so the agent stops
   spending half its budget rediscovering how faultkit intercepts traffic
   and which gotchas apply. Baselines cost 261 to 475 seconds and 70,000 to
   120,000 tokens each; the mechanics they rediscovered fit on two pages.
3. Scope rules: one scenario per invariant, the smallest gate that fails when
   it breaks, no suites, no harnesses of hand-written hostile responses.
4. The proof-state vocabulary and the rule that exit 3, or zero fired events,
   is invalid evidence rather than a pass.
5. A safety gate before any run, and the rule that the ledger, not the
   agent's narration, is what a gate reads. Two baselines discovered the
   narration lies; the skill states it up front.
6. The gate should be green without a fault and red under one, so it runs in
   ordinary CI too.

What the skill does not need to teach this model: how to find an invariant,
how to spot a fail-open `or`, that a fallback returning the primary's shape
is dangerous. It found all of those alone. The skill makes the result
consistent and cheap, and it carries the faultkit knowledge for models and
environments where the docs are not on disk.
