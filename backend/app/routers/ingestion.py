"""POST /api/upload — parse a SOC alert CSV and load it into SQLite.

Each upload represents a fresh assessment run, so the alerts table is wiped
before the new file's rows are inserted.
"""

import io
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert

router = APIRouter()

REQUIRED_COLUMNS: list[str] = [
    "alert_id",
    "entity_name",
    "severity",
    "created_time",
    "closed_time",
    "escalated",
    "investigation_notes",
    "asset_type",
]

TRUE_VALUES: set[str] = {"yes", "true", "1"}
FALSE_VALUES: set[str] = {"no", "false", "0"}


def _parse_escalated(value: object) -> bool:
    """Map yes/no/true/false/1/0 (any case, whitespace-tolerant) to a bool.

    Missing or unrecognized values default to False.
    """
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text in TRUE_VALUES


def _clean_notes(value: object) -> Optional[str]:
    """Blank or whitespace-only investigation notes become None."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _clean_required_str(value: object) -> Optional[str]:
    """Strip a required string field; missing/blank values become None so callers can skip them."""
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


@router.post("/upload")
async def upload_alerts(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Parse an uploaded alert CSV and replace the alerts table with its contents."""
    raw = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}") from exc

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise HTTPException(status_code=400, detail={"missing_columns": missing_columns})

    rows_received = len(df)

    df["alert_id"] = df["alert_id"].apply(_clean_required_str)
    df["entity_name"] = df["entity_name"].apply(_clean_required_str)
    df["severity"] = df["severity"].apply(
        lambda v: str(v).strip().lower() if pd.notna(v) else ""
    )
    df["escalated"] = df["escalated"].apply(_parse_escalated)
    df["created_time"] = pd.to_datetime(df["created_time"], errors="coerce")
    df["closed_time"] = pd.to_datetime(df["closed_time"], errors="coerce")
    df["investigation_notes"] = df["investigation_notes"].apply(_clean_notes)
    df["asset_type"] = df["asset_type"].apply(
        lambda v: str(v).strip() if pd.notna(v) else ""
    )

    invalid_mask = (
        df["alert_id"].isna() | df["entity_name"].isna() | df["created_time"].isna()
    )
    invalid_count = int(invalid_mask.sum())
    df_valid = df.loc[~invalid_mask].copy()

    # alert_id alone is not globally unique: each company's CSV restarts its
    # own alert_id series, so "ALT001" from one entity and "ALT001" from
    # another are different alerts, not duplicates. Dedupe on the pair.
    duplicate_mask = df_valid.duplicated(subset=["entity_name", "alert_id"], keep="first")
    duplicate_count = int(duplicate_mask.sum())
    df_clean = df_valid.loc[~duplicate_mask].copy()

    rows_skipped = invalid_count + duplicate_count
    rows_inserted = len(df_clean)

    alerts = [
        Alert(
            alert_id=row.alert_id,
            entity_name=row.entity_name,
            severity=row.severity,
            created_time=row.created_time.to_pydatetime(),
            closed_time=row.closed_time.to_pydatetime() if pd.notna(row.closed_time) else None,
            escalated=bool(row.escalated),
            investigation_notes=row.investigation_notes,
            asset_type=row.asset_type,
        )
        for row in df_clean.itertuples(index=False)
    ]

    try:
        db.query(Alert).delete()
        db.add_all(alerts)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to load alerts: {exc}") from exc

    entities = sorted(df_clean["entity_name"].unique().tolist()) if rows_inserted else []
    if rows_inserted:
        date_range = {
            "start": df_clean["created_time"].min().isoformat(),
            "end": df_clean["created_time"].max().isoformat(),
        }
    else:
        date_range = {"start": None, "end": None}

    return {
        "rows_received": rows_received,
        "rows_inserted": rows_inserted,
        "rows_skipped": rows_skipped,
        "entities_found": {"count": len(entities), "list": entities},
        "date_range": date_range,
    }
