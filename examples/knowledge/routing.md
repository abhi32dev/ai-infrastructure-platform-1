# Model Routing and Release Safety

A model gateway can route simple requests to a small inexpensive model and complex requests to a larger model. Routing inputs may include required context length, structured-output reliability, latency objective, privacy policy, tenant budget, and observed model health. Every decision should record its reason so cost and quality regressions can be diagnosed.

Fallbacks should not retry blindly across every model. The gateway needs deadlines, per-provider concurrency limits, circuit breakers, and a bounded fallback chain. Shadow traffic evaluates a candidate without affecting users. Canary traffic exposes a small percentage of real requests before promotion.

A release gate compares quality, latency, reliability, and cost against a versioned evaluation dataset. Offline tests catch known regressions, while online A/B tests measure user or business outcomes. Statistical significance does not replace practical significance: a tiny effect can be statistically significant with a large sample and still not justify its operational cost.

