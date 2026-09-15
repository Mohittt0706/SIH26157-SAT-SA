"""POST /api/upload — parse a SOC alert CSV, JSON, or SQLite DB export and load it into SQLite.

Each upload represents a fresh assessment run, so the alerts table is wiped
before the new file's rows are inserted.  AssessmentRun records persist
historically and are not affected by alerts-table resets.
"""

import io
import json
import os
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, AssessmentRun
from app.analytics.execution_gap import compute_execution_gap
from app.analytics.negative_space import compute_negative_space
from app.analytics.anomaly import compute_anomaly
from app.analytics.risk_score import compute_risk_scores

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

MAX_DB_UPLOAD_BYTES: int = 50 * 1024 * 1024
"""Cap on an uploaded .db/.sqlite file's size (50 MiB). Generous for a SOC
export of a few hundred thousand alert rows, but bounds how large a file this
endpoint will write to a temp file and open, however briefly and read-only."""

PREFERRED_TABLE_NAME: str = "alerts"
"""Table name tried first when a .db/.sqlite upload has more than one table
containing all REQUIRED_COLUMNS — matches the ingested table's own name."""

SQLITE_INTERNAL_TABLE_PREFIX: str = "sqlite_"
"""SQLite's own bookkeeping tables (sqlite_sequence, sqlite_stat1, ...) are
never candidates — they're not data the uploader intended to ingest."""

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


def _canonicalize_column(values: "pd.Series", empty_value: Optional[str] = None) -> "pd.Series":
    """Strip/collapse whitespace and canonicalize a column case-insensitively.

    Every case/whitespace variant of the same name maps to whichever spelling
    appeared *first* in the file — e.g. "Rivera Logistics" and later
    "rivera   logistics" both become "Rivera Logistics", so the same company
    doesn't split into two entities with half the alerts each (which would
    corrupt the peer median for negative_space). Missing/blank values become
    *empty_value*.
    """
    canonical_by_key: dict[str, str] = {}
    result: list[Optional[str]] = []
    for raw in values:
        if pd.isna(raw):
            result.append(empty_value)
            continue
        normalized = re.sub(r"\s+", " ", str(raw).strip())
        if not normalized:
            result.append(empty_value)
            continue
        key = normalized.casefold()
        result.append(canonical_by_key.setdefault(key, normalized))
    return pd.Series(result, index=values.index)


def _detect_format(filename: Optional[str]) -> str:
    """Pick the parser from the file extension, not the browser-supplied content-type."""
    name = (filename or "").strip().lower()
    if name.endswith(".json"):
        return "json"
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".db") or name.endswith(".sqlite"):
        return "db"
    raise HTTPException(
        status_code=400,
        detail="Unsupported file type: expected a .csv, .json, .db, or .sqlite file.",
    )


def _parse_csv(raw: bytes) -> "pd.DataFrame":
    try:
        return pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}") from exc


def _parse_json(raw: bytes) -> "pd.DataFrame":
    """Accept either a top-level array of alert objects or {"alerts": [...]}."""
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse JSON: {exc}") from exc

    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and isinstance(payload.get("alerts"), list):
        records = payload["alerts"]
    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "JSON must be either a top-level array of alert objects, or an "
                'object with a top-level "alerts" key containing that array.'
            ),
        )

    if not all(isinstance(record, dict) for record in records):
        raise HTTPException(
            status_code=400, detail="Each alert in the JSON array must be an object."
        )

    try:
        return pd.DataFrame.from_records(records)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse JSON: {exc}") from exc


def _table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    """Column names for *table_name*, in schema order.

    PRAGMA doesn't support bind parameters for identifiers, so *table_name*
    (which only ever comes from this connection's own sqlite_master, never
    from user-supplied text directly) is double-quote-escaped the standard
    SQL way before being interpolated.
    """
    escaped = table_name.replace('"', '""')
    cursor = conn.execute(f'PRAGMA table_info("{escaped}")')
    return [row[1] for row in cursor.fetchall()]


def _find_alerts_table(conn: sqlite3.Connection) -> tuple[str, dict[str, str]]:
    """Locate a table whose columns are a superset of REQUIRED_COLUMNS.

    Tries a table literally named "alerts" first (case-insensitive), then
    every other user table in the database, in the order sqlite_master
    returns them. Column matching is case-insensitive, since a real export
    tool's casing conventions (e.g. "AlertId", "ALERT_ID") shouldn't be a
    reason to reject an otherwise-valid export.

    Returns (table_name, column_map) where column_map maps each required
    column (lowercase) to that table's actual column name, for the caller to
    SELECT and rename by.

    Raises HTTPException(400) — naming every table found and, for each, which
    required columns are missing — if no table qualifies.
    """
    table_rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    table_names = [row[0] for row in table_rows if not row[0].startswith(SQLITE_INTERNAL_TABLE_PREFIX)]

    if not table_names:
        raise HTTPException(
            status_code=400,
            detail="The uploaded database contains no tables.",
        )

    # "alerts" first (case-insensitive), then everything else in place.
    ordered = sorted(table_names, key=lambda name: (name.lower() != PREFERRED_TABLE_NAME, table_names.index(name)))

    missing_by_table: dict[str, list[str]] = {}
    for table_name in ordered:
        columns = _table_columns(conn, table_name)
        lower_to_actual = {col.lower(): col for col in columns}
        missing = [req for req in REQUIRED_COLUMNS if req not in lower_to_actual]
        if not missing:
            column_map = {req: lower_to_actual[req] for req in REQUIRED_COLUMNS}
            return table_name, column_map
        missing_by_table[table_name] = missing

    raise HTTPException(
        status_code=400,
        detail={
            "message": "No table in the uploaded database contains all required columns.",
            "tables_found": table_names,
            "missing_columns_by_table": missing_by_table,
        },
    )


def _parse_sqlite_db(raw: bytes) -> "pd.DataFrame":
    """Parse a .db/.sqlite export: write to a temp file, open read-only, extract rows.

    Security: the file is opened with sqlite3's URI "mode=ro" (read-only at
    the SQLite level, not just a file-permission convention) and nothing from
    it is ever executed — only SELECT/PRAGMA reads against identifiers this
    function itself discovered via sqlite_master. The temp file is always
    removed afterward, success or failure.
    """
    if len(raw) > MAX_DB_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Database file too large: {len(raw)} bytes exceeds the "
                f"{MAX_DB_UPLOAD_BYTES} byte limit."
            ),
        )

    fd, tmp_path_str = tempfile.mkstemp(suffix=".sqlite")
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(raw)

        uri = f"file:{tmp_path.as_posix()}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True)
        except sqlite3.Error as exc:
            raise HTTPException(status_code=400, detail=f"Could not open database file: {exc}") from exc

        try:
            try:
                table_name, column_map = _find_alerts_table(conn)
            except sqlite3.Error as exc:
                # Lazy open: sqlite3.connect() succeeds even for a non-database
                # file — the first real read is what discovers that, e.g. via
                # sqlite_master here.
                raise HTTPException(status_code=400, detail=f"Not a valid SQLite database: {exc}") from exc

            select_list = ", ".join(f'"{column_map[req].replace(chr(34), chr(34) * 2)}" AS "{req}"' for req in REQUIRED_COLUMNS)
            escaped_table = table_name.replace('"', '""')
            try:
                df = pd.read_sql_query(f'SELECT {select_list} FROM "{escaped_table}"', conn)
            except (sqlite3.Error, pd.errors.DatabaseError) as exc:
                raise HTTPException(status_code=400, detail=f"Could not read table '{table_name}': {exc}") from exc
        finally:
            conn.close()

        return df
    finally:
        tmp_path.unlink(missing_ok=True)


def _process_dataframe(df: "pd.DataFrame", db: Session, filename: str = "unknown", file_format: str = "csv") -> dict[str, object]:
    """Run the shared normalization/validation/dedup/canonicalization pipeline and load it into SQLite.

    Both the CSV and JSON upload paths funnel through here so a company's data
    is treated identically regardless of which format it arrived in.
    """
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise HTTPException(status_code=400, detail={"missing_columns": missing_columns})

    rows_received = len(df)

    df["alert_id"] = df["alert_id"].apply(_clean_required_str)
    df["entity_name"] = _canonicalize_column(df["entity_name"])
    df["severity"] = df["severity"].apply(
        lambda v: str(v).strip().lower() if pd.notna(v) else ""
    )
    df["escalated"] = df["escalated"].apply(_parse_escalated)
    df["created_time"] = pd.to_datetime(df["created_time"], errors="coerce")
    df["closed_time"] = pd.to_datetime(df["closed_time"], errors="coerce")
    df["investigation_notes"] = df["investigation_notes"].apply(_clean_notes)
    df["asset_type"] = _canonicalize_column(df["asset_type"], empty_value="")

    invalid_mask = (
        df["alert_id"].isna() | df["entity_name"].isna() | df["created_time"].isna()
    )
    invalid_count = int(invalid_mask.sum())
    df_valid = df.loc[~invalid_mask].copy()

    # alert_id alone is not globally unique: each company's CSV restarts its
    # own alert_id series, so "ALT001" from one entity and "ALT001" from
    # another are different alerts, not duplicates. Dedupe on the pair.
    # entity_name is already canonicalized above, so "Rivera Logistics" and
    # "rivera logistics" collapse to the same key here too — a same-company
    # case variant with a repeated alert_id correctly dedupes instead of
    # silently becoming two separate composite-PK rows.
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

    # --- Create AssessmentRun audit record ---
    from datetime import datetime
    data_range_start = datetime.fromisoformat(date_range["start"]) if date_range.get("start") else None
    data_range_end = datetime.fromisoformat(date_range["end"]) if date_range.get("end") else None

    detector_config = _build_detector_config()
    results_snapshot = _build_results_snapshot(db, detector_config)

    db_assessment_run = AssessmentRun(
        source_filename=filename or "unknown",
        source_format=file_format,
        rows_received=rows_received,
        rows_inserted=rows_inserted,
        rows_skipped=rows_skipped,
        entity_count=len(entities) if rows_inserted else 0,
        data_range_start=data_range_start,
        data_range_end=data_range_end,
        detector_config=detector_config,
        results_snapshot=results_snapshot,
    )
    db.add(db_assessment_run)
    db.commit()

    return {
        "rows_received": rows_received,
        "rows_inserted": rows_inserted,
        "rows_skipped": rows_skipped,
        "entities_found": {"count": len(entities), "list": entities},
        "date_range": date_range,
    }


def _build_detector_config() -> str:
    """Build a complete detector configuration snapshot for audit purposes.

    Captures actual constant values, not just names, so a supervisor can
    verify that a run performed three months ago used the exact same
    thresholds and weights that are in the code today.
    The keys match the DetectorConfiguration model field names for
    proper Pydantic validation on retrieval.
    """
    from app.analytics.execution_gap import (
        FAST_CLOSURE_THRESHOLD_SECONDS,
        MIN_NOTE_LENGTH,
        MIN_DUPLICATE_MULTIPLICITY,
        TEMPLATE_DUPLICATE_Z_THRESHOLD,
        FAST_CLOSURE_WEIGHT,
        NO_ESCALATION_WEIGHT,
        TEMPLATE_NOTES_WEIGHT,
    )
    from app.analytics.negative_space import (
        LOW_VOLUME_Z_THRESHOLD,
        MIN_PEERS_WITH_SEVERITY,
        LOW_VOLUME_WEIGHT,
        MISSING_SEVERITY_WEIGHT,
    )
    from app.analytics.anomaly import (
        IFOREST_RANDOM_STATE,
        IFOREST_CONTAMINATION,
        IFOREST_N_ESTIMATORS,
    )
    from app.analytics.risk_score import (
        WEIGHT_EXECUTION_GAP,
        WEIGHT_NEGATIVE_SPACE,
        WEIGHT_ANOMALY,
        FLOOR_ATTENUATION,
        RISK_BAND_CRITICAL_THRESHOLD,
        RISK_BAND_HIGH_THRESHOLD,
        RISK_BAND_MEDIUM_THRESHOLD,
    )
    from app.routers.analytics import FINDING_SUMMARY_THRESHOLD

    config = {
        "fast_closure_threshold_seconds": FAST_CLOSURE_THRESHOLD_SECONDS,
        "min_note_length": MIN_NOTE_LENGTH,
        "min_duplicate_multiplicity": MIN_DUPLICATE_MULTIPLICITY,
        "template_duplicate_z_threshold": TEMPLATE_DUPLICATE_Z_THRESHOLD,
        "fast_closure_weight": FAST_CLOSURE_WEIGHT,
        "no_escalation_weight": NO_ESCALATION_WEIGHT,
        "template_notes_weight": TEMPLATE_NOTES_WEIGHT,
        "low_volume_z_threshold": LOW_VOLUME_Z_THRESHOLD,
        "min_peers_with_severity": MIN_PEERS_WITH_SEVERITY,
        "low_volume_weight": LOW_VOLUME_WEIGHT,
        "missing_severity_weight": MISSING_SEVERITY_WEIGHT,
        "iforest_random_state": IFOREST_RANDOM_STATE,
        "iforest_contamination": IFOREST_CONTAMINATION,
        "iforest_n_estimators": IFOREST_N_ESTIMATORS,
        "weight_execution_gap": WEIGHT_EXECUTION_GAP,
        "weight_negative_space": WEIGHT_NEGATIVE_SPACE,
        "weight_anomaly": WEIGHT_ANOMALY,
        "floor_attenuation": FLOOR_ATTENUATION,
        "risk_band_critical_threshold": RISK_BAND_CRITICAL_THRESHOLD,
        "risk_band_high_threshold": RISK_BAND_HIGH_THRESHOLD,
        "risk_band_medium_threshold": RISK_BAND_MEDIUM_THRESHOLD,
        "finding_summary_threshold": FINDING_SUMMARY_THRESHOLD,
    }
    return json.dumps(config, sort_keys=True)


def _build_results_snapshot(db: Session, detector_config: str) -> str:
    """Build the JSON results snapshot for this AssessmentRun.

    Runs the existing risk-score pipeline and serializes every entity's
    result so that the audit record contains the exact scores that were
    produced at upload time.
    """
    from app.analytics.risk_score import compute_risk_scores

    risk_rows = compute_risk_scores(db)

    entity_results: list[dict] = []
    for row in risk_rows:
        entity_results.append(
            {
                "entity_name": row["entity_name"],
                "risk_score": row["risk_score"],
                "risk_band": row["risk_band"],
                "execution_gap_component_score": row.get("execution_gap_score"),
                "negative_space_component_score": row.get("negative_space_score"),
                "anomaly_component_score": row.get("anomaly_score"),
            }
        )

    return json.dumps(entity_results, sort_keys=True)


def _parse_by_format(raw: bytes, file_format: str) -> "pd.DataFrame":
    if file_format == "csv":
        return _parse_csv(raw)
    if file_format == "json":
        return _parse_json(raw)
    return _parse_sqlite_db(raw)


@router.post("/upload")
async def upload_alerts(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Parse an uploaded alert CSV, JSON, or SQLite DB export and replace the alerts table with its contents."""
    raw = await file.read()
    file_format = _detect_format(file.filename)
    df = _parse_by_format(raw, file_format)
    return _process_dataframe(df, db, filename=file.filename or "unknown", file_format=file_format)
