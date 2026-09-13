"""Unit tests for expected_vs_observed key in GET /api/entities/{entity_name} endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime

from app.main import app
from app.database import Base, get_db
from app.models import Alert


@pytest.fixture
def test_db_session():
    """Set up a single-connection in-memory SQLite database with sample alert data."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    
    # Insert sample alerts for two entities
    alerts = [
        Alert(
            alert_id="ALT001",
            entity_name="EntityA",
            severity="Critical",
            created_time=datetime(2026, 1, 1, 10, 0, 0),
            closed_time=datetime(2026, 1, 1, 10, 10, 0),
            escalated=True,
            investigation_notes="Detailed investigation note for testing",
            asset_type="Database",
        ),
        Alert(
            alert_id="ALT002",
            entity_name="EntityB",
            severity="High",
            created_time=datetime(2026, 1, 1, 11, 0, 0),
            closed_time=datetime(2026, 1, 1, 11, 20, 0),
            escalated=False,
            investigation_notes="Another investigation note for entity B",
            asset_type="Server",
        ),
    ]
    db.add_all(alerts)
    db.commit()
    
    yield db
    db.close()


def test_get_entity_detail_includes_expected_vs_observed(test_db_session):
    """Verify that GET /api/entities/{entity_name} includes expected_vs_observed key in response."""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        response = client.get("/api/entities/EntityA")
        assert response.status_code == 200
        data = response.json()

        assert "expected_vs_observed" in data
        assert isinstance(data["expected_vs_observed"], list)
        
        # Verify shape of items in expected_vs_observed
        if len(data["expected_vs_observed"]) > 0:
            item = data["expected_vs_observed"][0]
            required_keys = {
                "metric",
                "metric_key",
                "observed",
                "expected",
                "unit",
                "deviation_z",
                "direction",
                "interpretation",
            }
            assert required_keys.issubset(item.keys())
    finally:
        app.dependency_overrides.clear()


def test_get_entity_detail_404_for_unknown_entity(test_db_session):
    """Verify 404 behavior is unchanged for non-existent entities."""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        response = client.get("/api/entities/NonExistentEntity")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()
