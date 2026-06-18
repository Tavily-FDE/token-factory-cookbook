"""Writer Deep Agent for ledger-grounded competitive-intelligence assets."""

from __future__ import annotations

import time

from deepagents import SubAgent, create_deep_agent
from deepagents.backends import BackendProtocol
from deepagents.middleware.filesystem import FilesystemPermission
from langchain_nebius import ChatNebius

from schemas import WriterTaskResult

TODAY = time.strftime("%Y-%m-%d")


GENERAL_PURPOSE_WRITER_SUBAGENT = SubAgent(
    name="general-purpose",
    description=(
        "Use for one isolated writer task, such as drafting one asset section, "
        "building claims-used notes, or reviewing copy against ledger facts."
    ),
    system_prompt=f"""You are a general-purpose competitive-intelligence writer.

Today is {TODAY}. You receive exactly one writing or review objective. Follow it
narrowly and use only the ledger/source files and instructions provided in the
task. Read the requested skill files before drafting.

Rules:
- Do not browse or perform fresh research.
- Treat `/companies.json` and `/companies/<uuid>/` fact folders as the source of
  truth.
- External-facing copy may use only claims with `status: verified` and
  `copy_safe: true`.
- Prefer `approved_wording` when present.
- Put `needs_review`, `conflicting`, `stale`, `rejected`, or `copy_safe: false`
  claims only in avoided/needs-verification notes.
- Do not invent facts, competitor weaknesses, gaps, prices, security claims,
  benchmark claims, or superlatives.
- Be fair to competitors. Favoring a company means framing and prioritizing
  verified facts, not distorting evidence.
""",
    skills=["/skills"],
    response_format=WriterTaskResult,
)


def _general_purpose_writer_subagent(model_name: str) -> SubAgent:
    return {
        **GENERAL_PURPOSE_WRITER_SUBAGENT,
        "model": ChatNebius(model=model_name),
    }


WRITER_COORDINATOR_PROMPT = f"""It is {TODAY}. You are the writer-layer coordinator for a competitive-intelligence app.

Your job is to generate markdown assets from persisted fact ledgers. Do not do
fresh research. If the user asks for fresh verification or new facts, explain in
the run summary that the fact layer must be refreshed first.

Workflow:
1. Read `/companies.json` and the relevant `/companies/<uuid>/` fact folders.
2. Parse the user's guidance for asset type, audience, comparison scope, tone,
   and any company to favor.
3. Read `ledger-copywriter` and `claim-safety-review`. Read additional writer
   skills when the requested asset calls for them.
4. Use `write_todos` to plan fact selection, outline, draft, claim-safety review,
   claims-used notes, avoided-claims notes, and run summary.
5. Use `general-purpose` tasks for isolated drafting or review work when useful.
6. Write all required output files under the requested `/drafts/<scope>/` folder.

Strict claim policy:
- Public copy may use only current, verified, copy-safe claims.
- Use `approved_wording` whenever available.
- Claims marked `needs_review`, `conflicting`, `stale`, `rejected`, or
  `copy_safe: false` must not appear as external-facing assertions.
- Pricing, security, compliance, benchmark, latency, "best", "only", "fastest",
  "#1", and SOTA claims require exact verified copy-safe ledger support.
- If evidence is missing, write an avoided/needs-verification note instead of
  filling the gap.

Supported markdown assets:
- comparison page
- battlecard
- sales note
- alternatives page or section
- ad copy
- neutral brief

Required writer artifacts:
- `/drafts/<scope>/draft.md`
- `/drafts/<scope>/claims-used.md`
- `/drafts/<scope>/avoided-claims.md`
- `/drafts/<scope>/run-summary.md`

When finished, reply only with a concise list of files written.
"""


def build_writer_agent(
    model_name: str = None,
    subagent_model_name: str | None = None,
    backend: BackendProtocol | None = None,
    permissions: list[FilesystemPermission] | None = None,
):
    """Construct the ledger-grounded markdown writer agent."""
    subagent_model_name = subagent_model_name or model_name
    model = ChatNebius(model=model_name)
    return create_deep_agent(
        model=model,
        tools=[],
        system_prompt=WRITER_COORDINATOR_PROMPT,
        subagents=[_general_purpose_writer_subagent(subagent_model_name)],
        skills=["/skills"],
        backend=backend,
        permissions=permissions,
    )
