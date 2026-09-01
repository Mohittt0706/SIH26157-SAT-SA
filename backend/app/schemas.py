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
