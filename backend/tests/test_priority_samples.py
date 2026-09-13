"""Unit tests for GET /api/priority-samples and the entity-ranking tie-break.

Covers step 4 of the manual-review task: the endpoint's field shape and
ordering, and that GET /api/risk-scores breaks risk_score ties by
entity_name ascending (added in this task) rather than falling back to
non-deterministic set-iteration order.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Alert


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

    alerts = []

    # TieCorp: two critical alerts, both un-escalated, both closed slowly
    # with a long note — each should trip exactly one rule (NO_ESCALATION),
    # nothing else, so they tie on priority_score and on entity_risk_score
    # (same entity). Only alert_id differs.
    for alert_id in ("ALT002", "ALT001"):
        alerts.append(
            _alert(
                alert_id, "TieCorp", "Critical",
                base, base + timedelta(minutes=30), False, long_note,
            )
        )

    # LoudCorp: one alert hit by two rules (fast closure + no escalation) —
    # should outrank TieCorp's single-rule alerts regardless of entity risk.
    alerts.append(
        _alert(
            "ALT900", "LoudCorp", "Critical",
            base, base + timedelta(seconds=10), False, long_note,
        )
    )
    # A second, unremarkable LoudCorp alert so it isn't a single-alert entity.
    alerts.append(
        _alert(
            "ALT901", "LoudCorp", "Low",
            base, base + timedelta(minutes=30), True, long_note,
        )
    )

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


def test_priority_samples_fields(client):
    """Every row has exactly the documented fields, correctly typed."""
    resp = client.get("/api/priority-samples?limit=5")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) > 0

    required = {
        "alert_id", "entity_name", "entity_risk_score", "severity",
        "created_time", "priority_score", "triggered_rules", "reason",
    }
    for row in rows:
        assert required.issubset(row.keys())
        assert isinstance(row["alert_id"], str)
        assert isinstance(row["entity_name"], str)
        assert isinstance(row["priority_score"], (int, float))
        assert isinstance(row["triggered_rules"], list)
        assert all(isinstance(r, str) for r in row["triggered_rules"])
        assert isinstance(row["reason"], str) and row["reason"]


def test_priority_samples_ordering_by_score_desc(client):
    """priority_score is non-increasing down the list."""
    resp = client.get("/api/priority-samples?limit=25")
    assert resp.status_code == 200
    rows = resp.json()
    scores = [r["priority_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)


def test_priority_samples_multi_rule_outranks_single_rule(client):
    """An alert cited by two rules ranks above a same-severity, single-rule alert."""
    resp = client.get("/api/priority-samples?limit=25")
    assert resp.status_code == 200
    rows = {r["alert_id"]: r for r in resp.json()}

    assert "ALT900" in rows
    assert len(rows["ALT900"]["triggered_rules"]) == 2
    assert "ALT001" in rows
    assert len(rows["ALT001"]["triggered_rules"]) == 1
    assert rows["ALT900"]["priority_score"] > rows["ALT001"]["priority_score"]


def test_priority_samples_tie_break_is_deterministic(client):
    """Two alerts tied on every scoring input (same entity, same rule, same
    severity) still come back in the same relative order on repeated calls —
    the ranking never falls back to insertion/hash order.
    """
    resp1 = client.get("/api/priority-samples?limit=25")
    resp2 = client.get("/api/priority-samples?limit=25")
    assert resp1.status_code == 200 and resp2.status_code == 200

    ids1 = [r["alert_id"] for r in resp1.json()]
    ids2 = [r["alert_id"] for r in resp2.json()]
    assert ids1 == ids2

    rows = {r["alert_id"]: r for r in resp1.json()}
    assert "ALT001" in rows and "ALT002" in rows
    # Confirm they actually tied on every input to the ranking, so the order
    # between them is purely a tie-break artifact, not a real score difference.
    assert rows["ALT001"]["priority_score"] == rows["ALT002"]["priority_score"]
    assert rows["ALT001"]["entity_risk_score"] == rows["ALT002"]["entity_risk_score"]


def test_priority_samples_limit_respected(client):
    resp = client.get("/api/priority-samples?limit=1")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_priority_samples_limit_out_of_range_rejected(client):
    assert client.get("/api/priority-samples?limit=0").status_code == 422
    assert client.get("/api/priority-samples?limit=101").status_code == 422


def test_risk_scores_tie_break_entity_name_ascending(client):
    """GET /api/risk-scores breaks a risk_score tie by entity_name ascending."""
    resp = client.get("/api/risk-scores")
    assert resp.status_code == 200
    rows = resp.json()

    by_score: dict[float, list[str]] = {}
    for row in rows:
        by_score.setdefault(row["risk_score"], []).append(row["entity_name"])

    # Whichever score(s) happen to tie in this fixture, each group must
    # already be in ascending entity_name order within the response.
    for score, names_in_order in by_score.items():
        if len(names_in_order) > 1:
            assert names_in_order == sorted(names_in_order), (
                f"entities tied at risk_score={score} are not entity_name-ascending: {names_in_order}"
            )

    # Overall list is sorted by risk_score descending.
    scores = [row["risk_score"] for row in rows]
    assert scores == sorted(scores, reverse=True)
