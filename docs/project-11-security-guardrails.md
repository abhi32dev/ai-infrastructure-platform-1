# Project 11 - Security, Privacy, Governance, and Guardrails

Implements signed expiring identity tokens, tenant isolation, role/action authorization, elevated high-risk tool controls, prompt-injection detection, PII redaction, output secret blocking, tenant-filtered retrieval, per-subject quotas, deletion and retention, and hash-chained audit events with tamper detection. Adversarial cases make guardrails measurable rather than anecdotal.

## Guardrail placement

1. Authentication: establish subject and tenant
2. Input: size/type/schema, injection, PII, policy classification
3. Retrieval: tenant and classification filters before similarity search
4. Planning: allowlisted capabilities and bounded delegation
5. Tool call: argument validation, least privilege, risk approval, idempotency
6. Output: secret/PII/policy/grounding checks
7. Runtime: quotas, deadlines, circuit breakers, cost budgets
8. Audit: decision, policy version, principal, resource, trace—never secrets or chain-of-thought

Exercises: tamper with tokens/audit records; attempt cross-tenant retrieval; exhaust quota; inject indirect instructions in a document; test secret-shaped output; delete a tenant. Discuss false positives, policy versioning, fail-open versus fail-closed, confused deputies, token audience, key rotation, ABAC versus RBAC, retrieval authorization before ranking, DLP, consent, data residency, and incident forensics.

## Complete answered Staff/Principal Q&A

The detailed answers, trade-offs, and exact implementation evidence are in [`projects/project-11-security/PROD.md`](../projects/project-11-security/PROD.md).
