# Business invariants

The method behind every mode. Read this once per codebase, then work from
the chain. It is short on purpose: a capable agent already knows how to
reason about failure. What it usually lacks is a fixed order of questions and
a rule for what counts as an answer.

## Boundaries to find

An AI workflow fails at the places where something crosses into the
application. Locate every one of these before judging any of them. The grep
patterns are starting points, not a complete list.

| Boundary | What to look for |
| --- | --- |
| Model call | `openai`, `anthropic`, `bedrock-runtime`, `langchain`, `langgraph`, `litellm`, `@ai-sdk`, `ai` (Vercel), raw `fetch`/`httpx`/`requests` to a provider host |
| Streamed response | `stream=True`, `for await`, `.stream(`, SSE parsing, partial JSON assembly |
| Tool execution | `@tool`, `bind_tools`, `ToolNode`, `withStructuredOutput`, `function_call`, `tool_calls[`, any dispatch table keyed by a name the model chose |
| Retrieval | vector search, `similarity_search`, `retriever`, search API calls whose results are fed to a prompt |
| Resilience code | `withRetry`, `withFallbacks`, `maxRetries`, `tenacity`, `p-retry`, `backoff`, circuit breakers, `try`/`except` returning a default |
| State write | writes to a database, queue, cache, file, or ledger that a later step reads |
| Irreversible action | payment, refund, charge, email, SMS, dispatch, deploy, delete, ticket routing, escalation, credit or access decision, anything a customer or regulator can see |

Irreversible actions are the ones that matter. Everything else is a path to
one of them. If a workflow has no irreversible action, its worst silent
failure is a wrong answer on a screen, and the review can say so in one line.

## The chain

For each irreversible action, fill this in. Six lines, in this order, no
prose around them.

```text
Business value:        what the workflow protects or produces
Unacceptable outcome:  the concrete thing that must never happen
Business invariant:    a deterministic statement over observable state
Fault:                 the failure that would produce the outcome
Recovery:              the smallest behaviour that keeps the invariant
Proof:                 the deterministic check that fails when it breaks
```

Filled in for an accounts-receivable agent that can hand an invoice to a
collections agency:

```text
Business value:        paying customers are never treated as delinquent
Unacceptable outcome:  a final notice or collections referral for a paid invoice
Business invariant:    no level-3 notice or escalation without fresh positive
                       payment evidence from the primary store
Fault:                 the payments service answers 200 from a replica six
                       days behind, so the settling payment is absent
Recovery:              list_payments rejects stale snapshots; escalation
                       refuses without fresh evidence and opens a review task
Proof:                 a test that runs the agent under that fault and asserts
                       the ledger holds no notice and no escalation
```

Fill the chain for the action with the largest blast radius first. One
invariant, fully proven, is worth more than six half-stated ones.

## Writing an invariant

An invariant is written over the side effect, never over the model's words.

Good:

- No `shipment.dispatched` record for a route whose corridor weather exceeds
  the route's approved severity limit.
- No ticket stored as `triaged` with an SLA unless the classification came
  from the model.
- No refund transaction whose amount exceeds the order total.

Bad:

- The model should be careful with overdue invoices.
- The agent handles rate limits gracefully.
- The summary should mention when a fallback was used.

The test: could a script check this from the store alone, with the model
switched off? If it needs the transcript, the prompt, or the model's
reasoning, it is not an invariant yet.

Two baselines in this skill's own evaluation found that an agent's closing
summary claimed actions its tools had refused. The narration is not
evidence. The ledger, the store, the queue, the outbox: those are.

## The two questions

For every candidate failure, in this order:

1. **Is there a check?** Schema validation, status-code handling, retries,
   fallbacks and policy evaluation all count.
2. **Does the check gate anything?** A check whose result is logged,
   reported, returned in a response object, or printed to the console, but
   does not decide whether the effect happens, is a log line, not a gate.

Any gate that can open for a reason unrelated to safety is not a gate.
Fail-open shapes to name on sight:

```python
should_dispatch = mode == "unsafe" or not violations   # the verdict is computed, then bypassed
```

```js
const result = await primary().catch(() => fallback());   // same type out, nobody downstream can tell
```

```python
priority = classify(ticket) or "P3"   # a default that conditions can only fail to lower
```

The cure for every one of these is structural: make the effect unreachable
unless permission was granted, and give the degraded path a different shape
from the healthy one.

## Recovery patterns

Five patterns, all deterministic, all placed next to the effect they protect.

**Recompute, do not trust.** Re-derive eligibility from the source data the
model was shown. Never read the model's stated reason as a fact.

**Separate shape from authorization.** Schema validation answers "is this
request well-formed?". Policy answers "is this action permitted given the
current state?". Treating the first as sufficient for the second is the
single most common silent failure.

**Fail closed, close to the effect.** The write happens only inside the
branch where the check passed. Put the check in the adapter that performs
the effect when you can, so a violating write is impossible rather than
merely avoided.

**Make refusal loud.** A blocked action is an event with a reason: a review
task, a held status, a log line at warning level, a metric. A crash is loud
too, and acceptable when nothing better exists.

**Mark degraded output as degraded.** A fallback result carries a source and
a degraded flag, and an irreversible action refuses to act on it. Count how
often the degraded path runs; an outage of the primary should show on a
graph.

Four things that look like fixes and are not:

- A better prompt. Prompting is guidance. The model in this skill's own
  evaluation received "do not treat this as no payment" in a tool result and
  escalated anyway.
- A retry. The response was valid; retrying samples another opinion.
- A stricter schema. Strict mode was already on and the wrong value was
  schema-valid.
- A second model as judge. A non-deterministic guard for a deterministic
  rule, with the same failure class it is meant to catch.
