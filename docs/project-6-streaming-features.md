# Project 6 - Streaming Features and Online Inference

Implements a durable partitioned event log, stable key partitioning, monotonically increasing partition offsets, independent consumer-group checkpoints, idempotent event publication, schema validation and DLQ, configurable late-event handling, stateful online aggregates, offline point-in-time snapshots, lag/freshness signals, and training-serving skew detection.

Exercises: publish duplicates and unsupported schemas; pause one group and observe lag; change allowed lateness; snapshot before and after new events; compare online and point-in-time features. Discuss at-least-once delivery, watermarking, repartitioning, hot keys, transactional offset+state writes, Kafka compaction, feature TTL, point-in-time joins, and why this SQLite implementation demonstrates semantics but not Kafka throughput or distributed fault tolerance.
