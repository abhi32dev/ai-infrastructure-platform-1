# Project 4 - Evaluation and Release-Gating Platform

Implements versioned evaluation suites, deterministic requirement and safety metrics, replaceable judge scoring, latency/cost measurement, persisted case results, and four-dimensional release gates. It also implements a two-proportion z-test for controlled experiments and reports absolute effect, relative effect, z-score, p-value, and significance.

## Exercises

Run a passing candidate, remove a required term, add a forbidden term, introduce latency, and increase cost. Observe that each dimension blocks independently. Replace the deterministic judge with a second model and discuss judge bias, position bias, calibration, reproducibility, and why a model judge cannot be the only safety control.

## Staff-level interview questions

### 1. How is an evaluation dataset versioned?

**Answer.** Version the complete evaluation contract, not only a JSON file: immutable case IDs, inputs, expected behavior, rubric, slicing metadata, preprocessing code, judge prompt/model, metric implementation, and threshold policy. A run must persist the suite ID and candidate version so a decision is reproducible. New or corrected cases create a new version; they do not silently rewrite the suite used by an earlier release.

```python
# ailab/eval_platform.py · EvaluationPlatform.register_suite/run
suite_id = f"{name}:{version}"
self.connection.execute(
    "INSERT OR REPLACE INTO suites VALUES (?,?,?,?,?)",
    (suite_id, name, version, json.dumps([asdict(case) for case in cases]), time.time()),
)
self.connection.execute(
    "INSERT INTO runs VALUES (?,?,?,?,?,?,?)",
    (run_id, suite_id, candidate.name, candidate.version,
     "evaluated", json.dumps(summary), time.time()),
)
```

The lab uses a readable `name:version` identity. Production additionally stores a content digest and makes published versions append-only, preventing the same label from resolving to different cases.

### 2. What prevents test leakage?

**Answer.** Separate authoring, tuning, validation, and final holdout datasets; restrict holdout access; deduplicate semantically across splits; split by time/user/source before chunking; and record every evaluation query. Never paste hidden answers into prompts, retrieval indexes, model-judge instructions, or training data. Repeated manual optimization against the holdout is itself leakage, so rotate shadow holdouts and require an independent owner for final release evaluation.

```text
TRAIN/TUNE  -> visible to builders; used for iteration
VALIDATION  -> limited reuse; reports slice regressions
HOLDOUT     -> access-controlled; one-way release decision
LIVE SHADOW -> post-training drift and novel failures

dataset_manifest = hash(source IDs + split policy + cases + rubric)
```

The current `EvalCase` boundary keeps prompts and expectations explicit; production adds lineage, access controls, similarity-based duplicate detection, and signed dataset manifests around it.

### 3. When is a p-value misleading?

**Answer.** A p-value is misleading when assignment is not random, samples are dependent, the metric or stopping rule was chosen after seeing results, many hypotheses are tested without correction, the sample is underpowered, instrumentation differs, or a tiny but useless effect becomes significant at enormous scale. It is not the probability that the treatment is better. Report effect size, confidence interval, sample size, guardrail metrics, assignment unit, and the pre-registered stopping rule with it.

```python
# ailab/eval_platform.py · two_proportion_z_test
pooled = (success_a + success_b) / (total_a + total_b)
se = math.sqrt(pooled * (1 - pooled) * (1 / total_a + 1 / total_b))
z = (rate_b - rate_a) / se if se else 0.0
p = math.erfc(abs(z) / math.sqrt(2))
```

This test assumes independent Bernoulli observations. User-clustered, repeated-measure, sequential, or network experiments need an analysis that matches their actual randomization and dependence structure.

### 4. What is practical significance?

**Answer.** Practical significance asks whether the effect is large enough to justify cost and risk. Define a minimum detectable/useful effect before the experiment and translate it into product and operational units: successful tasks, retained users, dollars, GPU-hours, latency, safety incidents, or support load. Promotion requires statistical evidence *and* a confidence interval compatible with that minimum effect while all safety and reliability guardrails remain acceptable.

```python
# The lab reports both absolute and relative effects.
effect = rate_b - rate_a
return {
    "absolute_effect": effect,
    "relative_effect": effect / rate_a if rate_a else None,
    "p_value": p,
    "statistically_significant": p < 0.05,
}
```

For example, a statistically significant `+0.03%` conversion change may be rejected if it adds expensive inference and the predeclared minimum useful effect is `+0.20%`.

### 5. How do you calculate power and sample size?

**Answer.** Choose the primary metric and assignment unit, baseline rate or variance, minimum detectable effect, significance level `alpha`, desired power `1-beta`, allocation ratio, and expected attrition. For two equal-sized independent proportions, use the normal-approximation planning formula below, then inflate for clustering, multiple comparisons, variance uncertainty, and noncompliance. Validate the final number with simulation when metrics are heavy-tailed or the design is sequential.

```python
# Production planning example for equal-sized two-proportion arms.
from statistics import NormalDist

z_alpha = NormalDist().inv_cdf(1 - alpha / 2)
z_beta = NormalDist().inv_cdf(power)
p_bar = (p_control + p_treatment) / 2
n_per_arm = (
    z_alpha * (2 * p_bar * (1 - p_bar)) ** 0.5
    + z_beta * (
        p_control * (1 - p_control)
        + p_treatment * (1 - p_treatment)
    ) ** 0.5
) ** 2 / (p_treatment - p_control) ** 2
```

Sample-size planning happens before exposure. If the experiment is inspected continuously, use a sequential design or alpha-spending rule rather than repeatedly applying a fixed-horizon p-value.

### 6. Which checks belong in CI, shadow traffic, canary, and A/B testing?

**Answer.** Match the stage to the question and blast radius. CI runs deterministic, fast, no-user-impact checks: schema, unit/property tests, frozen offline evals, safety fixtures, and hard latency/cost ceilings. Shadow validates production inputs, provider/model drift, and capacity without serving candidate output. Canary serves a small bounded population to detect correctness, latency, cost, and safety regressions with automatic rollback. A/B testing estimates causal product impact only after technical and safety gates pass.

```text
CI fail        -> block artifact promotion
Shadow fail    -> keep candidate dark; diagnose drift/capacity
Canary fail    -> automatically roll back serving traffic
A/B inconclusive -> keep control; collect to planned horizon
A/B harmful    -> stop treatment and preserve audit evidence
```

`EvaluationPlatform.gate` supplies the deterministic CI/offline decision boundary: quality, safety, p95 latency, and average cost fail independently. Production reuses the same metric definitions in shadow/canary dashboards while rollout controllers own traffic and rollback.

For the separate seven-question production architecture review, see [`projects/project-04-evaluation/PROD.md`](../projects/project-04-evaluation/PROD.md).
