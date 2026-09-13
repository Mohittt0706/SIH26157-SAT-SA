"""Unit tests for the blind manual-review workflow (step 5).

Covers: the blind evidence endpoint returns real evidence and leaks no VEIL
conclusion, valid/invalid submission, append-only history, and the
comparison/metrics endpoints' before/after-a-review behavior.
"""

import json
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Alert, AssessmentRun


FORBIDDEN_EVIDENCE_KEYS = [
    "risk_score",
    "risk_band",
    "primary_driver",
    "component_scores",
    "anomaly_score",
    "execution_gap",
    "negative_space",
    "anomaly",
    "detector",
    "rule",
    "findings",
    "evidence",
    "priority_score",
    "peer_metrics",
    "peer_median",
]


def _alert(alert_id, entity_name, severity, created, closed, escalated, notes, asset_type="Server"):
    return Alert(
        alert_id=alert_id,
        entity_name=entity_name,
        severity=severity,
        created_time=created,
        closed_time=closed,
        escalated=escalated,
        investigation_notes=notes,
        asset_type=asset_type,
    )


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

    base = datetime(2026, 1, 1, 9, 0, 0)
    long_note = "Investigated thoroughly and documented findings in detail."

    alerts = [
        _alert("ALT001", "ReviewCorp", "Critical", base, base + timedelta(seconds=5), False, "x"),
        _alert(
            "ALT002", "ReviewCorp", "Low", base + timedelta(hours=1),
            base + timedelta(hours=1, minutes=30), True, long_note, "Database",
        ),
        _alert(
            "ALT003", "ReviewCorp", "Medium", base + timedelta(hours=2),
            None, True, long_note, "Cloud Workload",
        ),
        _alert(
            "ALT001", "OtherCorp", "Low", base, base + timedelta(minutes=45), True, long_note,
        ),
    ]
    db.add_all(alerts)
    db.commit()
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


# ---------------------------------------------------------------------------
# 5.2 — blind evidence
# ---------------------------------------------------------------------------

def test_blind_evidence_returns_real_evidence(client):
    resp = client.get("/api/manual-review/ReviewCorp/evidence")
    assert resp.status_code == 200
    data = resp.json()

    assert data["entity_name"] == "ReviewCorp"
    assert len(data["alerts"]) == 3
    alert_ids = {a["alert_id"] for a in data["alerts"]}
    assert alert_ids == {"ALT001", "ALT002", "ALT003"}

    for a in data["alerts"]:
        assert set(a.keys()) == {
            "alert_id", "severity", "asset_type", "created_time", "closed_time",
            "closure_duration_seconds", "escalated", "investigation_notes",
        }

    agg = data["aggregates"]
    assert agg["total_alerts"] == 3
    assert agg["open_alerts"] == 1
    assert agg["closed_alerts"] == 2
    assert agg["escalated_count"] == 2
    assert agg["escalated_rate"] == pytest.approx(2 / 3)
    assert agg["severity_distribution"] == {"Critical": 1, "Low": 1, "Medium": 1}
    assert agg["asset_type_distribution"]["Server"] == 1
    assert agg["asset_type_distribution"]["Database"] == 1
    assert agg["asset_type_distribution"]["Cloud Workload"] == 1


def test_blind_evidence_404_for_unknown_entity(client):
    resp = client.get("/api/manual-review/NoSuchCorp/evidence")
    assert resp.status_code == 404


def test_blind_evidence_leaks_no_veil_conclusion(client):
    """Explicitly asserts none of the forbidden VEIL-conclusion keys appear
    anywhere in the blind evidence response, at any nesting level."""
    resp = client.get("/api/manual-review/ReviewCorp/evidence")
    assert resp.status_code == 200
    raw = resp.text

    for forbidden in FORBIDDEN_EVIDENCE_KEYS:
        assert f'"{forbidden}"' not in raw, f"forbidden VEIL key '{forbidden}' leaked into blind evidence response"

    # And structurally: only the two documented top-level keys.
    data = resp.json()
    assert set(data.keys()) == {"entity_name", "alerts", "aggregates"}
    assert set(data["aggregates"].keys()) == {
        "total_alerts", "open_alerts", "closed_alerts", "avg_closure_seconds",
        "escalated_count", "escalated_rate", "avg_investigation_note_length",
        "severity_distribution", "asset_type_distribution",
    }


# ---------------------------------------------------------------------------
# 5.3 — submit
# ---------------------------------------------------------------------------

VALID_REVIEW_PAYLOAD = {
    "entity_name": "ReviewCorp",
    "reviewer_id": "supervisor-1",
    "supervisory_concern": True,
    "concern_type": "execution_weakness",
    "manual_priority": "high",
    "manual_review_recommended": True,
    "evidence_sufficient": True,
    "rationale": "Critical alert closed in 5 seconds with no escalation.",
}


def test_valid_submission_persists(client):
    resp = client.post("/api/manual-review", json=VALID_REVIEW_PAYLOAD)
    assert resp.status_code == 201
    created = resp.json()
    assert created["entity_name"] == "ReviewCorp"
    assert created["concern_type"] == "execution_weakness"
    assert created["manual_priority"] == "high"
    assert "id" in created and "created_at" in created

    listed = client.get("/api/manual-review/ReviewCorp").json()
    assert len(listed) == 1
    assert listed[0]["id"] == created["id"]


def test_invalid_concern_type_rejected(client):
    payload = dict(VALID_REVIEW_PAYLOAD, concern_type="not_a_real_concern")
    resp = client.post("/api/manual-review", json=payload)
    assert resp.status_code == 422


def test_invalid_manual_priority_rejected(client):
    payload = dict(VALID_REVIEW_PAYLOAD, manual_priority="urgent")
    resp = client.post("/api/manual-review", json=payload)
    assert resp.status_code == 422


def test_missing_required_field_rejected(client):
    payload = dict(VALID_REVIEW_PAYLOAD)
    del payload["rationale"]
    resp = client.post("/api/manual-review", json=payload)
    assert resp.status_code == 422


def test_history_preserved_on_second_submission(client):
    """Submitting a second review for the same entity appends, never overwrites."""
    first = client.post("/api/manual-review", json=VALID_REVIEW_PAYLOAD).json()

    second_payload = dict(
        VALID_REVIEW_PAYLOAD,
        supervisory_concern=False,
        concern_type="no_concern",
        manual_priority="low",
        manual_review_recommended=False,
        rationale="On second look, this was a false alarm.",
    )
    second = client.post("/api/manual-review", json=second_payload).json()

    assert first["id"] != second["id"]

    history = client.get("/api/manual-review/ReviewCorp").json()
    assert len(history) == 2
    # Newest first.
    assert history[0]["id"] == second["id"]
    assert history[1]["id"] == first["id"]
    assert history[0]["manual_priority"] == "low"
    assert history[1]["manual_priority"] == "high"


def test_empty_history_for_never_reviewed_entity(client):
    resp = client.get("/api/manual-review/ReviewCorp")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# 5.5 — comparison
# ---------------------------------------------------------------------------

def test_comparison_unavailable_before_a_review(client):
    resp = client.get("/api/manual-review/ReviewCorp/comparison")
    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert data["reason"]
    # No VEIL fields leaked into the "unavailable" response either.
    for key in ("veil_risk_band", "veil_concern", "veil_prioritized"):
        assert data.get(key) is None


def test_comparison_available_after_a_review(client):
    client.post("/api/manual-review", json=VALID_REVIEW_PAYLOAD)

    resp = client.get("/api/manual-review/ReviewCorp/comparison")
    assert resp.status_code == 200
    data = resp.json()

    assert data["available"] is True
    assert data["manual_concern"] is True
    assert data["manual_priority"] == "high"
    assert data["manual_review_recommended"] is True
    assert data["veil_risk_band"] in {"critical", "high", "medium", "low"}
    assert isinstance(data["concern_agrees"], bool)
    assert isinstance(data["priority_agrees"], bool)
    assert isinstance(data["recommendation_agrees"], bool)
    assert isinstance(data["overall_agreement"], bool)


def test_comparison_uses_most_recent_review(client):
    client.post("/api/manual-review", json=VALID_REVIEW_PAYLOAD)
    second_payload = dict(VALID_REVIEW_PAYLOAD, manual_priority="low", rationale="revised")
    client.post("/api/manual-review", json=second_payload)

    data = client.get("/api/manual-review/ReviewCorp/comparison").json()
    assert data["manual_priority"] == "low"


# ---------------------------------------------------------------------------
# 5.6 — metrics
# ---------------------------------------------------------------------------

def test_metrics_empty_when_no_reviews_exist(client):
    resp = client.get("/api/manual-review/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_reviews"] == 0
    assert data["comparable_reviews"] == 0
    assert data["concern_agreement_count"] == 0
    assert data["concern_agreement_rate"] is None
    assert data["priority_agreement_count"] == 0
    assert data["priority_agreement_rate"] is None
    assert data["recommendation_agreement_count"] == 0
    assert data["recommendation_agreement_rate"] is None
    assert data["overall_agreement_count"] == 0
    assert data["overall_agreement_rate"] is None


def test_metrics_reflects_submitted_reviews(client):
    client.post("/api/manual-review", json=VALID_REVIEW_PAYLOAD)
    other_payload = dict(VALID_REVIEW_PAYLOAD, entity_name="OtherCorp", rationale="other")
    client.post("/api/manual-review", json=other_payload)

    data = client.get("/api/manual-review/metrics").json()
    assert data["total_reviews"] == 2
    assert data["comparable_reviews"] == 2
    assert 0 <= data["concern_agreement_count"] <= 2
    assert data["concern_agreement_rate"] == pytest.approx(data["concern_agreement_count"] / 2)


# ---------------------------------------------------------------------------
# Isolation from the analytics path
# ---------------------------------------------------------------------------

def test_manual_review_does_not_affect_risk_scores(client, test_db_session):
    """Submitting reviews must not change a single risk_score/risk_band."""
    before = {r["entity_name"]: (r["risk_score"], r["risk_band"]) for r in client.get("/api/risk-scores").json()}

    client.post("/api/manual-review", json=VALID_REVIEW_PAYLOAD)
    client.post("/api/manual-review", json=dict(VALID_REVIEW_PAYLOAD, manual_priority="low", rationale="r2"))

    after = {r["entity_name"]: (r["risk_score"], r["risk_band"]) for r in client.get("/api/risk-scores").json()}
    assert before == after
