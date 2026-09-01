"""Pydantic schemas for request/response bodies."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AlertBase(BaseModel):
    """Fields shared by every Alert representation, matching the CSV schema."""

    alert_id: str
    entity_name: str
    severity: str
    created_time: datetime
    closed_time: Optional[datetime] = None
    escalated: bool
    investigation_notes: Optional[str] = None
    asset_type: str


class AlertOut(AlertBase):
    """Alert as returned by the API, including the derived closure time."""

    model_config = ConfigDict(from_attributes=True)

    closure_seconds: Optional[float] = None


class EntityRiskScore(BaseModel):
    """Per-entity risk output combining all detectors into one weighted score."""

    model_config = ConfigDict(from_attributes=True)

    entity_name: str
    risk_score: float
    execution_gap_score: float
    negative_space_score: float
    anomaly_score: float
    flags: list[str]


class RiskScoreSummary(BaseModel):
    """One row of the GET /api/risk-scores dashboard list."""

    entity_name: str
    risk_score: float
    risk_band: str
    alert_count: int
    primary_driver: str
    findings_summary: list[str]


class EvidenceItem(BaseModel):
    """One piece of concrete evidence — a specific alert or feature deviation."""

    detail: str
    reason: str


class Finding(BaseModel):
    """One detector rule that fired for an entity, with its supporting evidence."""

    rule: str
    detector: str
    description: str
    evidence_count: int
    evidence: list[EvidenceItem]


class PeerMetricFloat(BaseModel):
    """An entity's value for a metric versus its peer median (float-valued metric)."""

    entity: float
    peer_median: float


class PeerMetricInt(BaseModel):
    """An entity's value for a metric versus its peer median (integer-valued metric)."""

    entity: int
    peer_median: float


class PeerMetrics(BaseModel):
    """The peer-comparison metrics shown on the drill-down page."""

    avg_closure_seconds: PeerMetricFloat
    escalation_rate: PeerMetricFloat
    avg_note_length: PeerMetricFloat
    alert_count: PeerMetricInt


class ComponentScores(BaseModel):
    """Raw 0.0-1.0 score from each of the three detectors."""

    execution_gap: float
    negative_space: float
    anomaly: float


class EntityDrillDown(BaseModel):
    """Full drill-down detail for one entity, returned by GET /api/entities/{entity_name}."""

    entity_name: str
    risk_score: float
    risk_band: str
    alert_count: int
    component_scores: ComponentScores
    findings: list[Finding]
    peer_metrics: PeerMetrics
