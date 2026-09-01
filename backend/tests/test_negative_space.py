"""Tests for the Negative Space detector."""

from __future__ import annotations

import math

import pytest

from app.analytics.negative_space import (
    LOW_VOLUME_Z_THRESHOLD,
    MIN_PEERS_WITH_SEVERITY,
    RULE_LOW_ALERT_VOLUME,
    RULE_MISSING_EXPECTED_SEVERITY,
    Finding,
    NegativeSpaceResult,
    _compute_for_entity,
    _rule_low_alert_volume,
    _rule_missing_expected_severity,
    build_peer_baseline,
    detect_missing_severities,
)


# ---------------------------------------------------------------------------
# Helpers — lightweight objects that mimic app.models.Alert for unit tests
# ---------------------------------------------------------------------------

class FakeAlert:
    """Minimal stand-in for Alert ORM model used in pure-logic tests."""

    def __init__(self, severity: str) -> None:
        self.severity = severity


# ---------------------------------------------------------------------------
# build_peer_baseline tests
# ---------------------------------------------------------------------------

class TestBuildPeerBaseline:
    """Tests for the peer baseline helper."""

    def test_excludes_current_entity(self) -> None:
        counts = {"A": 60, "B": 18, "C": 160, "D": 55, "E": 45}
        mean, std = build_peer_baseline(counts, "B")
        assert mean == pytest.approx(80.0)
        # Peer values: 60, 160, 55, 45 → stdev(ddof=1)
        assert std > 0.0

    def test_all_other_entities_excluded(self) -> None:
        counts = {"X": 10, "Y": 10, "Z": 10}
        mean, std = build_peer_baseline(counts, "X")
        assert mean == 10.0
        assert std == 0.0  # only 2 peers, both same → stdev = 0

    def test_single_peer(self) -> None:
        counts = {"A": 50, "B": 100}
        mean, std = build_peer_baseline(counts, "A")
        assert mean == 100.0
        assert std == 0.0  # <2 peers → std forced to 0

    def test_no_peers(self) -> None:
        counts = {"A": 42}
        mean, std = build_peer_baseline(counts, "A")
        assert mean == 0.0
        assert std == 0.0

    def test_zero_std_uniform_peers(self) -> None:
        counts = {"A": 30, "B": 30, "C": 30}
        mean, std = build_peer_baseline(counts, "A")
        assert mean == 30.0
        assert std == 0.0  # all peers identical

    def test_sample_stddev_used(self) -> None:
        """Verify sample standard deviation (ddof=1) is used."""
        counts = {"A": 0, "B": 10, "C": 20}
        mean, std = build_peer_baseline(counts, "A")
        assert mean == 15.0
        # sample stdev of [10, 20] = 7.071...
        assert std == pytest.approx(7.071, abs=0.01)


# ---------------------------------------------------------------------------
# detect_missing_severities tests
# ---------------------------------------------------------------------------

class TestDetectMissingSeverities:
    """Tests for missing severity detection."""

    def test_case_insensitive(self) -> None:
        entity_sevs = {
            "A": {"critical", "high"},
            "B": {"critical", "high", "medium"},
            "C": {"critical", "high", "medium"},
        }
        missing = detect_missing_severities(entity_sevs, "A")
        assert "medium" in missing

    def test_no_missing(self) -> None:
        entity_sevs = {
            "A": {"low", "medium", "high"},
            "B": {"low", "medium", "high"},
            "C": {"low", "medium", "high"},
        }
        missing = detect_missing_severities(entity_sevs, "A")
        assert missing == []

    def test_insufficient_peers_not_expected(self) -> None:
        """A severity in only 1 peer should NOT be flagged as expected."""
        entity_sevs = {
            "A": {"low"},
            "B": {"low", "medium"},
            "C": {"low"},
        }
        missing = detect_missing_severities(entity_sevs, "A")
        # 'medium' appears in only 1 peer → below MIN_PEERS_WITH_SEVERITY
        assert missing == []

    def test_no_peers(self) -> None:
        entity_sevs = {"A": {"low"}}
        missing = detect_missing_severities(entity_sevs, "A")
        assert missing == []

    def test_multiple_missing(self) -> None:
        entity_sevs = {
            "A": set(),
            "B": {"low", "high"},
            "C": {"low", "high"},
        }
        missing = detect_missing_severities(entity_sevs, "A")
        assert "low" in missing
        assert "high" in missing

    def test_severity_normalised_to_lowercase(self) -> None:
        entity_sevs = {
            "A": set(),
            "B": {"Critical", "HIGH"},
            "C": {"Critical", "HIGH"},
        }
        missing = detect_missing_severities(entity_sevs, "A")
        assert "critical" in missing
        assert "high" in missing


# ---------------------------------------------------------------------------
# _rule_low_alert_volume tests
# ---------------------------------------------------------------------------

class TestRuleLowAlertVolume:

    def test_triggered_when_z_below_threshold(self) -> None:
        triggered, z, finding = _rule_low_alert_volume(
            entity_alert_count=18, peer_mean=80.0, peer_std=50.0
        )
        assert triggered is True
        assert z == pytest.approx(-1.24, abs=0.01)
        assert finding is not None
        assert finding.type == RULE_LOW_ALERT_VOLUME

    def test_not_triggered_when_z_above_threshold(self) -> None:
        triggered, z, finding = _rule_low_alert_volume(
            entity_alert_count=80, peer_mean=80.0, peer_std=50.0
        )
        assert triggered is False
        assert finding is None

    def test_zero_std_below_mean(self) -> None:
        triggered, z, finding = _rule_low_alert_volume(
            entity_alert_count=10, peer_mean=50.0, peer_std=0.0
        )
        assert triggered is True  # z forced to -1.0

    def test_zero_std_equal_mean(self) -> None:
        triggered, z, finding = _rule_low_alert_volume(
            entity_alert_count=50, peer_mean=50.0, peer_std=0.0
        )
        assert triggered is False

    def test_zero_std_above_mean(self) -> None:
        triggered, z, finding = _rule_low_alert_volume(
            entity_alert_count=100, peer_mean=50.0, peer_std=0.0
        )
        assert triggered is False

    def test_boundary_z_equals_threshold(self) -> None:
        """At exactly z = -1.0 the rule should trigger (<=)."""
        # z = (10 - 50) / 40 = -1.0
        triggered, z, finding = _rule_low_alert_volume(
            entity_alert_count=10, peer_mean=50.0, peer_std=40.0
        )
        assert triggered is True
        assert z == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# _rule_missing_expected_severity tests
# ---------------------------------------------------------------------------

class TestRuleMissingExpectedSeverity:

    def test_no_expected(self) -> None:
        signal, findings = _rule_missing_expected_severity(
            current_severities={"low"}, missing_severities=[], total_expected=0
        )
        assert signal == 0.0
        assert findings == []

    def test_one_missing_of_two(self) -> None:
        signal, findings = _rule_missing_expected_severity(
            current_severities={"high"},
            missing_severities=["medium"],
            total_expected=2,
        )
        assert signal == pytest.approx(0.5)
        assert len(findings) == 1
        assert findings[0].type == RULE_MISSING_EXPECTED_SEVERITY

    def test_all_present(self) -> None:
        signal, findings = _rule_missing_expected_severity(
            current_severities={"low", "medium"},
            missing_severities=[],
            total_expected=2,
        )
        assert signal == 0.0
        assert findings == []


# ---------------------------------------------------------------------------
# _compute_for_entity integration tests
# ---------------------------------------------------------------------------

class TestComputeForEntity:

    def test_low_volume_and_missing_severity(self) -> None:
        entity_alert_counts = {"A": 60, "B": 18, "C": 160, "D": 55, "E": 45}
        entity_severity_sets = {
            "A": {"low", "medium", "high"},
            "B": {"low"},
            "C": {"low", "medium", "high"},
            "D": {"low", "medium", "high"},
            "E": {"low", "medium"},
        }
        # Entity B has 18 alerts, peer mean = (60+160+55+45)/4 = 80.0
        fake_alerts = [FakeAlert("low")] * 18
        result = _compute_for_entity("B", fake_alerts, entity_alert_counts, entity_severity_sets)

        assert result.entity_name == "B"
        assert result.negative_space_score > 0.0
        assert result.metrics["total_alerts"] == 18
        assert result.metrics["peer_mean_alerts"] == 80.0
        rule_types = [f.type for f in result.evidence]
        assert RULE_LOW_ALERT_VOLUME in rule_types
        assert RULE_MISSING_EXPECTED_SEVERITY in rule_types

    def test_no_finding_for_normal_entity(self) -> None:
        entity_alert_counts = {"A": 60, "B": 18, "C": 160, "D": 55, "E": 45}
        entity_severity_sets = {
            "A": {"low", "medium", "high"},
            "B": {"low"},
            "C": {"low", "medium", "high"},
            "D": {"low", "medium", "high"},
            "E": {"low", "medium"},
        }
        fake_alerts = [FakeAlert("low")] * 60
        result = _compute_for_entity("A", fake_alerts, entity_alert_counts, entity_severity_sets)

        # A has 60 alerts vs peer mean 69.75 → z is not significantly low
        # A has all severities peers have → no missing
        assert result.negative_space_score == 0.0
        assert result.evidence == []

    def test_score_bounds(self) -> None:
        entity_alert_counts = {"A": 100, "B": 1}
        entity_severity_sets = {"A": {"low"}, "B": set()}
        fake_alerts = [FakeAlert("low")] * 1
        result = _compute_for_entity("B", fake_alerts, entity_alert_counts, entity_severity_sets)
        assert 0.0 <= result.negative_space_score <= 1.0

    def test_peer_mean_excludes_self(self) -> None:
        entity_alert_counts = {"A": 100, "B": 100, "C": 100}
        entity_severity_sets = {"A": {"low"}, "B": {"low"}, "C": {"low"}}
        fake_alerts = [FakeAlert("low")] * 100
        result = _compute_for_entity("A", fake_alerts, entity_alert_counts, entity_severity_sets)
        assert result.metrics["peer_mean_alerts"] == 100.0
        assert result.metrics["peer_std_alerts"] == 0.0
        assert result.negative_space_score == 0.0


# ---------------------------------------------------------------------------
# Score clamping tests
# ---------------------------------------------------------------------------

class TestScoreClamping:

    def test_score_never_exceeds_one(self) -> None:
        """Even with extreme inputs the score must be ≤ 1.0."""
        entity_alert_counts = {"A": 1000, "B": 1}
        entity_severity_sets = {"A": {"low", "medium", "high", "critical"}, "B": set()}
        fake_alerts = [FakeAlert("low")] * 1
        result = _compute_for_entity("B", fake_alerts, entity_alert_counts, entity_severity_sets)
        assert result.negative_space_score <= 1.0

    def test_score_never_negative(self) -> None:
        entity_alert_counts = {"A": 0, "B": 100}
        entity_severity_sets = {"A": {"low"}, "B": {"low"}}
        fake_alerts = [FakeAlert("low")] * 100
        result = _compute_for_entity("B", fake_alerts, entity_alert_counts, entity_severity_sets)
        assert result.negative_space_score >= 0.0


# ---------------------------------------------------------------------------
# Evidence structure tests
# ---------------------------------------------------------------------------

class TestEvidenceStructure:

    def test_evidence_has_required_fields(self) -> None:
        entity_alert_counts = {"A": 60, "B": 10}
        entity_severity_sets = {"A": {"low", "medium"}, "B": {"low"}}
        fake_alerts = [FakeAlert("low")] * 10
        result = _compute_for_entity("B", fake_alerts, entity_alert_counts, entity_severity_sets)
        for f in result.evidence:
            assert hasattr(f, "type")
            assert hasattr(f, "detail")
            assert hasattr(f, "reason")
            assert isinstance(f.type, str)
            assert isinstance(f.detail, str)
            assert isinstance(f.reason, str)
            assert len(f.detail) > 0
            assert len(f.reason) > 0

    def test_no_fake_evidence_when_no_signal(self) -> None:
        entity_alert_counts = {"A": 50, "B": 50}
        entity_severity_sets = {"A": {"low"}, "B": {"low"}}
        fake_alerts = [FakeAlert("low")] * 50
        result = _compute_for_entity("A", fake_alerts, entity_alert_counts, entity_severity_sets)
        assert result.evidence == []
