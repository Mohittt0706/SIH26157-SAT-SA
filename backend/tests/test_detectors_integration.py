"""Unit tests for Execution Gap and Negative Space detector verification & integration."""

import pytest
from pathlib import Path

from app.analytics.anomaly import _CsvAlert, extract_features_from_csv
from app.analytics.execution_gap import (
    FAST_CLOSURE_WEIGHT,
    NO_ESCALATION_WEIGHT,
    TEMPLATE_NOTES_WEIGHT,
    compute_execution_gap_from_csv,
    _fast_closure_rule,
    _no_escalation_rule,
    _template_notes_rule,
)
from app.analytics.negative_space import (
    LOW_VOLUME_WEIGHT,
    MISSING_SEVERITY_WEIGHT,
    compute_negative_space_from_csv,
    build_peer_baseline,
    detect_missing_severities,
)


@pytest.fixture
def root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def synthetic_csv(root_dir: Path) -> Path:
    return root_dir / "dataset" / "soc_alerts_synthetic_dataset.csv"


def test_detector_weights():
    """Verify exact detector rule weights specified in project requirements."""
    assert FAST_CLOSURE_WEIGHT == 0.4
    assert NO_ESCALATION_WEIGHT == 0.3
    assert TEMPLATE_NOTES_WEIGHT == 0.3
    assert FAST_CLOSURE_WEIGHT + NO_ESCALATION_WEIGHT + TEMPLATE_NOTES_WEIGHT == 1.0

    assert LOW_VOLUME_WEIGHT == 0.6
    assert MISSING_SEVERITY_WEIGHT == 0.4
    assert LOW_VOLUME_WEIGHT + MISSING_SEVERITY_WEIGHT == 1.0


def test_fast_closure_rule():
    """Verify fast closure rule triggers on critical/high alerts closed in < 300s."""
    raw_row_fast = {
        "alert_id": "ALT_FAST",
        "entity_name": "TestCorp",
        "severity": "Critical",
        "created_time": "2026-01-01 10:00:00",
        "closed_time": "2026-01-01 10:02:00",  # 120s < 300s
        "closure_duration_minutes": "2",
        "escalated": "No",
        "investigation_notes": "Fast close test note long enough for min length",
        "asset_type": "Server",
    }
    raw_row_open = {
        "alert_id": "ALT_OPEN",
        "entity_name": "TestCorp",
        "severity": "Critical",
        "created_time": "2026-01-01 10:00:00",
        "closed_time": "",  # Open alert
        "closure_duration_minutes": "",
        "escalated": "No",
        "investigation_notes": "Open alert test note long enough for min length",
        "asset_type": "Server",
    }

    alerts = [_CsvAlert(raw_row_fast), _CsvAlert(raw_row_open)]
    rate, evidence = _fast_closure_rule(alerts)

    assert rate == 1.0  # 1 fast closure out of 1 closed candidate
    assert len(evidence) == 1
    assert evidence[0].alert_id == "ALT_FAST"
    assert "closed in 120s" in evidence[0].reason or "closed in 120" in evidence[0].reason


def test_no_escalation_rule():
    """Verify no escalation rule triggers on un-escalated Critical alerts."""
    raw_crit_unescalated = {
        "alert_id": "ALT_NO_ESC",
        "entity_name": "TestCorp",
        "severity": "Critical",
        "escalated": "No",
        "investigation_notes": "Test investigation note string long enough",
        "asset_type": "Database",
    }
    raw_crit_escalated = {
        "alert_id": "ALT_ESC",
        "entity_name": "TestCorp",
        "severity": "Critical",
        "escalated": "Yes",
        "investigation_notes": "Test investigation note string long enough",
        "asset_type": "Database",
    }

    alerts = [_CsvAlert(raw_crit_unescalated), _CsvAlert(raw_crit_escalated)]
    rate, evidence = _no_escalation_rule(alerts)

    assert rate == 0.5  # 1 out of 2 critical alerts un-escalated
    assert len(evidence) == 1
    assert evidence[0].alert_id == "ALT_NO_ESC"


def test_negative_space_peer_baseline():
    """Verify peer mean and std dev calculation excluding current entity."""
    counts = {"A": 10, "B": 20, "C": 30}
    peer_mean, peer_std = build_peer_baseline(counts, "A")
    assert peer_mean == 25.0  # mean of 20 and 30
    assert peer_std > 0.0


def test_missing_expected_severity():
    """Verify missing severity is detected when >= 2 peers have it."""
    sev_sets = {
        "Entity1": {"critical", "high", "medium", "low"},
        "Entity2": {"critical", "high", "medium"},
        "Entity3": {"low"},  # Missing critical, high, medium
    }
    missing = detect_missing_severities(sev_sets, "Entity3")
    assert "critical" in missing
    assert "high" in missing


def test_csv_detector_integration(synthetic_csv: Path):
    """Test full CSV detector integration for Execution Gap and Negative Space."""
    eg_results = compute_execution_gap_from_csv(synthetic_csv)
    ns_results = compute_negative_space_from_csv(synthetic_csv)

    assert len(eg_results) == 10
    assert len(ns_results) == 10

    for entity, res in eg_results.items():
        assert "score" in res
        assert "metrics" in res
        assert "evidence" in res
        assert 0.0 <= res["score"] <= 1.0

    for entity, res in ns_results.items():
        assert "score" in res
        assert "metrics" in res
        assert "evidence" in res
        assert 0.0 <= res["score"] <= 1.0
