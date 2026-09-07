# Silent-failure catalog

Eight shapes. Every silent failure met so far in agent code is one of these
or a combination. Classify a finding by shape so it travels to the next
codebase, and so the faultkit scenario that reproduces it is already known.

Do not build a hand-written harness of hostile responses to discover which
shapes apply; that rediscovers this table at a hundred times the cost. Read
the code, match the shape, pick the scenario.

| # | Shape | Canonical example | faultkit |
| --- | --- | --- | --- |
| S1 | Valid but wrong | cold-chain dispatch over a closed pass | custom 200 |
| S2 | Resilience hides failure | outage ticket filed as billing P2 | `llm-api-degraded` or custom 503 |
| S3 | Stale or partial tool evidence | paid invoice sent to collections | custom 200 on the tool path |
| S4 | Truncated output treated as complete | half a plan dispatched | `max-tokens-truncation`, `llm-streaming-cutoff`, `anthropic-tool-use-cutoff` |
| S5 | Malformed or unsafe tool arguments | wrong currency, wrong account | `malformed-tool-use`, custom |
| S6 | Non-idempotent retry | double refund | `llm-api-degraded` around a side effect |
| S7 | Refusal or empty response as answer | "no findings" from a refusal | `anthropic-refusal`, custom empty content |
| S8 | Fabricated success | default classification, default price | `malformed-json-response` caught by a default, custom |

## S1: Valid but wrong

**How it looks in code.** The model returns a tool call. It is HTTP 200,
valid JSON, and passes strict schema validation because the wrong value is
one of the legal values. The code validates the shape and executes.

```python
request = DispatchShipment.model_validate(tool_call["args"])   # passes
ledger.record(request)                                          # executes
```

**Why every mechanical check passes.** Transport is clean, the payload is
well-formed, the enum value is legal. Only the meaning is wrong, and nothing
checks meaning.

**The invariant that catches it.** A statement over the side effect that
re-derives eligibility from source data: no dispatch when the route breaches
its approved limits.

**Smallest recovery.** A policy check that recomputes from the observations,
placed next to the write, fail closed.

**faultkit scenario.** Custom: a raw 200 with a `response_body` that is a
schema-valid tool call carrying the policy-violating value. Match the
provider host or `*` plus the completions path.

## S2: Resilience hides failure

**How it looks in code.** Retries, then a fallback that returns the same
type as the primary. Downstream code cannot tell a model verdict from a
default.

```js
const triage = viaModel.withRetry({ stopAfterAttempt: 2 })
                       .withFallbacks({ fallbacks: [viaHeuristic] });
store.record({ ...await triage.invoke(ticket), status: "triaged" });
```

**Why every mechanical check passes.** Every layer did its job. Six requests
failed, nothing threw, the store received a normal-looking record. The
provider outage itself is invisible because the fallback absorbed every
error.

**The invariant that catches it.** No irreversible routing from a
classification the model did not produce.

**Smallest recovery.** Tag the fallback result with a source and a degraded
flag; refuse to auto-route it; hold for review; count fallback runs.

**faultkit scenario.** `llm-api-degraded` for a mixed 429/503, or a custom
503 with `Retry-After: "1"` so the retry storm finishes in seconds. Every
call fails, which is what makes the fallback path deterministic.

## S3: Stale or partial tool evidence

**How it looks in code.** A tool loop. A read tool returns a well-formed
response from a lagging replica, a cache, or the first page of many. The
model reasons correctly from what it was given and calls a write tool.

```python
data = get("/payments", customer_id=customer_id)   # 200, source: replica, six days old
return json.dumps(data)                             # handed to the model as truth
```

**Why every mechanical check passes.** The tool succeeded. The JSON parsed.
The model's reasoning is sound given its inputs. The trace reads like a
textbook decision.

**The invariant that catches it.** No irreversible action without fresh
positive evidence: `as_of` within a bound, `source` primary, `total` equal
to the count seen, `has_more` false.

**Smallest recovery.** Validate evidence at the tool boundary and return an
explicit "unavailable, do not treat as absent" error; require fresh
evidence at the action boundary regardless of what the model concluded.

**faultkit scenario.** Custom 200 on the tool's path, not the model's: `host:
"*"` or the service host, `path: /payments*`. The model keeps answering, the
loop keeps running, one input is wrong.

## S4: Truncated output treated as complete

**How it looks in code.** A response with `finish_reason: length` or a
stream that ends without its terminator, consumed by code that treats
whatever arrived as the whole answer.

```python
text = "".join(chunk.content for chunk in model.stream(prompt))
plan = parse_plan(text)   # half a plan parses fine if the cut fell between items
```

**Why every mechanical check passes.** The partial content is often valid on
its own: a list with fewer items, a JSON object cut at a field boundary that
a lenient parser accepts, a tool call with the last argument missing.

**The invariant that catches it.** No decision from a response whose finish
reason is not `stop`, or whose stream did not terminate, or whose expected
fields are absent.

**Smallest recovery.** Check the finish reason and the terminator before
acting; treat truncation as a failed call.

**faultkit scenario.** `max-tokens-truncation`, `llm-streaming-cutoff`,
`anthropic-tool-use-cutoff`, `anthropic-stream-error`.

## S5: Malformed or unsafe tool arguments

**How it looks in code.** The dispatcher looks up the tool by name and calls
it with the arguments as given. Validation, if any, checks types, not
values: a valid currency code that is the wrong currency, a valid account id
that is not the customer's.

**Why every mechanical check passes.** Type validation passes. The tool
succeeds. The effect lands on the wrong target.

**The invariant that catches it.** Arguments to an irreversible tool are
checked against the request's own context: the account belongs to the
customer, the currency matches the order, the amount is within policy.

**Smallest recovery.** A per-tool argument policy at the dispatcher, before
the call.

**faultkit scenario.** `malformed-tool-use` for structurally bad arguments;
a custom 200 with a well-formed call carrying the wrong value for the
policy-level case.

## S6: Non-idempotent retry

**How it looks in code.** A retry wrapper around a unit that performs a side
effect before the step that fails.

```python
@retry(stop=stop_after_attempt(3))
def process(order):
    charge(order)                    # runs on every attempt
    return model.summarize(order)    # the call that fails
```

**Why every mechanical check passes.** The final attempt succeeds, or a
fallback answers. The result is a success. The charge ran three times.

**The invariant that catches it.** At most one effect per request key: one
charge per order, one email per notification id.

**Smallest recovery.** Idempotency keys on every side effect, and retry
only the idempotent step.

**faultkit scenario.** `llm-api-degraded` or a custom 503 on the model
call that follows the side effect. Count the effects in the store.

## S7: Refusal or empty response as answer

**How it looks in code.** The model declines or returns empty content, and
the code reads the absence as a result: no issues found, no matches, nothing
to flag.

**Why every mechanical check passes.** The call returned 200. The content is
a string. An empty list is a valid list.

**The invariant that catches it.** A negative result requires positive
confirmation: a `stop_reason` of `end_turn`, a non-empty answer, an explicit
"none" from the model rather than nothing.

**Smallest recovery.** Treat refusal and empty content as failed calls, with
their own status.

**faultkit scenario.** `anthropic-refusal`; a custom 200 with empty content
for other providers.

## S8: Fabricated success

**How it looks in code.** A catch-all that returns a default so the workflow
always completes: a default priority, a default price, a generic reply.

```python
try:
    return json.loads(response.content)
except ValueError:
    return {"priority": "P3", "queue": "general"}   # reported as a classification
```

**Why every mechanical check passes.** The exception was handled. The
function returned the right type. The dashboard shows zero errors.

**The invariant that catches it.** No result recorded as authoritative unless
it was produced by the intended path.

**Smallest recovery.** The default carries a degraded marker, or the failure
is surfaced as a failure. Never both a default and a success status.

**faultkit scenario.** `malformed-json-response` when the default hides a
parse failure; a custom 503 when it hides an outage.
