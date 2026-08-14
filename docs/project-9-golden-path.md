# Project 9 - Multi-Tenant AI Platform Golden Path

Generates a governed service repository containing a runnable Python health service, test, non-root container, Kubernetes deployment/service/default-deny network policy, probes and resource bounds, Terraform environment validation, four isolated environment configurations, CI test/audit/build gates, CODEOWNERS, SLOs, and resource-scoped IAM.

The validator blocks missing controls, root containers, writable roots, missing limits, wildcard IAM, and incomplete CI gates. Exercises: generate a service; start its health server; build its image; inspect manifests; intentionally weaken every security control and run validation. Discuss templates versus paved roads, upgrade propagation, policy-as-code, escape hatches, tenancy boundaries, secret delivery, workload identity, image signing, GitOps promotion, drift, and platform adoption metrics.

## Complete answered Staff/Principal Q&A

The detailed answers, trade-offs, and exact implementation evidence are in [`projects/project-09-golden-path/PROD.md`](../projects/project-09-golden-path/PROD.md).
