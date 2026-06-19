"""Runtime-side validation models for competitive-intelligence facts.

Subagents persist their work to files; they no longer return structured
Pydantic results. The only model kept here is `ClaimCandidate`, used by the
CLI to validate `/companies/<uuid>/facts.yaml` entries at run end.
"""

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


class ClaimCandidate(BaseModel):
    """One atomic source-backed claim, validated from persisted `facts.yaml`."""

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
