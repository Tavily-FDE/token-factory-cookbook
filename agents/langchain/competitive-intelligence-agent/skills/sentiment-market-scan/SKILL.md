---
name: sentiment-market-scan
description: Research cautious public sentiment and dated market momentum for competitive-intelligence ledgers using reviews, communities, repos, news, launches, funding, partnerships, customer signals, and changelogs.
---

# Sentiment Market Scan

Use this for public perception and recent market movement. Keep claims cautious.

## Workflow

1. Search recent company activity: launches, pricing changes, funding,
   partnerships, acquisitions, executive changes, customer wins, changelog
   signals, and roadmap signals.
2. Search public sentiment: Reddit, Hacker News, G2, Capterra, Product Hunt,
   Trustpilot, GitHub issues/discussions, and category communities.
3. Look for repeated themes, not isolated comments.
4. Separate developer/practitioner sentiment from buyer/admin sentiment.
5. Mark sentiment claims `copy_safe: false` by default.

## Tavily Guidance

- Use `time_range` for recent market-momentum queries when appropriate.
- Use `include_domains` for known community/review sources.
- Extract pages when snippets are insufficient, but avoid long user-generated
  quotes.

## Output

Return `market_momentum` and `sentiment` claim candidates with source URLs,
audience, confidence, and notes.

## Gotchas

- Do not treat one viral comment as market sentiment.
- Do not use community claims for product facts when official docs exist.
- Do not overstate confidence when review volume is sparse.
- Use market momentum sources for dated events, not broad positioning claims.
