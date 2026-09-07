# faultkit execution

How to turn an invariant into a run that produces evidence. Everything here
was learned by doing it against real agents; the gotchas are the ones that
cost the most time.

## Custom scenarios

Record the six lines first. If any is blank, the scenario is not ready.

```text
Business value:
Unacceptable outcome:
Business invariant:
Boundary host and path:
Synthetic response:
Expected safe outcome:
```

Then the YAML:

```yaml
name: <invariant-slug>
description: <one line: what the synthetic response pretends to be>
experiments:
  - name: <fault-name>
    fault:
      http_status: 200
      response_headers:
        Content-Type: application/json
      response_body: '<verbatim JSON, the real service's shape>'
    match:
      host: "<host glob>"
      path: <path glob>
    probability: 1.0
```

Rules:

- `probability: 1.0`. Determinism is the point. A run that fires sometimes
  cannot be a gate.
- The narrowest `match` that still fires. A `path` glob almost always; a
  `host` glob only when the same path exists on several hosts you do not
  want to touch.
- `response_body` verbatim, in the real service's shape, with nothing
  invented. A stale snapshot omits data; it does not fabricate any.
- One scenario per invariant. A second failure mode is a second file.
- Put the file under `tests/faults/<invariant-slug>.yaml` unless the project
  already keeps scenarios somewhere.

Three worked examples, one per shape that needs a custom scenario:

**S1, valid but wrong, cold-chain dispatch.** Match `host: "*"`, `path:
/v1/chat/completions`. The body is a complete chat completion whose tool
call selects the route that breaches two weather limits, with a plausible
reason. Every structural check passes; only the policy check can catch it.

**S2, resilience hides failure, support triage.** Match `host:
api.openai.com`, `path: /v1/chat/completions`, `http_status: 503`,
`Retry-After: "1"`. Every call fails, the retry layers exhaust, the fallback
answers. The short `Retry-After` is deliberate; see the gotchas.

**S3, stale evidence, collections.** Match `host: "*"`, `path: /payments*`,
`http_status: 200`, a payments body with `"source": "replica"`, an `as_of`
days old, and the settling payment absent. The model is never touched and
the loop runs to its wrong conclusion.

## Choosing the injection mode

| Target | Mode | Why |
| --- | --- | --- |
| Python, Go, curl, most libc clients calling a provider | forward proxy (default) | they honour `HTTPS_PROXY` and the injected CA bundle |
| Node global `fetch`, undici, SDKs in a filtered subprocess | `--base-url` | they ignore proxy env; faultkit injects `OPENAI_BASE_URL` and friends |
| Bedrock via boto3 or the AWS SDKs | forward proxy | SigV4 survives the MITM; base-URL rewriting breaks it |
| A tool's backend service, local or remote | forward proxy, `host: "*"` or the host, plus a `path` glob | model calls pass through untouched; the loop keeps running |
| Syscall-level faults | eBPF, Linux, privileges | outside the runner; give the user the command |

When unsure whether a client honours proxy env, run once in forward-proxy
mode. If faultkit prints `warning: no requests reached faultkit`, switch to
`--base-url`. That warning is never something to work around by editing
the scenario.

## Gotchas

**Base-URL mode needs a provider host.** faultkit decides which environment
variable to inject from the scenario's `host`, so it must be a provider it
knows: `api.openai.com`, `api.anthropic.com`. `host: "*"` does not work in
`--base-url` mode.

**The builtin rate-limit fixture sends `Retry-After: 30`.** SDKs honour it.
A six-request retry storm becomes three minutes of sleeping. For any retry
or fallback path, write a raw 503 or 429 with `Retry-After: "1"`.

**Forward-proxy mode intercepts loopback too.** It sets `HTTP_PROXY` and no
`NO_PROXY`, so a mock service on `127.0.0.1` is faulted like any other host.
`--base-url` mode is the opposite: it sets `NO_PROXY=127.0.0.1,localhost`.

**Synthetic faults never reach the provider.** A fully synthetic fault skips
the upstream round trip. Running a faulted scenario with a real key
exported costs nothing and works offline. Only the un-faulted baseline
spends tokens.

**"No requests reached faultkit" is invalid evidence.** The target never
used the proxy or the injected base URL. The run may print a green test
result; it proved nothing. Exit code 3 says the same thing.

**Every synthetic response carries `X-Faultkit-Synthetic: true`.** Useful in
an outcome object for diagnostics, never as an input to a decision.

**A faulted model call stops an agent loop at step one.** With
`probability: 1.0` on the model host, the first call fails and the loop
never reaches its tools. Loop failures are reproduced by faulting a tool's
path while the model passes through.

## Proof states

faultkit exits 0 when the target passed, 1 when it failed, 2 on an internal
error, 3 when no fault fired, 4 on a usage error. The skill reads them as
three proof states:

| faultkit exit | Fired | Gate | Proof state |
| --- | --- | --- | --- |
| 3 | 0 | any | `invalid evidence: nothing was injected` |
| 0 or 1 | 0 | any | `invalid evidence: nothing was injected` |
| 1 | > 0 | failed | `silent failure confirmed` |
| 0 | > 0 | passed | `invariant proven under fault` |
| 2, 4 | | | `error: faultkit exited N` |

The proof condition for hardened code is `faults fired > 0 AND invariant
held`. A target that passed with nothing fired is the most dangerous
result, because it looks like the good one. Use these exact strings; CI and
humans should read the same word.

## The gate test

A gate is deterministic when it asserts on the side effect, not on the
model's text, and when its failure message says what happened in the terms
of the business. It is green without a fault and red under one, so ordinary
CI exercises the guard too. Skip outside faultkit only when the test cannot
run at all without an injected fault.

Rules:

- Assert on the store, ledger, queue, or outbox.
- Start the failure message with `SILENT FAILURE:` and name the action, its
  source, and what was recorded.
- Never read the agent's closing summary as evidence; two agents in this
  skill's own evaluation reported actions their tools had refused.
- Never edit fixture data, weaken an assertion, or lower `probability` to
  make a run pass.

pytest:

```python
def test_unsafe_agent_never_persists_a_policy_violation(tmp_path):
    ledger = DispatchLedger(tmp_path / "ledger.jsonl")
    outcome = run_agent(ledger, mode="unsafe")
    assert outcome.business_invariant_preserved, (
        "SILENT FAILURE: HTTP 200, schema-valid tool call, but "
        f"{outcome.requested_dispatch.route_id} was dispatched with policy "
        f"violations {outcome.policy_violations}"
    )
```

`node:test`:

```js
test("a ticket the model did not classify is never auto-routed", async () => {
  const outcome = await runAgent({ mode: "unsafe" });
  assert.ok(outcome.business_invariant_preserved,
    `SILENT FAILURE: ${outcome.ticket_id} auto-routed to ` +
    `${outcome.stored.queue}/${outcome.stored.priority} with a ` +
    `${outcome.stored.sla_hours}h SLA from a ${outcome.source} classification`);
});
```

## Running with the helper

`scripts/run_faultkit.py` acquires faultkit, runs the scenario, reads the
JSON report, and prints the proof block. It exits with faultkit's own code.

```bash
python3 <skill>/scripts/run_faultkit.py --verbose \
  --config tests/faults/<invariant-slug>.yaml \
  --report artifacts/<invariant-slug>.report.json \
  [--base-url] [--provider openai] [--color auto|always|never] \
  -- <the project's test command>
```

`--verbose` makes faultkit print one line per fired fault with its host and
path, which is the evidence a reader wants to see. The proof block is
coloured when stdout is a terminal: green for proven, red for a confirmed
silent failure, yellow for invalid evidence. `NO_COLOR` and `FORCE_COLOR`
are honoured; `--color always` forces it for captured output that a person
will read.

Binary resolution, first match wins: `--faultkit-bin`, the `FAULTKIT`
environment variable, `faultkit` on `PATH`, `--faultkit-source <dir>` built
with `go build`, then a download of the pinned release for this platform
verified against the release's `checksums.txt` and cached under
`~/.cache/faultkit/<version>/`. The pinned version is a
constant in the script; it is never resolved from "latest".

The proof block:

```text
=== proof ===
scenario:      tests/faults/paid-invoice-never-escalated.yaml
mode:          auto
faults fired:  1
target exit:   1
proof state:   silent failure confirmed
report:        artifacts/paid-invoice-never-escalated.report.json
```

Run the gate under the fault once per mode of the code under test. The
unhardened path should read `silent failure confirmed`; the hardened path
should read `invariant proven under fault`. Anything else is not done yet.

## Safety

- Runs stay in local, test, or explicitly authorized environments. Before
  running, look for production signals: deploy variables, non-local database
  URLs, a `.env` naming a live account, a real provider key with a baseline
  that would spend it. If found, stop and say why.
- Irreversible side effects must be fakes: a JSONL ledger, an in-memory
  store, a sandbox account.
- The runner downloads only the pinned version from the fixed releases URL,
  verified by checksum.
- Never weaken a test, edit fixture data, or change a scenario's
  `probability` to make a proof pass. Report the failure instead.
