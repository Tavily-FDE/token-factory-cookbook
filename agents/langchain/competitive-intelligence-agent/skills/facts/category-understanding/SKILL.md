---
name: category-understanding
description: Identify a company's product category, buyer/use case, product surface, likely research lanes, and source-discovery priorities before competitive-intelligence fact gathering. Use when the fact agent receives a company name or scope and needs initial problem-space understanding without writing copy.
---

# Category Understanding

Use this skill before lane-specific research. Produce neutral research framing,
not positioning copy.

## Workflow

1. Identify the company and likely official domain.
2. Determine the product category and adjacent category labels.
3. Identify likely buyers, users, and technical evaluators.
4. List product surfaces that matter for research: API, dashboard, SDKs, docs,
   integrations, security/trust, pricing, benchmarks, changelog, blog.
5. Select research lanes that are useful for this scope.
6. Record ambiguity as evidence gaps instead of guessing.

## Tavily Guidance

- Use `tavily_search` for homepage, docs, product overview, and category terms.
- Prefer official pages for category and product-surface claims.
- Use secondary sources only to understand market/category language, not as proof
  for product or pricing facts.

## Output

Return:

```markdown
category_context:
  company: <Company>
  likely_domain: <domain or unknown>
  category: <neutral category>
  buyer_use_cases:
    - <use case>
  product_surfaces:
    - <surface>
  recommended_lanes:
    - source_pack
    - pricing
    - product_capabilities
  evidence_gaps:
    - <ambiguity>
```

## Gotchas

- Do not add competitors to the research scope unless the user asked for them.
- Do not turn category framing into copy or differentiation.
- Do not overfit to a homepage tagline when docs indicate a narrower product.
