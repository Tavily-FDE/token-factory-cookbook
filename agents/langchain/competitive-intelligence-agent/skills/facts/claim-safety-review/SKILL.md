---
name: claim-safety-review
description: Review competitive-intelligence claims for substantiation, source fit, stale facts, unsupported superlatives, fairness, comparison basis, risk level, and copy-safe approved wording before writer agents use them.
---

# Claim Safety Review

Use this before marking claims copy-safe or approving wording for later writer
agents.

## Workflow

1. Match each claim to direct source evidence.
2. Check status, freshness window, exact units, source type, evidence posture,
   source fit, and comparison basis.
3. Flag unsupported superlatives, stale pricing, broad security/compliance
   claims, benchmark claims without methodology, and absolute competitor
   limitations.
4. Rewrite risky claims into narrower approved wording or leave
   `approved_wording` empty.
5. Move unsafe claims to verification queue or keep them `copy_safe: false`.

## Evidence Calibration

- `evidence_posture: direct_fact` means the source of record directly states an
  exact operational fact.
- `evidence_posture: vendor_claim` means the company states the claim but it is
  self-reported or promotional.
- `evidence_posture: third_party_report` means the claim comes from press,
  analyst, investor, review, or database reporting.
- `evidence_posture: inference` means the claim is derived from multiple facts.

Do not use evidence posture values as `source_type`; `source_type` must remain
one of the allowed source taxonomy values.

- `source_fit: exact` means the source explicitly states the narrow claim.
- `source_fit: partial` means the source supports only part of the claim.
- `source_fit: context` means the source explains the area but does not prove the
  claim.
- `source_fit: lead_only` means the source is useful for discovery but not
  acceptable as claim evidence.

Only `source_fit: exact` can be `status: verified`. If source fit is weaker,
narrow the claim or mark it `needs_review`.

Use `confidence: high` only for current, exact source-of-record evidence with no
known conflict. Use `medium` for self-reported high-risk claims or credible
secondary reports, and `low` for weak, sparse, unclear, or inferred evidence.

`copy_safe: true` means approved wording is safe for downstream reuse without
overstating the evidence. For vendor-authored benchmarks, latency, uptime,
customer counts, compliance posture, funding/valuation, and superlatives, prefer
attributed approved wording such as "Company reports..." or "According to...".

## Safer Wording Patterns

- "not clearly documented in public docs"
- "public pricing is not listed"
- "requires custom quote"
- "best suited for"
- "centered on"
- "according to <source>"
- "as of <date_checked>"

## Output

Return reviewed claim candidates with `evidence_posture`, `source_fit`,
`status`, `confidence`, `copy_safe`, `risk_level`, `approved_wording`, and
notes updated.

## Gotchas

- Do not let useful copy outrun evidence.
- Do not use one verified claim to support a broader claim.
- Do not use sentiment claims as public attack copy.
- Do not hide competitor strengths.
