"""Lightweight structured output models for competitive-intelligence facts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ClaimCategory = Literal[
    "positioning",
    "pricing",
    "product_capability",
    "integration",
    "security_compliance",
    "benchmark",
    "latency",
    "market_momentum",
    "sentiment",
    "limitation",
    "editorial_angle",
]

SourceType = Literal[
    "official_homepage",
    "official_pricing",
    "official_docs",
    "official_blog",
    "official_changelog",
    "official_security",
    "official_benchmark",
    "public_repo",
    "review_site",
    "community_discussion",
    "news",
    "analyst",
    "secondary",
]

ClaimStatus = Literal["verified", "needs_review", "stale", "conflicting", "rejected"]
Confidence = Literal["high", "medium", "low"]
RiskLevel = Literal["low", "medium", "high"]
EvidencePosture = Literal["direct_fact", "vendor_claim", "third_party_report", "inference"]
SourceFit = Literal["exact", "partial", "context", "lead_only"]


class SourcePackEntry(BaseModel):
    """One reusable source discovered for a company."""

    model_config = ConfigDict(extra="allow")

    url: str = Field(min_length=1)
    title: str = ""
    source_type: SourceType
    use: str = Field(min_length=1)
    notes: str = ""


class ClaimCandidate(BaseModel):
    """One atomic source-backed claim candidate."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(min_length=1)
    company_id: str | None = None
    company: str = Field(min_length=1)
    category: ClaimCategory
    claim: str = Field(min_length=1)
    approved_wording: str = ""
    source_url: str = Field(min_length=1)
    source_title: str = ""
    source_type: SourceType
    date_checked: str = Field(min_length=1)
    observed_value: dict[str, Any] = Field(default_factory=dict)
    evidence_posture: EvidencePosture = "direct_fact"
    source_fit: SourceFit = "exact"
    scope: str = ""
    confidence: Confidence
    freshness_days: int = Field(ge=1)
    status: ClaimStatus
    copy_safe: bool = False
    risk_level: RiskLevel
    notes: str = ""


class ResearchTaskResult(BaseModel):
    """Structured result returned by one general-purpose fact task."""

    model_config = ConfigDict(extra="allow")

    company: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    source_pack: list[SourcePackEntry] = Field(default_factory=list)
    claim_candidates: list[ClaimCandidate] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    notes: str = ""


class CompanyFactsSummary(BaseModel):
    """Short summary for a company's fact-gathering run."""

    model_config = ConfigDict(extra="allow")

    company_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    category: str = ""
    sources_count: int = 0
    claims_count: int = 0
    needs_review_count: int = 0
    evidence_gaps: list[str] = Field(default_factory=list)
    run_summary: str = ""


class ClaimUsed(BaseModel):
    """One ledger claim used in generated copy."""

    model_config = ConfigDict(extra="allow")

    claim_id: str = Field(min_length=1)
    company: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    wording_used: str = Field(min_length=1)
    usage_context: str = ""


class AvoidedClaim(BaseModel):
    """One claim or claim area intentionally avoided by the writer."""

    model_config = ConfigDict(extra="allow")

    claim_id: str | None = None
    company: str = ""
    claim: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    source_url: str = ""


class WriterTaskResult(BaseModel):
    """Structured result returned by one writer subtask."""

    model_config = ConfigDict(extra="allow")

    asset_type: str = ""
    draft_markdown: str = ""
    claims_used: list[ClaimUsed] = Field(default_factory=list)
    avoided_claims: list[AvoidedClaim] = Field(default_factory=list)
    notes: str = ""


class DraftSummary(BaseModel):
    """Summary of a completed writer run."""

    model_config = ConfigDict(extra="allow")

    scope: str = Field(min_length=1)
    guidance: str = ""
    draft_path: str = ""
    claims_used_count: int = 0
    avoided_claims_count: int = 0
    run_summary: str = ""
