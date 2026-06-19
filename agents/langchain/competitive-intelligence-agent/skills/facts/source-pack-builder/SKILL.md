---
name: source-pack-builder
description: Build reusable source packs for a company before claim-ledger creation. Use when the fact agent needs official pages, docs, pricing, trust/security, changelog, benchmarks, integrations, repos, sentiment sources, or market/news sources for competitive research.
---

# Source Pack Builder

Build the source map that later claim work can reuse. Source packs are not
claims; they describe what each source can support.

## Workflow

1. Define company, domain, category, and required research lanes.
2. Discover official surfaces first: homepage, product pages, docs, API
   reference, pricing, changelog, blog, trust/security, privacy/legal, status,
   SDKs/repos, integrations, customers, benchmarks.
3. Map official domains before broad extraction.
4. Extract high-value pages after mapping.
5. Add secondary sources only for sentiment, market momentum, or source
   discovery.
6. Record mapped surfaces, read pages, and unreviewed official areas.

## Tavily Guidance

- Use `tavily_search` to find official domains and important surfaces.
- Use `tavily_map` with `allow_external=false`, small depth, and relevant path
  filters where possible.
- Use `tavily_extract` for known high-value URLs.
- Use `tavily_crawl` only for bounded official clusters with an explicit limit.

## Source Types

Use: `official_homepage`, `official_pricing`, `official_docs`,
`official_blog`, `official_changelog`, `official_security`,
`official_benchmark`, `public_repo`, `review_site`, `community_discussion`,
`news`, `analyst`, `secondary`.

## Output

Return source entries and evidence gaps:

```markdown
source_pack:
  - url: <url>
    title: <title>
    source_type: <source_type>
    use: <what this source supports>
    notes: <coverage caveat>

evidence_gaps:
  - <missing official surface or weak coverage>
```

## Gotchas

- Do not treat a homepage as evidence for pricing, security, or benchmarks.
- Do not crawl a whole site before mapping it.
- For comparisons, seek equivalent source surfaces for each company.
