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
    """Tests for the peer baseline helper (median/MAD, not mean/stdev)."""

    def test_excludes_current_entity(self) -> None:
        counts = {"A": 60, "B": 18, "C": 160, "D": 55, "E": 45}
        median, mad = build_peer_baseline(counts, "B")
        # Peer values: 60, 160, 55, 45 → sorted [45, 55, 60, 160]
        assert median == pytest.approx(57.5)
        # abs devs from 57.5: 12.5, 2.5, 2.5, 102.5 → sorted [2.5, 2.5, 12.5, 102.5]
        assert mad == pytest.approx(7.5)

    def test_all_other_entities_excluded(self) -> None:
        counts = {"X": 10, "Y": 10, "Z": 10}
        median, mad = build_peer_baseline(counts, "X")
        assert median == 10.0
        assert mad == 0.0  # only 2 peers, both same → MAD = 0

    def test_single_peer(self) -> None:
        counts = {"A": 50, "B": 100}
        median, mad = build_peer_baseline(counts, "A")
        assert median == 100.0
        assert mad == 0.0  # <2 peers → MAD forced to 0

    def test_no_peers(self) -> None:
        counts = {"A": 42}
        median, mad = build_peer_baseline(counts, "A")
        assert median == 0.0
        assert mad == 0.0

    def test_zero_mad_uniform_peers(self) -> None:
        counts = {"A": 30, "B": 30, "C": 30}
        median, mad = build_peer_baseline(counts, "A")
        assert median == 30.0
        assert mad == 0.0  # all peers identical

    def test_mad_resists_a_single_outlier(self) -> None:
        """A single high-volume outlier peer should not inflate the spread
        the way it would under mean/stdev — this is the whole point of the
        median/MAD switch (see Delta Rail vs. Fortis in production data)."""
        counts = {"A": 0, "B": 10, "C": 20, "D": 1000}
        median, mad = build_peer_baseline(counts, "A")
        # Peers: 10, 20, 1000 → median = 20
        assert median == pytest.approx(20.0)
        # abs devs from 20: 10, 0, 980 → median of those = 10
        assert mad == pytest.approx(10.0)


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
    """Tests for the graded (ramp, not binary) modified-z-score low-volume rule.

    Signal is 0.0 at LOW_VOLUME_Z_THRESHOLD (-1.0), rises linearly to 1.0 at
    LOW_VOLUME_Z_SATURATION (-5.0), and is clamped at both ends.
    """

    def test_signal_partway_up_the_ramp(self) -> None:
        # z = 0.6745 * (18 - 80) / 30 = -1.394
        # fraction = (-1.0 - (-1.394)) / (-1.0 - (-5.0)) = 0.394 / 4.0 = 0.0985
        signal, z, finding = _rule_low_alert_volume(
            entity_alert_count=18, peer_median=80.0, peer_mad=30.0
        )
        assert z == pytest.approx(-1.394, abs=0.01)
        assert signal == pytest.approx(0.0985, abs=0.001)
        assert finding is not None
        assert finding.type == RULE_LOW_ALERT_VOLUME

    def test_signal_zero_above_threshold(self) -> None:
        signal, z, finding = _rule_low_alert_volume(
            entity_alert_count=80, peer_median=80.0, peer_mad=30.0
        )
        assert z == 0.0
        assert signal == 0.0
        assert finding is None

    def test_signal_zero_exactly_at_threshold(self) -> None:
        """No cliff: right at the threshold itself the ramp reads 0.0, same as
        just short of it — continuous with the "not flagged" side."""
        diff = -1.0 / 0.6745
        signal, z, finding = _rule_low_alert_volume(
            entity_alert_count=diff, peer_median=0.0, peer_mad=1.0
        )
        assert z == pytest.approx(-1.0)
        assert signal == pytest.approx(0.0)
        assert finding is None

    def test_signal_saturates_at_saturation_point(self) -> None:
        # Constructed so z lands exactly on LOW_VOLUME_Z_SATURATION (-5.0):
        # diff = -5.0 / MAD_ZSCORE_SCALE.
        diff = -5.0 / 0.6745
        signal, z, finding = _rule_low_alert_volume(
            entity_alert_count=diff, peer_median=0.0, peer_mad=1.0
        )
        assert z == pytest.approx(-5.0)
        assert signal == pytest.approx(1.0)
        assert finding is not None

    def test_signal_clamped_beyond_saturation(self) -> None:
        """Far past saturation (e.g. Delta Rail's z=-5.49) still clamps at 1.0,
        it does not overshoot."""
        diff = -10.0 / 0.6745
        signal, z, finding = _rule_low_alert_volume(
            entity_alert_count=diff, peer_median=0.0, peer_mad=1.0
        )
        assert z == pytest.approx(-10.0)
        assert signal == pytest.approx(1.0)

    def test_zero_mad_below_median(self) -> None:
        """Zero-MAD fallback forces z to exactly -1.0 (the threshold itself),
        so the graded signal is 0.0 there, not the old flat 1.0."""
        signal, z, finding = _rule_low_alert_volume(
            entity_alert_count=10, peer_median=50.0, peer_mad=0.0
        )
        assert z == -1.0
        assert signal == 0.0

    def test_zero_mad_equal_median(self) -> None:
        signal, z, finding = _rule_low_alert_volume(
            entity_alert_count=50, peer_median=50.0, peer_mad=0.0
        )
        assert signal == 0.0

    def test_zero_mad_above_median(self) -> None:
        signal, z, finding = _rule_low_alert_volume(
            entity_alert_count=100, peer_median=50.0, peer_mad=0.0
        )
        assert signal == 0.0


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
        # Entity B has 18 alerts; peers [60, 160, 55, 45] → median = 57.5
        fake_alerts = [FakeAlert("low")] * 18
        result = _compute_for_entity("B", fake_alerts, entity_alert_counts, entity_severity_sets)

        assert result.entity_name == "B"
        assert result.negative_space_score > 0.0
        assert result.metrics["total_alerts"] == 18
        assert result.metrics["peer_median_alerts"] == 57.5
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

        # A has 60 alerts; peers [18, 160, 55, 45] → median 50.0, MAD 18.5
        # → z ≈ 0.36, not significantly low
        # A has all severities peers have → no missing
        assert result.negative_space_score == 0.0
        assert result.evidence == []

    def test_score_bounds(self) -> None:
        entity_alert_counts = {"A": 100, "B": 1}
        entity_severity_sets = {"A": {"low"}, "B": set()}
        fake_alerts = [FakeAlert("low")] * 1
        result = _compute_for_entity("B", fake_alerts, entity_alert_counts, entity_severity_sets)
        assert 0.0 <= result.negative_space_score <= 1.0

    def test_peer_median_excludes_self(self) -> None:
        entity_alert_counts = {"A": 100, "B": 100, "C": 100}
        entity_severity_sets = {"A": {"low"}, "B": {"low"}, "C": {"low"}}
        fake_alerts = [FakeAlert("low")] * 100
        result = _compute_for_entity("A", fake_alerts, entity_alert_counts, entity_severity_sets)
        assert result.metrics["peer_median_alerts"] == 100.0
        assert result.metrics["peer_mad_alerts"] == 0.0
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
