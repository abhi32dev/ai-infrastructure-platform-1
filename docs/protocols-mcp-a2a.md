# Protocol Lab - MCP and Agent-to-Agent (A2A)

This additional isolated lab implements the two complementary protocol surfaces against current official concepts:

- MCP protocol revision `2025-06-18`: initialization/version negotiation, capabilities, tools, resources, prompts, JSON-RPC errors, initialized/cancel notifications, schema checks, tool guardrails, telemetry, and cost
- A2A `1.0`: Agent Card discovery, skills/interfaces/capabilities, version negotiation, messages and typed parts, persistent task lifecycle, artifacts, context, list/get/cancel, failure state, security, telemetry, and cost

MCP lets an agent use tools/context exposed by a server. A2A lets independent opaque agents discover and collaborate without sharing internal reasoning or tool implementation. An A2A remote agent may itself be an MCP host/client internally.

## Guardrails and observability

Every protocol operation authenticates a principal supplied by the hosting boundary, applies tenant/RBAC/risk policy, validates schemas and message content, blocks injection patterns, records trace spans, and attributes latency/cost. Audit records store decisions and identities, not secrets or chain-of-thought.

## Exercises

1. Call MCP before initialize and inspect the protocol error.
2. Negotiate an unsupported revision.
3. List/call tools; omit a required argument; invoke a high-risk tool.
4. Read a resource and render a prompt.
5. Cancel an MCP request ID.
6. Inspect an A2A Agent Card and choose a skill/interface.
7. Send a message and inspect task history/artifacts.
8. Defer and cancel a long-running task.
9. Trigger remote failure and observe terminal task state.
10. Attempt prompt injection and cross-tenant access.
11. Inspect correlated telemetry and cost attribution.

## Staff-level discussion

Explain protocol versus transport; JSON-RPC correlation; capability/version negotiation; task state machines; artifact chunking and idempotency; synchronous, streaming, and push updates; authentication at the transport and authorization at operations; agent-card trust/signing; SSRF and confused-deputy risks; delegation depth and budgets; cancellation propagation; trace-context propagation; schema evolution; retry safety; data minimization; and MCP-versus-A2A selection.

Primary references used for terminology: [MCP specification](https://modelcontextprotocol.io/specification/2025-06-18) and [A2A 1.0 specification](https://a2a-protocol.org/latest/specification).
