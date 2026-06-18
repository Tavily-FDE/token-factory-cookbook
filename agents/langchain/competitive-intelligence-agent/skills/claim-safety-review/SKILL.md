---
name: claim-safety-review
description: Review competitive-intelligence claims for substantiation, source fit, stale facts, unsupported superlatives, fairness, comparison basis, risk level, and copy-safe approved wording before writer agents use them.
---

# Claim Safety Review

Use this before marking claims copy-safe or approving wording for later writer
agents.

## Workflow

1. Match each claim to direct source evidence.
2. Check status, freshness window, exact units, source type, and comparison
   basis.
3. Flag unsupported superlatives, stale pricing, broad security/compliance
   claims, benchmark claims without methodology, and absolute competitor
   limitations.
4. Rewrite risky claims into narrower approved wording or leave
   `approved_wording` empty.
5. Move unsafe claims to verification queue or keep them `copy_safe: false`.

## Safer Wording Patterns

- "not clearly documented in public docs"
- "public pricing is not listed"
- "requires custom quote"
- "best suited for"
- "centered on"
- "according to <source>"
- "as of <date_checked>"

## Output

Return reviewed claim candidates with `status`, `copy_safe`, `risk_level`,
`approved_wording`, and notes updated.

## Gotchas

- Do not let useful copy outrun evidence.
- Do not use one verified claim to support a broader claim.
- Do not use sentiment claims as public attack copy.
- Do not hide competitor strengths.
