"""Tests for POST /api/upload's .db/.sqlite support (dataset export ingestion).

Covers: a .db export with an "alerts" table produces byte-identical results
to the same rows uploaded as CSV; a .db export whose real table is named
something other than "alerts" is still found via the column-superset
fallback; a .db with no qualifying table returns a clean 400 (no stack
trace) naming the tables found and what's missing; and the file-size limit
is enforced without needing an actual 50MB fixture.
"""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.routers import ingestion as ingestion_module

CSV_HEADER = "alert_id,entity_name,severity,created_time,closed_time,escalated,investigation_notes,asset_type\n"
CSV_ROWS = [
    "ALT001,Acme Corp,Critical,2026-01-01 09:00:00,2026-01-01 09:04:00,Yes,Investigated thoroughly and closed.,Server\n",
    "ALT002,Acme Corp,Low,2026-01-02 10:00:00,2026-01-02 11:00:00,No,Reviewed and closed.,Database\n",
    "ALT003,Acme Corp,High,2026-01-03 08:00:00,,No,,Endpoint\n",
    "ALT001,Beta LLC,Medium,2026-01-04 12:00:00,2026-01-04 12:30:00,Yes,Escalated to IR team after correlation.,Cloud Workload\n",
]
CSV_TEXT = CSV_HEADER + "".join(CSV_ROWS)


@pytest.fixture
def test_db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def client(test_db_session):
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _build_sqlite_bytes(table_name: str = "alerts", extra_column: bool = False) -> bytes:
    """Build a small .sqlite file (in-memory build, then serialized to bytes)
    containing the same rows as CSV_ROWS, in a table named *table_name*.
    """
    fd, _tmp_name = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    tmp_path = Path(_tmp_name)
    tmp_path.unlink()  # sqlite3.connect creates it fresh
    conn = sqlite3.connect(str(tmp_path))
    try:
        extra = ", category TEXT" if extra_column else ""
        conn.execute(
            f'CREATE TABLE "{table_name}" ('
            "alert_id TEXT, entity_name TEXT, severity TEXT, created_time TEXT, "
            f"closed_time TEXT, escalated TEXT, investigation_notes TEXT, asset_type TEXT{extra}"
            ")"
        )
        rows = [
            ("ALT001", "Acme Corp", "Critical", "2026-01-01 09:00:00", "2026-01-01 09:04:00", "Yes", "Investigated thoroughly and closed.", "Server"),
            ("ALT002", "Acme Corp", "Low", "2026-01-02 10:00:00", "2026-01-02 11:00:00", "No", "Reviewed and closed.", "Database"),
            ("ALT003", "Acme Corp", "High", "2026-01-03 08:00:00", None, "No", None, "Endpoint"),
            ("ALT001", "Beta LLC", "Medium", "2026-01-04 12:00:00", "2026-01-04 12:30:00", "Yes", "Escalated to IR team after correlation.", "Cloud Workload"),
        ]
        placeholders = ", ".join(["?"] * (9 if extra_column else 8))
        for row in rows:
            values = row + ("misc",) if extra_column else row
            conn.execute(f'INSERT INTO "{table_name}" VALUES ({placeholders})', values)
        conn.commit()
    finally:
        conn.close()
    data = tmp_path.read_bytes()
    tmp_path.unlink()
    return data


def _build_sqlite_bytes_no_match() -> bytes:
    """A .db with tables that exist but none containing all required columns."""
    fd, _tmp_name = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    tmp_path = Path(_tmp_name)
    tmp_path.unlink()
    conn = sqlite3.connect(str(tmp_path))
    try:
        conn.execute("CREATE TABLE incidents (incident_id TEXT, org TEXT, level TEXT)")
        conn.execute("INSERT INTO incidents VALUES ('X1', 'Acme', 'high')")
        conn.execute("CREATE TABLE notes (note_id TEXT, body TEXT)")
        conn.commit()
    finally:
        conn.close()
    data = tmp_path.read_bytes()
    tmp_path.unlink()
    return data


def _upload_csv(client):
    return client.post(
        "/api/upload",
        files={"file": ("dataset.csv", CSV_TEXT.encode("utf-8"), "text/csv")},
    )


def _upload_db(client, data: bytes, filename: str = "dataset.db"):
    return client.post(
        "/api/upload",
        files={"file": (filename, data, "application/octet-stream")},
    )


# ---------------------------------------------------------------------------
# CSV baseline
# ---------------------------------------------------------------------------

def test_csv_upload_still_works(client):
    resp = _upload_csv(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["rows_received"] == 4
    assert body["rows_inserted"] == 4
    assert body["rows_skipped"] == 0
    assert body["entities_found"]["count"] == 2
    assert set(body["entities_found"]["list"]) == {"Acme Corp", "Beta LLC"}


# ---------------------------------------------------------------------------
# .db / .sqlite happy paths
# ---------------------------------------------------------------------------

def test_db_upload_with_alerts_table_matches_csv(client, test_db_session):
    csv_resp = _upload_csv(client)
    csv_body = csv_resp.json()

    db_bytes = _build_sqlite_bytes(table_name="alerts")
    db_resp = _upload_db(client, db_bytes, filename="export.db")
    assert db_resp.status_code == 200
    db_body = db_resp.json()

    # Response shape identical field-for-field (rows/entities/date_range) —
    # byte-identical result of the same underlying rows through the same
    # _process_dataframe pipeline, regardless of source format.
    assert db_body["rows_received"] == csv_body["rows_received"]
    assert db_body["rows_inserted"] == csv_body["rows_inserted"]
    assert db_body["rows_skipped"] == csv_body["rows_skipped"]
    assert db_body["entities_found"] == csv_body["entities_found"]
    assert db_body["date_range"] == csv_body["date_range"]


def test_sqlite_extension_also_accepted(client):
    db_bytes = _build_sqlite_bytes(table_name="alerts")
    resp = _upload_db(client, db_bytes, filename="export.sqlite")
    assert resp.status_code == 200
    assert resp.json()["rows_inserted"] == 4


def test_db_upload_falls_back_to_non_alerts_table(client):
    """A table named something other than "alerts" is still found via the
    column-superset fallback, as long as it has every required column."""
    db_bytes = _build_sqlite_bytes(table_name="soc_export")
    resp = _upload_db(client, db_bytes, filename="export.db")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rows_inserted"] == 4
    assert set(body["entities_found"]["list"]) == {"Acme Corp", "Beta LLC"}


def test_db_upload_with_extra_columns_ignores_them(client):
    db_bytes = _build_sqlite_bytes(table_name="alerts", extra_column=True)
    resp = _upload_db(client, db_bytes, filename="export.db")
    assert resp.status_code == 200
    assert resp.json()["rows_inserted"] == 4


def test_db_upload_prefers_alerts_table_when_multiple_qualify(client):
    """When more than one table qualifies, the literal "alerts" table wins,
    even though "archive" was created first (so sqlite_master would list it
    first without the explicit preference)."""
    fd, _tmp_name = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    tmp_path = Path(_tmp_name)
    tmp_path.unlink()
    conn = sqlite3.connect(str(tmp_path))
    try:
        cols = "alert_id TEXT, entity_name TEXT, severity TEXT, created_time TEXT, closed_time TEXT, escalated TEXT, investigation_notes TEXT, asset_type TEXT"
        conn.execute(f"CREATE TABLE archive ({cols})")
        conn.execute("INSERT INTO archive VALUES ('OLD1','Old Corp','Low','2020-01-01 00:00:00',NULL,'No',NULL,'Server')")
        conn.execute(f"CREATE TABLE alerts ({cols})")
        conn.execute("INSERT INTO alerts VALUES ('ALT001','Acme Corp','Critical','2026-01-01 09:00:00','2026-01-01 09:04:00','Yes','note','Server')")
        conn.commit()
    finally:
        conn.close()
    data = tmp_path.read_bytes()
    tmp_path.unlink()

    resp = _upload_db(client, data, filename="export.db")
    assert resp.status_code == 200
    body = resp.json()
    assert body["rows_inserted"] == 1
    assert body["entities_found"]["list"] == ["Acme Corp"]


# ---------------------------------------------------------------------------
# No qualifying table — clean 400, not a stack trace
# ---------------------------------------------------------------------------

def test_db_upload_no_matching_table_returns_clean_400(client):
    db_bytes = _build_sqlite_bytes_no_match()
    resp = _upload_db(client, db_bytes, filename="export.db")
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert isinstance(detail, dict)
    assert set(detail["tables_found"]) == {"incidents", "notes"}
    assert set(detail["missing_columns_by_table"].keys()) == {"incidents", "notes"}
    # incidents has none of our 8 required columns
    assert set(detail["missing_columns_by_table"]["incidents"]) == set(ingestion_module.REQUIRED_COLUMNS)


def test_db_upload_no_tables_at_all_returns_clean_400(client):
    fd, _tmp_name = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    tmp_path = Path(_tmp_name)
    tmp_path.unlink()
    conn = sqlite3.connect(str(tmp_path))
    conn.close()  # empty database, zero tables
    data = tmp_path.read_bytes()
    tmp_path.unlink()

    resp = _upload_db(client, data, filename="empty.db")
    assert resp.status_code == 400


def test_not_actually_a_sqlite_file_returns_clean_400(client):
    resp = _upload_db(client, b"this is not a sqlite database", filename="fake.db")
    assert resp.status_code == 400
    # No 500, no raw traceback text leaking into the response.
    assert "Traceback" not in resp.text


# ---------------------------------------------------------------------------
# Size limit
# ---------------------------------------------------------------------------

def test_db_upload_over_size_limit_rejected(client, monkeypatch):
    monkeypatch.setattr(ingestion_module, "MAX_UPLOAD_BYTES", 10)
    db_bytes = _build_sqlite_bytes(table_name="alerts")
    assert len(db_bytes) > 10
    resp = _upload_db(client, db_bytes, filename="export.db")
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


def test_csv_upload_over_size_limit_rejected(client, monkeypatch):
    """The same MAX_UPLOAD_BYTES limit applies to CSV, not just .db/.sqlite."""
    monkeypatch.setattr(ingestion_module, "MAX_UPLOAD_BYTES", 10)
    resp = _upload_csv(client)
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


def test_json_upload_over_size_limit_rejected(client, monkeypatch):
    """The same MAX_UPLOAD_BYTES limit applies to JSON, not just .db/.sqlite."""
    monkeypatch.setattr(ingestion_module, "MAX_UPLOAD_BYTES", 10)
    payload = json.dumps({"alerts": [{"alert_id": "A1", "entity_name": "Acme Corp"}]}).encode("utf-8")
    resp = client.post(
        "/api/upload",
        files={"file": ("dataset.json", payload, "application/json")},
    )
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Temp file cleanup
# ---------------------------------------------------------------------------

def test_temp_file_removed_after_successful_upload(client):
    before = set(Path(tempfile.gettempdir()).glob("*.sqlite"))
    db_bytes = _build_sqlite_bytes(table_name="alerts")
    resp = _upload_db(client, db_bytes, filename="export.db")
    assert resp.status_code == 200
    after = set(Path(tempfile.gettempdir()).glob("*.sqlite"))
    assert after <= before  # no new .sqlite temp files left behind


def test_temp_file_removed_after_failed_upload(client):
    before = set(Path(tempfile.gettempdir()).glob("*.sqlite"))
    resp = _upload_db(client, _build_sqlite_bytes_no_match(), filename="export.db")
    assert resp.status_code == 400
    after = set(Path(tempfile.gettempdir()).glob("*.sqlite"))
    assert after <= before


# ---------------------------------------------------------------------------
# Extension detection
# ---------------------------------------------------------------------------

def test_unsupported_extension_still_rejected(client):
    resp = client.post(
        "/api/upload",
        files={"file": ("export.txt", b"whatever", "text/plain")},
    )
    assert resp.status_code == 400
