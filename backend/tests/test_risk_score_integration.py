"""Unit tests for Risk Score, Soft Floor, Risk Band, and Primary Driver integration."""

import pytest
from pathlib import Path

from app.analytics.risk_score import (
    WEIGHT_EXECUTION_GAP,
    WEIGHT_NEGATIVE_SPACE,
    WEIGHT_ANOMALY,
    FLOOR_ATTENUATION,
    RISK_BAND_CRITICAL_THRESHOLD,
    RISK_BAND_HIGH_THRESHOLD,
    RISK_BAND_MEDIUM_THRESHOLD,
    _combine_entity,
    _risk_band,
    _apply_max_detector_floor,
    compute_risk_scores_from_csv,
)
from app.analytics.anomaly import train_synthetic_model


@pytest.fixture
def root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def synthetic_csv(root_dir: Path) -> Path:
    return root_dir / "dataset" / "soc_alerts_synthetic_dataset.csv"


@pytest.fixture
def model_artifact_path(tmp_path: Path) -> Path:
    p = tmp_path / "anomaly_model.joblib"
    train_synthetic_model(
        Path(__file__).resolve().parents[2] / "dataset" / "soc_alerts_synthetic_dataset.csv",
        p,
    )
    return p


def test_weights_sum():
    """Verify weights sum to 1.0."""
    assert WEIGHT_EXECUTION_GAP == 0.40
    assert WEIGHT_NEGATIVE_SPACE == 0.35
    assert WEIGHT_ANOMALY == 0.25
    assert round(WEIGHT_EXECUTION_GAP + WEIGHT_NEGATIVE_SPACE + WEIGHT_ANOMALY, 2) == 1.00


def test_risk_band_thresholds():
    """Test boundary conditions for Risk Bands."""
    assert _risk_band(0.0) == "low"
    assert _risk_band(19.9) == "low"
    assert _risk_band(20.0) == "medium"
    assert _risk_band(44.9) == "medium"
    assert _risk_band(45.0) == "high"
    assert _risk_band(69.9) == "high"
    assert _risk_band(70.0) == "critical"
    assert _risk_band(100.0) == "critical"


def test_risk_score_weighted_sum_and_soft_floor():
    """Test manual arithmetic for weighted sum and soft floor attenuation."""
    # Case 1: Standard weighted sum dominates floor
    # EG=0.5, NS=0.4, AN=0.3
    # Weighted sum = 0.40*0.5 + 0.35*0.4 + 0.25*0.3 = 0.20 + 0.14 + 0.075 = 0.415
    # Floor = max(0.5, 0.4, 0.3) * 0.85 = 0.5 * 0.85 = 0.425 -> Floor dominates!
    eg = {"score": 0.5, "metrics": {}, "evidence": []}
    ns = {"score": 0.4, "metrics": {}, "evidence": []}
    an = {"score": 0.3, "metrics": {}, "evidence": []}

    res = _combine_entity("TestEntity", eg, ns, an)
    assert res["risk_score"] == 42.5  # 0.425 * 100
    assert res["risk_band"] == "medium"
    assert res["primary_driver"] == "execution_gap"  # contrib: EG=0.20 vs NS=0.14 vs AN=0.075

    # Case 2: Single detector high at 1.000, others 0.0
    # EG=0.0, NS=0.0, AN=1.000
    # Weighted sum = 0.25
    # Floor = 1.000 * 0.85 = 0.85 -> risk score = 85.0 (critical)
    eg_zero = {"score": 0.0, "metrics": {}, "evidence": []}
    ns_zero = {"score": 0.0, "metrics": {}, "evidence": []}
    an_high = {"score": 1.0, "metrics": {}, "evidence": []}

    res_soft = _combine_entity("SingleHighEntity", eg_zero, ns_zero, an_high)
    assert res_soft["risk_score"] == 85.0
    assert res_soft["risk_band"] == "critical"
    assert res_soft["primary_driver"] == "anomaly"  # contrib: AN=0.25 vs 0.0


def test_zero_detector_scores():
    """Verify behavior when all detectors return 0.0."""
    zero_res = {"score": 0.0, "metrics": {}, "evidence": []}
    res = _combine_entity("ZeroCorp", zero_res, zero_res, zero_res)
    assert res["risk_score"] == 0.0
    assert res["risk_band"] == "low"


def test_csv_risk_pipeline(synthetic_csv: Path, model_artifact_path: Path):
    """Test full CSV risk pipeline integration."""
    rows = compute_risk_scores_from_csv(synthetic_csv, model_artifact_path)
    assert len(rows) == 10
    for r in rows:
        assert "risk_score" in r
        assert "risk_band" in r
        assert "primary_driver" in r
        assert "evidence" in r
        assert 0.0 <= r["risk_score"] <= 100.0
        assert r["risk_band"] in ("critical", "high", "medium", "low")
        assert r["primary_driver"] in ("execution_gap", "negative_space", "anomaly")
