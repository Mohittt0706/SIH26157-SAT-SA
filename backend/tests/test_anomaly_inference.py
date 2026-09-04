"""Unit tests for Isolation Forest training, model persistence, and inference pipeline."""

import os
from pathlib import Path
import pytest
import numpy as np

from app.analytics.anomaly import (
    FEATURE_NAMES,
    extract_features_from_csv,
    train_synthetic_model,
    predict_anomaly,
    load_anomaly_model,
)


@pytest.fixture
def root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def synthetic_csv(root_dir: Path) -> Path:
    return root_dir / "dataset" / "soc_alerts_synthetic_dataset.csv"


@pytest.fixture
def model_artifact_path(tmp_path: Path) -> Path:
    return tmp_path / "anomaly_model.joblib"


def test_model_training_and_persistence(synthetic_csv: Path, model_artifact_path: Path):
    """Test model training on synthetic data and joblib persistence."""
    results = train_synthetic_model(synthetic_csv, model_artifact_path)
    
    assert model_artifact_path.exists(), "anomaly_model.joblib was not created"
    assert len(results) == 10, f"Expected 10 entities in training result, got {len(results)}"
    
    model_dict = load_anomaly_model(model_artifact_path)
    assert "scaler" in model_dict
    assert "clf" in model_dict
    assert model_dict["feature_names"] == FEATURE_NAMES
    assert model_dict["hyperparameters"]["n_estimators"] == 200
    assert model_dict["hyperparameters"]["contamination"] == 0.2
    assert model_dict["hyperparameters"]["random_state"] == 42


def test_inference_without_retraining(synthetic_csv: Path, model_artifact_path: Path):
    """Test inference on external features using persisted model without refitting."""
    # Train model on synthetic dataset
    train_synthetic_model(synthetic_csv, model_artifact_path)
    
    # Save original trees/estimators reference to verify zero retraining occurs
    model_dict_before = load_anomaly_model(model_artifact_path)
    clf_before = model_dict_before["clf"]
    estimators_before = list(clf_before.estimators_)

    # Sample external feature vector
    external_features = {
        "Equifax": {
            "alert_count": 8.0,
            "avg_closure_seconds": 10928.57,
            "escalation_rate": 0.5,
            "critical_ratio": 0.25,
            "avg_note_length": 51.38,
            "unique_asset_types": 5.0,
        }
    }

    # Run inference
    inference_results = predict_anomaly(external_features, model_artifact_path)
    
    assert "Equifax" in inference_results
    eqx_res = inference_results["Equifax"]
    assert 0.0 <= eqx_res.score <= 1.0, f"Score out of bounds: {eqx_res.score}"
    assert len(eqx_res.metrics) == 6

    # Verify model estimators were NOT altered/refitted during inference
    model_dict_after = load_anomaly_model(model_artifact_path)
    clf_after = model_dict_after["clf"]
    assert len(clf_after.estimators_) == len(estimators_before)


def test_invalid_feature_vectors(synthetic_csv: Path, model_artifact_path: Path):
    """Test exception handling for missing features or NaN values."""
    train_synthetic_model(synthetic_csv, model_artifact_path)

    # Missing feature
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
        predict_anomaly(bad_features_missing, model_artifact_path)

    # NaN feature value
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
        predict_anomaly(bad_features_nan, model_artifact_path)
