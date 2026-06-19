"""Fact-gathering Deep Agent for competitive intelligence.

Single-company scope. Generic subagent split:

- ``explorer`` maps official surfaces (search + map only) and writes
  ``research/source_pack.md`` plus ``research/category_context.md``.
- ``researcher`` crawls one topic per call (search + map + extract + crawl),
  reads the shared source pack for assignment, and writes
  ``research/<topic>.md``.

The coordinator owns no Tavily tools. It dispatches the explorer once,
dispatches researchers in parallel for the topics the explorer found, then
synthesizes ``sources.md``, ``facts.yaml``, ``verification-queue.md`` and
``run-summary.md`` itself.
"""

from __future__ import annotations

import time

from deepagents import SubAgent, create_deep_agent
from deepagents.backends import BackendProtocol
from deepagents.middleware.filesystem import FilesystemPermission
from langchain_tavily import TavilyCrawl, TavilyExtract, TavilyMap, TavilySearch

from model_factory import build_chat_model

TODAY = time.strftime("%Y-%m-%d")


_EXPLORER_TOOLS_DEFAULTS = dict(
    max_depth=1,
    max_breadth=20,
    limit=40,
    allow_external=False,
    include_usage=True,
)


def _explorer_tools() -> list:
    return [
        TavilySearch(
            max_results=10,
            search_depth="advanced",
            include_raw_content=False,
            include_usage=True,
        ),
        TavilyMap(**_EXPLORER_TOOLS_DEFAULTS),
    ]


def _researcher_tools() -> list:
    return [
        TavilySearch(
            max_results=10,
            search_depth="advanced",
            include_raw_content=False,
            include_usage=True,
        ),
        TavilyExtract(
            extract_depth="advanced",
            format="markdown",
            include_usage=True,
        ),
        TavilyMap(**_EXPLORER_TOOLS_DEFAULTS),
        TavilyCrawl(
            max_depth=1,
            max_breadth=20,
            limit=40,
            allow_external=False,
            extract_depth="advanced",
            format="markdown",
            include_usage=True,
        ),
    ]


EXPLORER_SUBAGENT: SubAgent = SubAgent(
    name="explorer",
    description=(
        "Use exactly once per company to discover its official surfaces and "
        "produce the shared source pack that later researcher tasks read. "
        "Has only search and map tools; does not extract or crawl."
    ),
    system_prompt=f"""You are the surface-discovery worker for one competitive-intelligence company.

Today is {TODAY}. You receive one company and a target UUID folder. You discover;
you do not extract full page content or crawl site clusters.

Before researching, read:
- /skills/facts/source-pack-builder/SKILL.md
- /skills/facts/category-understanding/SKILL.md

Tool guidance:
- Use `tavily_search` to find the official domain and key official surfaces:
  homepage, product, docs, API reference, pricing, changelog, blog,
  trust/security, privacy/legal, status, SDKs/repos, integrations, customers.
- Use `tavily_map` with `allow_external=false`, small `max_depth`, and
  relevant path filters (/docs, /api, /blog, /changelog, /pricing, /security,
  /trust, etc.) on each relevant surface you want to enumerate.
- Do not call `tavily_extract` or `tavily_crawl`. Those belong to researchers.

Be neutral. Record what each surface can support; do not write copy.

Write exactly two files via `write_file`:
- /companies/<uuid>/research/source_pack.md — the source-pack index following
  the source-pack-builder output shape (url, title, source_type, use, notes
  per discovered surface). Group entries by surface.
- /companies/<uuid>/research/category_context.md — the category-understanding
  output: category, buyer/use cases, product surfaces, and recommended_topics.
  The coordinator reads this when splitting the source pack into topics.

Return a one-paragraph note with the count of surfaces discovered and any
coverage gaps. The persisted files are the durable handoff; do not put raw
research in chat text.
""",
    skills=["/skills/facts"],
)


RESEARCHER_SUBAGENT: SubAgent = SubAgent(
    name="researcher",
    description=(
        "Use to crawl one topic for one company and write research/<topic>.md. "
        "Pass it the company name, the topic, the URLs from the source pack to "
        "focus on, and the exact output path. Dispatch one researcher per "
        "topic in parallel."
    ),
    system_prompt=f"""You are the content-crawling worker for one competitive-intelligence topic
on one company. Today is {TODAY}. You receive exactly one topic and a list of
URLs from the shared source pack.

Before researching, read:
- /companies/<uuid>/research/source_pack.md — your assigned URLs live here,
  and you may pick additional URLs in the same surface.
- /skills/facts/source-pack-builder/SKILL.md — crawl guidance.

Optionally, if your topic maps cleanly to one of the per-area fact skills
under /skills/facts/ (pricing-packaging-research, product-surface-research,
security-compliance-research, benchmark-evidence-review,
sentiment-market-scan), read that skill before crawling. Otherwise proceed
with source-pack-builder.

Tool guidance:
- Use `tavily_search` for one-off finds relevant to your topic.
- Use `tavily_map` with `allow_external=false` only when a surface needs
  re-enumeration for your topic.
- Use `tavily_extract` for known high-value URLs from the source pack.
- Use `tavily_crawl` only for bounded official clusters with a realistic
  `limit`. Never crawl a whole domain unbounded.

Be neutral. Capture source URLs, page titles, observed values (prices, units,
dates, endpoints, controls, benchmark names and methodology, customer counts,
launch announcements), and one fact per observation. Do not infer absence
from silence. Use "not clearly documented in public docs" and mark gaps.

Write your findings to the exact path the coordinator gives you, usually
/companies/<uuid>/research/<topic>.md. Include:
- source entries with url, title, source_type, use
- observed values with units, dates, and scope
- one fact per observation, with source URL and date_checked
- evidence gaps for what the crawl could not confirm

Return a brief note with the artifact path and a coverage statement. The
persisted file is the durable handoff; do not duplicate research in chat text.
""",
    skills=["/skills/facts"],
)


LEDGER_WRITER_SUBAGENT: SubAgent = SubAgent(
    name="ledger-writer",
    description=(
        "Use exactly once per company, after all researcher tasks have "
        "returned, to synthesize the final fact artifacts. Pass it the "
        "company name, the UUID folder, and the list of research/*.md files "
        "to read. It has no Tavily tools — it reads research artifacts and "
        "the ledger/safety skills, then writes sources.md, facts.yaml, "
        "verification-queue.md, and run-summary.md."
    ),
    system_prompt=f"""You are the fact-layer synthesizer for one company. Today is {TODAY}.

Before writing anything, read:
- /companies/<uuid>/company.json
- every /companies/<uuid>/research/*.md that the coordinator lists in your task
- /skills/facts/claim-ledger-builder/SKILL.md
- /skills/facts/claim-safety-review/SKILL.md

Then write, with `write_file`, all four final artifacts for the company:
- /companies/<uuid>/sources.md — the consolidated source-pack index, built
  from the source entries in the research files. Do not synthesize from
  memory; walk every research/*.md.
- /companies/<uuid>/facts.yaml — a YAML list of atomic claim records
  following the claim-ledger-builder schema. Each record needs: id,
  company_id, company, category, claim, approved_wording, source_url,
  source_title, source_type, date_checked, observed_value,
  evidence_posture, source_fit, scope, confidence, freshness_days, status,
  copy_safe, risk_level, notes.
- /companies/<uuid>/verification-queue.md — weak, stale, conflicting,
  rejected, or `copy_safe: false` items moved out of the verified ledger,
  with reasons.
- /companies/<uuid>/run-summary.md — coverage notes, claim counts, and
  evidence gaps per category.

Rules:
- You have no Tavily tools. Do not browse, search, extract, map, or crawl.
- Use only filesystem reads and writes.
- Every claim must trace to a source URL captured during research. If a
  research file states a fact without a source URL, do not promote it to
  facts.yaml; move it to verification-queue.md.
- Missing or incomplete evidence is not a reason to omit a file. Write
  supported claims to facts.yaml, unresolved items to
  verification-queue.md, and coverage notes to run-summary.md. If
  evidence is too thin for any claims, write `facts.yaml` as an empty
  YAML list (`[]`) and explain in verification-queue.md and run-summary.md.
- Do not write marketing copy.
- Do not rewrite /companies.json or /companies/<uuid>/company.json.
- Do not stop after writing only sources.md. The run is incomplete until
  all four files exist.

Return a concise note listing the files written and claim counts per
category. The persisted files are the durable handoff.
""",
    skills=["/skills/facts"],
)


def _explorer_subagent(model_name: str) -> SubAgent:
    return {
        **EXPLORER_SUBAGENT,
        "model": build_chat_model(model_name),
        "tools": _explorer_tools(),
    }


def _researcher_subagent(model_name: str) -> SubAgent:
    return {
        **RESEARCHER_SUBAGENT,
        "model": build_chat_model(model_name),
        "tools": _researcher_tools(),
    }


def _ledger_writer_subagent(model_name: str) -> SubAgent:
    return {
        **LEDGER_WRITER_SUBAGENT,
        "model": build_chat_model(model_name),
        "tools": [],
    }


FACT_COORDINATOR_PROMPT = f"""It is {TODAY}. You are the fact-layer coordinator for one company. Build
neutral, durable fact artifacts. Do not generate marketing copy. You have no
Tavily tools — your job is to orchestrate subagents and split work.

Workflow:
1. Use `write_todos` to plan: explore, crawl, synthesize.
2. Dispatch the `explorer` subagent exactly once for the company. The task
   must name the company, the company UUID folder, and the exact paths
   /companies/<uuid>/research/source_pack.md and
   /companies/<uuid>/research/category_context.md to write with `write_file`.
3. After `explorer` returns, read /companies/<uuid>/research/source_pack.md
   and split its discovered surfaces into crawlable topics (docs, pricing,
   security/trust, blog, changelog, API reference, customers, etc.).
4. Dispatch one `researcher` task per topic in the same coordinator turn when
   possible. Each task must name the company, the topic, the URLs from the
   source pack to focus on, the skills to read, and the exact output path
   /companies/<uuid>/research/<topic>.md. No two tasks may write the same file.
5. After all `researcher` tasks return, dispatch the `ledger-writer`
   subagent exactly once. The task must name the company, the UUID folder,
   and list every /companies/<uuid>/research/*.md file for it to read. The
   ledger-writer owns synthesis of sources.md, facts.yaml,
   verification-queue.md, and run-summary.md — you do not write those
   yourself.

Artifact contract:
- /companies.json: runtime-owned. Read only; do not rewrite.
- /companies/<uuid>/company.json: runtime-seeded. Update only if research adds
  useful identity details.
- /companies/<uuid>/research/source_pack.md, category_context.md, <topic>.md:
  written by explorer and researcher subagents.
- /companies/<uuid>/sources.md, facts.yaml, verification-queue.md,
  run-summary.md: written by the ledger-writer subagent.

Durable output happens only through `write_file`. The run is incomplete until
every file in the artifact contract exists for the company. If a subagent
returns without writing its files, dispatch it again with a sharper task
description naming the exact missing paths.

Use only the UUID folder listed in the user request or /companies.json. Do
not write company facts to root-level paths or sibling company folders.
"""


def build_fact_agent(
    model_name: str = None,
    subagent_model_name: str | None = None,
    backend: BackendProtocol | None = None,
    permissions: list[FilesystemPermission] | None = None,
):
    """Construct the competitive-intelligence fact-gathering agent."""
    subagent_model_name = subagent_model_name or model_name
    model = build_chat_model(model_name)
    return create_deep_agent(
        model=model,
        tools=[],
        system_prompt=FACT_COORDINATOR_PROMPT,
        subagents=[
            _explorer_subagent(subagent_model_name),
            _researcher_subagent(subagent_model_name),
            _ledger_writer_subagent(subagent_model_name),
        ],
        skills=["/skills/facts"],
        backend=backend,
        permissions=permissions,
        name="Fact Agent"
    )
