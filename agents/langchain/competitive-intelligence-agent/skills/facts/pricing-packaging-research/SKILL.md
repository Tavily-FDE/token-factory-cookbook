---
name: pricing-packaging-research
description: Research competitor pricing, packaging, free tiers, trials, credits, seats, usage units, add-ons, billing cadence, limits, and enterprise quote language. Use for pricing claim candidates in fact ledgers, not for pricing copy.
---

# Pricing Packaging Research

Pricing is high-risk and changes often. Treat it as exact evidence.

## Workflow

1. Search for official pricing and docs first.
2. Extract pricing pages with `extract_depth="advanced"` when cards, tables,
   calculators, or FAQ sections matter.
3. Check docs for usage meters, credits, request limits, overages, endpoint
   costs, seats, add-ons, and enterprise terms.
4. Capture plan names, prices, billing cadence, free tier/trial, included usage,
   overage terms, enterprise/custom quote language, and caveats.
5. Create atomic pricing claims with `freshness_days: 30`.

## Tavily Guidance

- Queries: `"<company>" pricing`, `site:<domain> pricing`, `"<company>" API credits`,
  `"<company>" enterprise pricing`, `"<company>" rate limits`.
- Use `tavily_extract` for official pages before relying on snippets.
- Use third-party pricing summaries only as `needs_review` leads.

## Output

Return claim candidates plus evidence gaps. Pricing claims should usually use
`risk_level: medium` or `high`; use `copy_safe: true` only for exact, narrow,
officially supported wording.

## Gotchas

- Do not convert credits to pages, requests, documents, or tokens unless the
  source defines the conversion.
- Do not compare monthly and annual billing without labeling cadence.
- Do not imply pay-as-you-go exists unless public docs say so.
- Do not compare entry price without included usage.
