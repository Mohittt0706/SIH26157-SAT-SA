"""Unit tests for GET /api/trends and GET /api/trends/{entity_name} endpoints."""

import json
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models import AssessmentRun


@pytest.fixture
def test_db_session():
    """Set up an in-memory SQLite database with sample AssessmentRun records."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    base_time = datetime(2026, 1, 1, 12, 0, 0)

    # Run 1: Early run
    snapshot_1 = [
        {
            "entity_name": "ImprovingCorp",
            "risk_score": 60.0,
            "risk_band": "high",
            "execution_gap_component_score": 0.5,
            "negative_space_component_score": 0.4,
            "anomaly_component_score": 0.3,
        },
        {
            "entity_name": "DeterioratingCorp",
            "risk_score": 20.0,
            "risk_band": "low",
            "execution_gap_component_score": 0.1,
            "negative_space_component_score": 0.1,
            "anomaly_component_score": 0.1,
        },
        {
            "entity_name": "StableCorp",
            "risk_score": 30.0,
            "risk_band": "medium",
            "execution_gap_component_score": 0.2,
            "negative_space_component_score": 0.2,
            "anomaly_component_score": 0.2,
        },
        {
            "entity_name": "SingleRunCorp",
            "risk_score": 25.0,
            "risk_band": "medium",
            "execution_gap_component_score": 0.2,
            "negative_space_component_score": 0.2,
            "anomaly_component_score": 0.1,
        },
    ]

    # Run 2: Later run
    snapshot_2 = [
        {
            "entity_name": "ImprovingCorp",
            "risk_score": 35.0,  # 60.0 -> 35.0 (change = -25.0 < -5.0 -> improving)
            "risk_band": "medium",
            "execution_gap_component_score": 0.2,
            "negative_space_component_score": 0.2,
            "anomaly_component_score": 0.1,
        },
        {
            "entity_name": "DeterioratingCorp",
            "risk_score": 55.0,  # 20.0 -> 55.0 (change = +35.0 > 5.0 -> deteriorating)
            "risk_band": "high",
            "execution_gap_component_score": 0.4,
            "negative_space_component_score": 0.4,
            "anomaly_component_score": 0.3,
        },
        {
            "entity_name": "StableCorp",
            "risk_score": 32.0,  # 30.0 -> 32.0 (change = +2.0 <= 5.0 -> stable)
            "risk_band": "medium",
            "execution_gap_component_score": 0.2,
            "negative_space_component_score": 0.2,
            "anomaly_component_score": 0.2,
        },
    ]

    run1 = AssessmentRun(
        run_timestamp=base_time,
        source_filename="run1.csv",
        source_format="csv",
        rows_received=100,
        rows_inserted=100,
        rows_skipped=0,
        entity_count=4,
        detector_config="{}",
        results_snapshot=json.dumps(snapshot_1),
    )

    run2 = AssessmentRun(
        run_timestamp=base_time + timedelta(days=7),
        source_filename="run2.csv",
        source_format="csv",
        rows_received=100,
        rows_inserted=100,
        rows_skipped=0,
        entity_count=3,
        detector_config="{}",
        results_snapshot=json.dumps(snapshot_2),
    )

    db.add_all([run1, run2])
    db.commit()

    yield db
    db.close()


def test_trend_detail_improving_deteriorating_stable(test_db_session):
    """Test 2+ runs trend calculations for improving, deteriorating, and stable entities."""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        # Improving case
        resp_imp = client.get("/api/trends/ImprovingCorp")
        assert resp_imp.status_code == 200
        data_imp = resp_imp.json()
        assert data_imp["entity_name"] == "ImprovingCorp"
        assert len(data_imp["points"]) == 2
        assert data_imp["change"] == -25.0
        assert data_imp["direction"] == "improving"

        # Deteriorating case
        resp_det = client.get("/api/trends/DeterioratingCorp")
        assert resp_det.status_code == 200
        data_det = resp_det.json()
        assert data_det["entity_name"] == "DeterioratingCorp"
        assert len(data_det["points"]) == 2
        assert data_det["change"] == 35.0
        assert data_det["direction"] == "deteriorating"

        # Stable case
        resp_sta = client.get("/api/trends/StableCorp")
        assert resp_sta.status_code == 200
        data_sta = resp_sta.json()
        assert data_sta["entity_name"] == "StableCorp"
        assert len(data_sta["points"]) == 2
        assert data_sta["change"] == 2.0
        assert data_sta["direction"] == "stable"

    finally:
        app.dependency_overrides.clear()


def test_trend_detail_insufficient_data(test_db_session):
    """Test entity with fewer than 2 runs returns insufficient_data, points=[], change=None."""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        resp = client.get("/api/trends/SingleRunCorp")
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_name"] == "SingleRunCorp"
        assert data["points"] == []
        assert data["direction"] == "insufficient_data"
        assert data["change"] is None
    finally:
        app.dependency_overrides.clear()


def test_trend_detail_404_non_existent(test_db_session):
    """Test entity that was never present in any run returns 404."""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        resp = client.get("/api/trends/NonExistentCorp")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_trends_summary_endpoint(test_db_session):
    """Test GET /api/trends returns all entity directions."""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        resp = client.get("/api/trends")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 4

        entity_dirs = {item["entity_name"]: item["direction"] for item in data}
        assert entity_dirs["ImprovingCorp"] == "improving"
        assert entity_dirs["DeterioratingCorp"] == "deteriorating"
        assert entity_dirs["StableCorp"] == "stable"
        assert entity_dirs["SingleRunCorp"] == "insufficient_data"
    finally:
        app.dependency_overrides.clear()
