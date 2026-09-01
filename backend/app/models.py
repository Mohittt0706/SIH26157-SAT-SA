"""ORM models for SAT-SA — the SOC alert table."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Alert(Base):
    """A single SOC alert/case record ingested from a company's CSV export.

    Maps directly to the CSV schema documented in project.md:
    alert_id, entity_name, severity, created_time, closed_time, escalated,
    investigation_notes, asset_type.
    """

    __tablename__ = "alerts"

    alert_id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_name: Mapped[str] = mapped_column(String, index=True)
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
