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


class DetectorConfiguration(BaseModel):
    """Snapshot of all named constants that affected scoring for a given run."""

    model_config = ConfigDict(from_attributes=True)

    fast_closure_threshold_seconds: int
    min_note_length: int
    min_duplicate_multiplicity: int
    template_duplicate_z_threshold: float
    fast_closure_weight: float
    no_escalation_weight: float
    template_notes_weight: float
    low_volume_z_threshold: float
    min_peers_with_severity: int
    low_volume_weight: float
    missing_severity_weight: float
    iforest_random_state: int
    iforest_contamination: float
    iforest_n_estimators: int
    weight_execution_gap: float
    weight_negative_space: float
    weight_anomaly: float
    floor_attenuation: float
    risk_band_critical_threshold: float
    risk_band_high_threshold: float
    risk_band_medium_threshold: float
    finding_summary_threshold: float


class EntityResultSnapshot(BaseModel):
    """One entity's scored result stored in an AssessmentRun's results_snapshot."""

    model_config = ConfigDict(from_attributes=True)

    entity_name: str
    risk_score: float
    risk_band: str
    execution_gap_component_score: float
    negative_space_component_score: float
    anomaly_component_score: float


class AuditRunListItem(BaseModel):
    """Response model for GET /api/audit/runs list endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    filename: str
    format: str
    rows_received: int
    rows_inserted: int
    rows_skipped: int
    entity_count: int


class AuditRunDetail(BaseModel):
    """Response model for GET /api/audit/runs/{run_id} endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    filename: str
    format: str
    rows_received: int
    rows_inserted: int
    rows_skipped: int
    entity_count: int
    data_range_start: Optional[datetime] = None
    data_range_end: Optional[datetime] = None
    detector_config: DetectorConfiguration
    results_snapshot: list[EntityResultSnapshot]


class EntityDrillDown(BaseModel):
    """Full drill-down detail for one entity, returned by GET /api/entities/{entity_name}."""

    entity_name: str
    risk_score: float
    risk_band: str
    alert_count: int
    component_scores: ComponentScores
    findings: list[Finding]
    peer_metrics: PeerMetrics
