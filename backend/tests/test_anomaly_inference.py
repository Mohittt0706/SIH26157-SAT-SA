"""Unit tests for the fresh-fit anomaly detection path."""

from pathlib import Path

import pytest

from app.analytics.anomaly import compute_anomaly_from_features, extract_features_from_csv


@pytest.fixture
def root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def synthetic_csv(root_dir: Path) -> Path:
    return root_dir / "dataset" / "soc_alerts_synthetic_dataset.csv"


def test_fresh_fit_scores_every_entity(synthetic_csv: Path):
    """Fitting fresh on the synthetic dataset's own features scores all 10 entities."""
    features = extract_features_from_csv(synthetic_csv)
    results = compute_anomaly_from_features(features)

    assert len(results) == 10
    for name, res in results.items():
        assert 0.0 <= res.score <= 1.0, f"Score out of bounds for {name}: {res.score}"
        assert len(res.metrics) == 6


def test_invalid_feature_vectors():
    """Missing or NaN feature values raise a clear error instead of silently scoring."""
    bad_features_missing = {
        "BadEntity": {
            "alert_count": 10.0,
            # avg_closure_seconds missing
            "escalation_rate": 0.5,
            "critical_ratio": 0.2,
            "avg_note_length": 50.0,
            "unique_asset_types": 4.0,
        }
    }
    with pytest.raises(KeyError):
        compute_anomaly_from_features(bad_features_missing)

    bad_features_nan = {
        "BadEntity": {
            "alert_count": 10.0,
            "avg_closure_seconds": float("nan"),
            "escalation_rate": 0.5,
            "critical_ratio": 0.2,
            "avg_note_length": 50.0,
            "unique_asset_types": 4.0,
        }
    }
    with pytest.raises(ValueError):
        compute_anomaly_from_features(bad_features_nan)
