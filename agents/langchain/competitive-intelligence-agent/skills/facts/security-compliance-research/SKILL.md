---
name: security-compliance-research
description: Research trust, security, privacy, compliance, data handling, retention, model-training policy, enterprise controls, SLAs, and safeguards for source-backed competitive-intelligence claim ledgers.
---

# Security Compliance Research

Security and compliance claims are high risk. Use exact source-backed wording.

## Workflow

1. Search official trust, security, privacy, legal, DPA, docs, enterprise, and
   status pages first.
2. Extract official pages before relying on snippets.
3. Capture certifications, controls, data use, retention, model-training policy,
   enterprise features, SLAs, and safeguards.
4. If a control is not publicly documented, say "not clearly documented in
   public materials" and mark `needs_review`.
5. Default `risk_level: high`; use `freshness_days: 90`.

## Tavily Guidance

- Queries: `"<company>" SOC 2`, `"<company>" security`, `"<company>" trust center`,
  `"<company>" data retention`, `"<company>" privacy`, `"<company>" SLA`.
- Use `tavily_extract` on official trust/security/legal pages.
- Use secondary sources only when the official source is inaccessible, and mark
  risky claims `needs_review`.

## Output

Return security/compliance claim candidates plus evidence gaps.

## Gotchas

- Do not claim a competitor lacks a control unless an official source says so.
- Distinguish "does not train on customer data" from zero data retention.
- Distinguish anti-bot protection from authenticated login-wall access.
- Do not mark broad security claims copy-safe.
