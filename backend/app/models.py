"""ORM models for SAT-SA — the SOC alert table."""

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Alert(Base):
    """A single SOC alert/case record ingested from a company's CSV export.

    Maps directly to the CSV schema documented in project.md:
    alert_id, entity_name, severity, created_time, closed_time, escalated,
    investigation_notes, asset_type.
    """

    __tablename__ = "alerts"

    # alert_id is only unique *within* one company's export — each company's
    # CSV restarts its own alert_id series, so two different entities can
    # legitimately share the same alert_id. The real natural key is the pair
    # (entity_name, alert_id); a composite primary key enforces that at the
    # DB level instead of silently colliding across entities.
    alert_id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_name: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    severity: Mapped[str] = mapped_column(String)
    created_time: Mapped[datetime] = mapped_column(DateTime)
    closed_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean)
    investigation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    asset_type: Mapped[str] = mapped_column(String)

    @property
    def closure_seconds(self) -> Optional[float]:
        """Seconds between created_time and closed_time, or None if still open."""
        if self.closed_time is None:
            return None
        return (self.closed_time - self.created_time).total_seconds()


class AssessmentRun(Base):
    """Persistent audit record for a SAT-SA assessment run.

    Stores a historical snapshot of each upload so that a supervisor can
    verify the configuration and data that produced the risk scores for
    that run, independently of the current alerts table.
    """

    __tablename__ = "assessment_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    source_filename: Mapped[str] = mapped_column(String, nullable=False)
    source_format: Mapped[str] = mapped_column(String, nullable=False)
    rows_received: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_inserted: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_skipped: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_count: Mapped[int] = mapped_column(Integer, nullable=False)
    data_range_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    data_range_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    detector_config: Mapped[str] = mapped_column(Text, nullable=False)
    results_snapshot: Mapped[str] = mapped_column(Text, nullable=False)


class ConcernType(str, enum.Enum):
    """A manual reviewer's classification of what, if anything, concerns them."""

    EXECUTION_WEAKNESS = "execution_weakness"
    MISSING_EVIDENCE = "missing_evidence"
    UNUSUAL_BEHAVIOUR = "unusual_behaviour"
    OTHER = "other"
    NO_CONCERN = "no_concern"


class ManualPriority(str, enum.Enum):
    """A manual reviewer's own priority verdict for an entity.

    Deliberately the same four-value vocabulary as risk_score.py's
    RiskBand ("critical" | "high" | "medium" | "low") so a manual verdict and
    VEIL's risk_band are directly comparable in the blind-review comparison
    endpoint — see app/routers/manual_review.py.
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ManualReview(Base):
    """A supervisor's manual, blind judgement of one entity's raw evidence.

    Entirely separate from the analytics path: nothing here is read by any
    detector, by risk_score.py, or by sample_priority.py, and nothing in this
    table is ever written by them either. It exists solely so a human
    reviewer's independent verdict (formed from GET
    /api/manual-review/{entity_name}/evidence, which deliberately excludes
    every VEIL conclusion) can later be compared against VEIL's own output —
    see GET /api/manual-review/{entity_name}/comparison. A review is never
    edited or overwritten (see POST /api/manual-review) — every submission is
    a new row, so review history is preserved.
    """

    __tablename__ = "manual_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    reviewer_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    supervisory_concern: Mapped[bool] = mapped_column(Boolean, nullable=False)
    concern_type: Mapped[ConcernType] = mapped_column(
        SAEnum(ConcernType, values_callable=lambda enum_cls: [member.value for member in enum_cls]),
        nullable=False,
    )
    manual_priority: Mapped[ManualPriority] = mapped_column(
        SAEnum(ManualPriority, values_callable=lambda enum_cls: [member.value for member in enum_cls]),
        nullable=False,
    )
    manual_review_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evidence_sufficient: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
