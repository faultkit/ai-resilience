# faultkit scenarios

The installed binary's `faultkit scenario list` is authoritative. Run it
before choosing; this table describes v0.1.2 and will lag behind releases.
Never present a roadmap scenario as shipped.

## Builtin scenarios

| Scenario | Mode | Catalog shape | Example invariant | Notes |
| --- | --- | --- | --- | --- |
| `llm-api-degraded` | proxy | S2, S6 | a fallback result is never auto-routed; at most one charge per order | 429/503/timeout across OpenAI, Anthropic, Bedrock; narrow with `--provider` |
| `malformed-json-response` | proxy | S8 | no result recorded unless produced by the intended path | 200 with invalid JSON; tests what a lenient parser or a default hides |
| `malformed-tool-use` | proxy | S5 | no irreversible tool call with arguments outside the request's context | schema-violating tool arguments |
| `max-tokens-truncation` | proxy | S4 | no decision from a response whose finish reason is not `stop` | 200 with `finish_reason: length` |
| `llm-streaming-cutoff` | proxy | S4 | a partial stream never becomes a final decision | drops the SSE connection mid-token, no terminator |
| `anthropic-overloaded` | proxy | S2 | as `llm-api-degraded` | HTTP 529 `overloaded_error` |
| `anthropic-stream-error` | proxy | S4 | a stream without `message_stop` is not an answer | error event mid-stream |
| `anthropic-tool-use-cutoff` | proxy | S4, S5 | an incomplete tool call is never dispatched | `stop_reason: max_tokens` on a `tool_use` block |
| `anthropic-refusal` | proxy | S7 | a refusal is not a negative result | 200 with `stop_reason: refusal` |
| `anthropic-request-too-large` | proxy | S2 | an oversized request degrades explicitly | HTTP 413 |
| `bedrock-model-timeout` | proxy | S2 | as `llm-api-degraded` | HTTP 408 `ModelTimeoutException` |
| `bedrock-service-unavailable` | proxy | S2 | as `llm-api-degraded` | HTTP 503 `ServiceUnavailableException` |
| `flaky-network` | ebpf | S2, S6 | a reset connection never leaves a half-applied effect | `ECONNRESET` on recv; Linux, privileges required |
| `tool-permission-denied` | ebpf | S8 | a failed file operation is not reported as done | `EACCES` on file operations; Linux, privileges required |

The two eBPF scenarios need Linux 5.8+, x86-64, and either root or the
`cap_bpf`, `cap_net_admin`, `cap_perfmon` capabilities. The runner does not
escalate privileges; tell the user the command and let them run it.

## When a builtin is not enough

A builtin expresses a transport or format failure. Three shapes are neither:

- S1, valid but wrong: the response is a perfect 200 whose value breaks
  policy.
- S3, stale or partial evidence: the fault is on a tool's backend, not the
  model, and the body must look like that backend's normal answer.
- S8 when the default hides a value problem rather than a parse problem.

These need a custom scenario. See `faultkit-execution.md`, "Custom
scenarios". Writing one takes minutes; the body is the response the real
system would send on its worst plausible day.
