"""Pydantic schemas for request/response bodies."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models import ConcernType, ManualPriority


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


class ExpectedVsObservedItem(BaseModel):
    """Comparison of a single metric's observed value vs peer baseline."""

    metric: str
    metric_key: str
    observed: float
    expected: float
    unit: str
    deviation_z: float
    direction: str
    interpretation: str


class EntityDrillDown(BaseModel):
    """Full drill-down detail for one entity, returned by GET /api/entities/{entity_name}."""

    entity_name: str
    risk_score: float
    risk_band: str
    alert_count: int
    primary_driver: str
    component_scores: ComponentScores
    findings: list[Finding]
    peer_metrics: PeerMetrics
    expected_vs_observed: list[ExpectedVsObservedItem]


class TrendPoint(BaseModel):
    """One historical data point for entity risk trend."""

    run_id: int
    timestamp: datetime
    risk_score: float
    risk_band: str
    execution_gap: float
    negative_space: float
    anomaly: float


class EntityTrendDetail(BaseModel):
    """Trend details for a single entity across historical assessment runs."""

    entity_name: str
    points: list[TrendPoint]
    direction: str  # "improving" | "stable" | "deteriorating" | "volatile" | "insufficient_data"
    change: Optional[float] = None
    """First-to-last risk_score difference — kept for reference only; it no
    longer decides `direction` (see _compute_entity_trend), since it's blind
    to a series that dips and recovers back to its starting value."""
    volatility: Optional[float] = None
    """Population standard deviation of risk_score across the series, in
    points. None when there are fewer than two points to compute it from."""


class EntityTrendSummary(BaseModel):
    """Summary trend direction for an entity (dashboard view)."""

    entity_name: str
    direction: str


class PrioritySample(BaseModel):
    """One alert ranked for manual supervisory review by GET /api/priority-samples.

    Mirrors the dict shape returned by
    app.analytics.sample_priority.compute_sample_priority.
    """

    alert_id: str
    entity_name: str
    entity_risk_score: float
    severity: str
    created_time: datetime
    priority_score: float
    triggered_rules: list[str]
    reason: str


# ---------------------------------------------------------------------------
# Blind manual review — see app/routers/manual_review.py
# ---------------------------------------------------------------------------

class AlertEvidenceRow(BaseModel):
    """One raw alert record as shown in the blind manual-review dossier.

    Deliberately just the alert's own fields — no detector-derived value
    (no rule name, no evidence "reason" string, nothing indicating this
    particular alert was ever flagged by anything) appears here.
    """

    alert_id: str
    severity: str
    asset_type: str
    created_time: datetime
    closed_time: Optional[datetime] = None
    closure_duration_seconds: Optional[float] = None
    escalated: bool
    investigation_notes: Optional[str] = None


class EntityEvidenceAggregates(BaseModel):
    """Descriptive aggregates over one entity's own alerts only.

    Every figure here is something a human reviewer could compute themselves
    by reading the alert list above — counts, an average, a distribution.
    None of it compares this entity to any other (no peer median, no
    percentile, nothing that would reveal where this entity ranks), since
    that comparison is itself a VEIL-shaped conclusion.
    """

    total_alerts: int
    open_alerts: int
    closed_alerts: int
    avg_closure_seconds: Optional[float] = None
    escalated_count: int
    escalated_rate: float
    avg_investigation_note_length: float
    severity_distribution: dict[str, int]
    asset_type_distribution: dict[str, int]


class EntityBlindEvidence(BaseModel):
    """Response for GET /api/manual-review/{entity_name}/evidence.

    Contains raw operational evidence and self-descriptive aggregates only.
    Must never gain a risk_score, risk_band, primary_driver, component
    score, detector/rule name, finding, evidence item produced by a
    detector, priority_score, or peer-relative comparison — the blindness
    of the manual-review workflow depends on this endpoint staying that way.
    """

    entity_name: str
    alerts: list[AlertEvidenceRow]
    aggregates: EntityEvidenceAggregates


class ManualReviewCreate(BaseModel):
    """Request body for POST /api/manual-review.

    concern_type and manual_priority are strict enums (ConcernType,
    ManualPriority from app.models) — FastAPI/Pydantic reject any value
    outside them with a 422, no extra validation code needed here.
    """

    entity_name: str
    reviewer_id: Optional[str] = None
    supervisory_concern: bool
    concern_type: ConcernType
    manual_priority: ManualPriority
    manual_review_recommended: bool
    evidence_sufficient: bool
    rationale: str = Field(min_length=1)


class ManualReviewOut(BaseModel):
    """One persisted manual review, as returned by the GET endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_name: str
    created_at: datetime
    reviewer_id: Optional[str] = None
    supervisory_concern: bool
    concern_type: ConcernType
    manual_priority: ManualPriority
    manual_review_recommended: bool
    evidence_sufficient: bool
    rationale: str


class ManualReviewComparison(BaseModel):
    """Response for GET /api/manual-review/{entity_name}/comparison.

    `available` is False (with every other field null) when no review has
    ever been submitted for this entity, or when a review exists but the
    entity isn't present in the currently-loaded dataset's VEIL results
    (e.g. a fresh upload replaced it) — in both cases there is nothing real
    to compare, so nothing is fabricated in its place.
    """

    available: bool
    entity_name: str
    reason: Optional[str] = None

    review_id: Optional[int] = None
    review_created_at: Optional[datetime] = None

    manual_concern: Optional[bool] = None
    veil_concern: Optional[bool] = None
    concern_agrees: Optional[bool] = None

    manual_priority: Optional[ManualPriority] = None
    veil_risk_band: Optional[str] = None
    priority_agrees: Optional[bool] = None

    manual_review_recommended: Optional[bool] = None
    veil_prioritized: Optional[bool] = None
    recommendation_agrees: Optional[bool] = None

    overall_agreement: Optional[bool] = None


class ManualReviewMetrics(BaseModel):
    """Response for GET /api/manual-review/metrics.

    Aggregates every submitted review (not one-per-entity — a re-reviewed
    entity contributes one data point per submission, since each submission
    is itself a review event). `comparable_reviews` may be less than
    `total_reviews` when a review's entity is no longer present in the
    current dataset's VEIL results; those reviews are excluded from every
    rate below rather than counted as either agreement or disagreement.
    A rate is null (not 0.0) when its denominator is zero — an unmeasured
    rate is not the same as a measured 0%.
    """

    total_reviews: int
    comparable_reviews: int

    concern_agreement_count: int
    concern_agreement_rate: Optional[float] = None

    priority_agreement_count: int
    priority_agreement_rate: Optional[float] = None

    recommendation_agreement_count: int
    recommendation_agreement_rate: Optional[float] = None

    overall_agreement_count: int
    overall_agreement_rate: Optional[float] = None


