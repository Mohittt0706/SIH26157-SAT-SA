"""Unit tests for Step 1.5 external dataset testing and end-to-end pipeline verification."""

import pytest
from pathlib import Path

from app.analytics.anomaly import extract_features_from_csv
from app.analytics.execution_gap import compute_execution_gap_from_csv
from app.analytics.negative_space import compute_negative_space_from_csv
from app.analytics.risk_score import compute_risk_scores_from_csv


@pytest.fixture
def root_dir() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture
def synthetic_csv(root_dir: Path) -> Path:
    return root_dir / "dataset" / "soc_alerts_synthetic_dataset.csv"


@pytest.fixture
def external_files(root_dir: Path) -> list[tuple[str, Path]]:
    ext_dir = root_dir / "dataset" / "external"
    return [
        ("Equifax", ext_dir / "soc_alerts_equifax.csv"),
        ("JPMorgan Chase", ext_dir / "soc_alerts_jpmorgan_chase.csv"),
        ("MGM Resorts", ext_dir / "soc_alerts_mgm_resorts.csv"),
        ("Microsoft", ext_dir / "soc_alerts_microsoft.csv"),
        ("T-Mobile", ext_dir / "soc_alerts_t-mobile.csv"),
    ]


def test_external_datasets_exist_and_load(external_files: list[tuple[str, Path]]):
    """Verify all 5 external CSV datasets exist and load successfully."""
    for entity_name, fpath in external_files:
        assert fpath.exists(), f"External dataset missing: {fpath}"
        feats = extract_features_from_csv(fpath)
        assert entity_name in feats
        assert len(feats[entity_name]) == 6


def test_end_to_end_external_pipeline(external_files: list[tuple[str, Path]], root_dir: Path):
    """Test full end-to-end pipeline execution on external datasets."""
    # Combine external files to run peer baseline negative space
    output_dir = root_dir / "backend" / "validation_outputs"
    combined_csv = output_dir / "temp_test_combined_external.csv"
    
    first = True
    with open(combined_csv, "w", newline="", encoding="utf-8") as out_f:
        for _name, ext_path in external_files:
            with open(ext_path, "r", encoding="utf-8") as in_f:
                lines = in_f.readlines()
                if first:
                    out_f.write(lines[0])
                    first = False
                for line in lines[1:]:
                    if line.strip():
                        out_f.write(line)

    risk_rows = compute_risk_scores_from_csv(combined_csv)
    assert len(risk_rows) == 5

    for row in risk_rows:
        assert "entity_name" in row
        assert "risk_score" in row
        assert "risk_band" in row
        assert "primary_driver" in row
        assert "execution_gap_score" in row
        assert "negative_space_score" in row
        assert "anomaly_score" in row
        assert "evidence" in row
        assert 0.0 <= row["risk_score"] <= 100.0
        assert row["risk_band"] in ("critical", "high", "medium", "low")
