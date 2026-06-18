---
name: product-surface-research
description: Research product surfaces, APIs, endpoints, SDKs, integrations, workflow coverage, docs, changelogs, supported modes, public limits, and documented capabilities for competitive-intelligence fact ledgers.
---

# Product Surface Research

Map what the product actually does from official product pages, docs, API
references, repos, and changelogs.

## Workflow

1. Identify docs, API reference, SDK repos, changelog, integration pages, and
   product overview pages.
2. Map official docs domains to find relevant URL clusters.
3. Extract endpoint and parameter pages when details matter.
4. Capture APIs, endpoints, workflows, supported inputs/outputs, SDKs,
   integrations, limits, rate limits, enterprise-only features, and documented
   gaps.
5. Turn findings into atomic `product_capability`, `integration`, or
   `limitation` claims.

## Tavily Guidance

- Use `tavily_map` before broad docs crawling.
- Use bounded `tavily_crawl` only when a docs cluster jointly defines a feature.
- Use `tavily_extract` for exact endpoint, parameter, and integration details.

## Output

Return capability claim candidates with exact URLs, source titles, source type,
scope, confidence, and evidence gaps.

## Gotchas

- Do not confuse search, scrape, crawl, extract, map, and research.
- Do not confuse generic JSON API output with custom schema extraction.
- Do not claim absence from missing docs; use "not clearly documented in public
  docs" and mark `needs_review`.
- Do not cite marketing pages for endpoint details when docs exist.
