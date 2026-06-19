---
name: ledger-copywriter
description: Generate markdown copy from verified competitive-intelligence ledgers. Use when writer agents need to turn company facts, approved wording, source URLs, and evidence gaps into comparison pages, battlecards, sales notes, alternatives sections, ad copy, or briefs without inventing claims.
---

# Ledger Copywriter

Write from the ledger, not from memory. Treat facts as constraints.

## Workflow

1. Read `/companies.json` and relevant company fact folders.
2. Identify the requested asset, audience, tone, and favored company if any.
3. Select only claims with `status: verified` and `copy_safe: true` for public
   assertions.
4. Use `approved_wording` whenever available.
5. Draft the asset in markdown.
6. Create claims-used and avoided-claims notes.
7. Run a final claim-safety pass before writing the final draft.

## Output

Write:

- `/drafts/<scope>/draft.md`
- `/drafts/<scope>/claims-used.md`
- `/drafts/<scope>/avoided-claims.md`

## Gotchas

- Do not browse or verify new facts in the writer layer.
- Do not use `needs_review`, `conflicting`, `stale`, `rejected`, or
  `copy_safe: false` claims as public copy.
- Do not turn "not clearly documented" into "does not support."
