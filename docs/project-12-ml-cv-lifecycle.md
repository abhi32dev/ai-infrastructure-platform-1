# Project 12 - Classical ML and Computer-Vision Lifecycle

Implements deterministic data generation, schema/finite/binary-label validation, seeded splitting, logistic-regression training from gradient descent, classification metrics, file-based model/version registry, quality-gated promotion, rollback, batch/online prediction boundary, feature-mean drift monitoring, and retraining recommendation.

The CV track creates synthetic image arrays, connected-component object detection, bounding boxes, IoU, and centroid tracking with persistent identities. This makes detection-versus-tracking and metric mechanics inspectable without a GPU or opaque downloaded weights.

Exercises: derive the gradient; alter learning rate; corrupt data; fail promotion; shift one feature; roll forward/back; add two crossing objects; calculate IoU manually. Discuss reproducibility, leakage, calibration, imbalance, lineage, shadow/canary, covariate/concept drift, label delay, retraining triggers, detector thresholds, NMS, mAP, tracker association, GPU batching, and framework packaging.

NumPy is the only runtime dependency and is pinned inside this project's environment. TensorFlow/PyTorch integration remains a framework substitution over these lifecycle contracts; the lab does not falsely claim that this connected-component detector is a neural detector.
