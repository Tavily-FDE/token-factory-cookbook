---
name: claim-ledger-builder
description: Convert source packs, extracted pages, and research notes into atomic competitive-intelligence claim ledgers with source URLs, date checked, confidence, freshness, status, copy safety, approved wording, and verification queues.
---

# Claim Ledger Builder

Turn evidence into durable claims that later writer agents can safely use.

## Workflow

1. Start from source packs, extracted pages, and research task results.
2. Split compound statements into one fact per claim.
3. Attach source URL, source title, source type, date checked, scope, confidence,
   freshness, risk, and notes.
4. Prefer the strongest primary source when several sources support the same
   fact.
5. Preserve conflicts and mark them `conflicting`.
6. Mark weak, implicit, stale, secondary-for-risky, or incomplete claims
   `needs_review` or `stale`.
7. Put weak, risky, stale, conflicting, and rejected claims into the company
   verification queue.

## Claim Categories

Use: `positioning`, `pricing`, `product_capability`, `integration`,
`security_compliance`, `benchmark`, `latency`, `market_momentum`, `sentiment`,
`limitation`, `editorial_angle`.

## Facts YAML Schema

Write `/companies/<company_uuid>/facts.yaml` as a YAML list. Keep each record
atomic: one fact, one best source, one status.

```yaml
- id: <company-slug>.<category>.<short-id>
  company_id: "<uuid-from-companies-json>"
  company: <Company>
  category: positioning|pricing|product_capability|integration|security_compliance|benchmark|latency|market_momentum|sentiment|limitation|editorial_angle
  claim: "<one atomic fact>"
  approved_wording: "<copy-safe wording or empty string>"
  source_url: "<url>"
  source_title: "<page title>"
  source_type: official_homepage|official_pricing|official_docs|official_blog|official_changelog|official_security|official_benchmark|public_repo|review_site|community_discussion|news|analyst|secondary
  date_checked: "<YYYY-MM-DD>"
  observed_value: {}
  scope: "<plan/product/endpoint/control/event/audience context>"
  confidence: high|medium|low
  freshness_days: 30|60|90|180
  status: verified|needs_review|stale|conflicting|rejected
  copy_safe: true|false
  risk_level: low|medium|high
  notes: "<caveats and review rationale>"
```

Required fields for every record: `id`, `company_id`, `company`, `category`,
`claim`, `source_url`, `source_title`, `source_type`, `date_checked`,
`observed_value`, `confidence`, `status`, `copy_safe`, `risk_level`, and
`notes`.

## Freshness Defaults

- Pricing: 30 days.
- Benchmarks and latency: 60 days.
- Product capabilities: 90 days.
- Security/compliance: 90 days.
- Market momentum: 90 days.
- Sentiment: 90 days and usually `copy_safe: false`.
- Positioning: 180 days.

## Gotchas

- Do not translate units unless the source defines the conversion.
- Do not cite a source that supports only a nearby or weaker claim.
- Do not mark unsupported superlatives copy-safe.
- Do not remove competitor strengths; the fact layer is neutral.
