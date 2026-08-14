# Project 8 - Adaptive Self-Healing Batch Platform

Implements manifest-backed runs, payload-size-aware bin packing, bounded parallel workers, per-item checkpoints, bounded retry, partial resume, output checksums, TTL idempotency across runs, and three-pass reconciliation against actual durable output listings. Permanent failures remain explicit missing items and make the run fail.

Exercises: vary payload size and target bytes; inject transient/permanent failures; delete a durable output after apparent success; resume a run; repeat the manifest inside/outside TTL. Discuss atomicity between output and checkpoint, conditional writes, leases, stragglers, Lambda limits, S3 listing semantics, work stealing, hot partitions, poison items, reconciliation cost, and why actual storage validation is stronger than trusting futures.

## Complete answered Staff/Principal Q&A

The detailed answers, trade-offs, and exact implementation evidence are in [`projects/project-08-batch-platform/PROD.md`](../projects/project-08-batch-platform/PROD.md).
