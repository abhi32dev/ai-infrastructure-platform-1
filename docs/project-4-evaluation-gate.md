# Project 4 - Evaluation and Release-Gating Platform

Implements versioned evaluation suites, deterministic requirement and safety metrics, replaceable judge scoring, latency/cost measurement, persisted case results, and four-dimensional release gates. It also implements a two-proportion z-test for controlled experiments and reports absolute effect, relative effect, z-score, p-value, and significance.

## Exercises and interview prompts

Run a passing candidate, remove a required term, add a forbidden term, introduce latency, and increase cost. Observe that each dimension blocks independently. Replace the deterministic judge with a second model and discuss judge bias, position bias, calibration, reproducibility, and why a model judge cannot be the only safety control.

Ask: How is an evaluation dataset versioned? What prevents test leakage? When is a p-value misleading? What is practical significance? How do you calculate power and sample size? Which checks belong in CI, shadow traffic, canary, and A/B testing?

