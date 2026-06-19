---
name: benchmark-evidence-review
description: Verify benchmark, leaderboard, latency, quality, accuracy, fastest, best, SOTA, and number-one claims for competitive-intelligence ledgers, including methodology, metric, date, scope, and comparability.
---

# Benchmark Evidence Review

Benchmarks are high-risk because metrics are easy to quote without scope.

## Workflow

1. Find the original benchmark or latency source.
2. Extract the source and capture benchmark name, metric, score, date, task,
   method, sample size if available, compared systems, and limitations.
3. Separate raw benchmark result claims from interpretation.
4. Mark benchmark and latency claims `freshness_days: 60`.
5. Mark `copy_safe: true` only when wording is narrow and methodology is clear.

## Tavily Guidance

- Search for the original source before citing summaries.
- Use `tavily_extract` for benchmark pages, reports, docs, and changelogs.
- Use secondary coverage only as leads unless it contains the original data.

## Output

Return benchmark or latency claim candidates, methodology notes, and evidence
gaps.

## Gotchas

- Do not compare scores across different tasks or methods.
- Do not call something "SOTA" unless the source defines that claim.
- Do not compare p50 latency to p95 latency.
- Do not generalize one endpoint latency to all workflows.
- Mark vendor charts without methodology `needs_review`.
