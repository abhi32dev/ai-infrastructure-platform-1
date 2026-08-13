# Project 5 - High-Availability Inference Serving

Implements a live threaded server with readiness/liveness, bounded queues, load shedding, per-request deadlines, dynamic batching, batch validation, model error propagation, graceful drain/shutdown, deterministic canary routing, canary failure fallback, and rollback. Metrics expose completions, batches, maximum observed batch, rejected load, deadline failures, and model failures.

Exercises: vary batch size and wait time; run concurrent load; reduce queue capacity; inject slow/broken models; compare queue and inference latency; send 100% canary traffic then roll back. Discuss why thread cancellation cannot stop arbitrary Python model code, how process isolation solves it, HPA signals, GPU memory constraints, warmup, readiness versus liveness, and correlated failure across replicas.
