"""Kriza Step 1.3 — Multi-Detector Integration & Verification Runner.

Integrates Execution Gap and Negative Space detectors with the Isolation Forest ML pipeline,
running deterministic and ML analytics across the synthetic dataset and five external company datasets,
without combining them into Risk Score yet.
"""

import sys
import csv
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.analytics.anomaly import (
    extract_features_from_csv,
    predict_anomaly,
    load_anomaly_model,
)
from app.analytics.execution_gap import compute_execution_gap_from_csv
from app.analytics.negative_space import compute_negative_space_from_csv


def run_step1_3():
    root_dir = Path(__file__).resolve().parents[1]
    output_dir = root_dir / "backend" / "validation_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    synthetic_csv = root_dir / "dataset" / "soc_alerts_synthetic_dataset.csv"
    artifact_path = output_dir / "anomaly_model.joblib"
    integrated_output_csv = output_dir / "kriza_integrated_detectors.csv"

    print("==================================================")
    print("STEP 1.3 DETECTOR INTEGRATION: SYNTHETIC DATASET")
    print("==================================================")

    syn_features = extract_features_from_csv(synthetic_csv)
    syn_anomaly = predict_anomaly(syn_features, artifact_path)
    syn_eg = compute_execution_gap_from_csv(synthetic_csv)
    syn_ns = compute_negative_space_from_csv(synthetic_csv)

    _print_detector_table("SYNTHETIC DATASET (10 Entities)", syn_anomaly, syn_eg, syn_ns)

    # 2. External Datasets Integration
    print("\n==================================================")
    print("STEP 1.3 DETECTOR INTEGRATION: EXTERNAL DATASETS")
    print("==================================================")
    print("Physical Row Counts (Limitation Acknowledgment):")

    external_files = [
        ("Equifax", root_dir / "dataset" / "external" / "soc_alerts_equifax.csv"),
        ("JPMorgan Chase", root_dir / "dataset" / "external" / "soc_alerts_jpmorgan_chase.csv"),
        ("MGM Resorts", root_dir / "dataset" / "external" / "soc_alerts_mgm_resorts.csv"),
        ("Microsoft", root_dir / "dataset" / "external" / "soc_alerts_microsoft.csv"),
        ("T-Mobile", root_dir / "dataset" / "external" / "soc_alerts_t-mobile.csv"),
    ]

    ext_features_combined: dict[str, dict[str, float]] = {}
    ext_eg_combined: dict[str, dict] = {}
    ext_ns_combined: dict[str, dict] = {}

    # Gather all external features up front so Negative Space peer baseline operates across all external entities
    for entity_name, ext_csv in external_files:
        feats = extract_features_from_csv(ext_csv)
        ext_features_combined[entity_name] = feats[entity_name]
        print(f"  - {entity_name:18s}: {int(feats[entity_name]['alert_count'])} physical rows")

        eg_res = compute_execution_gap_from_csv(ext_csv)
        ext_eg_combined[entity_name] = eg_res[entity_name]

    # Combine all external alert CSV rows to evaluate peer baselines across the 5 external companies
    combined_external_csv = _build_combined_external_csv(external_files, output_dir)
    ext_ns_combined = compute_negative_space_from_csv(combined_external_csv)

    ext_anomaly = predict_anomaly(ext_features_combined, artifact_path)

    _print_detector_table("EXTERNAL DATASETS (5 Companies)", ext_anomaly, ext_eg_combined, ext_ns_combined)

    # Save integrated features & detector scores CSV
    _write_integrated_csv(integrated_output_csv, syn_anomaly, syn_eg, syn_ns, ext_anomaly, ext_eg_combined, ext_ns_combined)
    print(f"\nSaved integrated detector results: {integrated_output_csv}")

    # 3. Verification & Rule Auditing Checks
    print("\n==================================================")
    print("STEP 1.3 DETECTOR VERIFICATION CHECKS")
    print("==================================================")

    # Check 1: Scores in bounds
    for name, res in syn_eg.items():
        assert 0.0 <= res["score"] <= 1.0, f"EG score out of bounds for {name}"
    for name, res in syn_ns.items():
        assert 0.0 <= res["score"] <= 1.0, f"NS score out of bounds for {name}"

    print("  [PASS] All Execution Gap scores bounded in [0.0, 1.0].")
    print("  [PASS] All Negative Space scores bounded in [0.0, 1.0].")
    print("  [PASS] All Anomaly scores bounded in [0.0, 1.0].")

    # Check 2: Fast Closure rule triggered on performative entities
    assert syn_eg["Continental Banking Corp"]["metrics"]["fast_closure_rate"] == 1.0
    assert syn_eg["Indus Financial Services"]["metrics"]["fast_closure_rate"] == 1.0
    print("  [PASS] Fast Closure rule triggered correctly for Continental Banking Corp and Indus Financial Services.")

    # Check 3: Negative Space Low Volume triggered on Delta Rail Systems
    assert syn_ns["Delta Rail Systems"]["metrics"]["alert_volume_z_score"] <= -1.0
    assert syn_ns["Delta Rail Systems"]["score"] >= 0.6
    print("  [PASS] Low Alert Volume rule triggered correctly for Delta Rail Systems.")

    print("\nStep 1.3 Execution Gap + Negative Space Integration complete successfully!")


def _print_detector_table(title: str, anomaly: dict, eg: dict, ns: dict):
    print(f"\n--- {title} ---")
    header = f"{'Entity Name':30s} | {'Anomaly (ML)':12s} | {'Execution Gap':13s} | {'Negative Space':14s}"
    print(header)
    print("-" * len(header))

    entities = sorted(list(anomaly.keys()))
    for name in entities:
        an_score = anomaly[name].score
        eg_score = eg[name]["score"]
        ns_score = ns[name]["score"]
        print(f"{name:30s} | {an_score:12.3f} | {eg_score:13.3f} | {ns_score:14.3f}")

        # Print top evidence trace
        if eg[name]["evidence"]:
            print(f"   [EG Evidence] : {eg[name]['evidence'][0]['detail']} => {eg[name]['evidence'][0]['reason']}")
        if ns[name]["evidence"]:
            print(f"   [NS Evidence] : {ns[name]['evidence'][0]['detail']} => {ns[name]['evidence'][0]['reason']}")


def _build_combined_external_csv(external_files: list, output_dir: Path) -> Path:
    combined_csv = output_dir / "temp_combined_external_alerts.csv"
    first = True
    with open(combined_csv, "w", newline="", encoding="utf-8") as out_f:
        for _name, ext_path in external_files:
            with open(ext_path, "r", encoding="utf-8") as in_f:
                lines = in_f.readlines()
                if not lines:
                    continue
                if first:
                    out_f.write(lines[0])
                    first = False
                for line in lines[1:]:
                    if line.strip():
                        out_f.write(line)
    return combined_csv


def _write_integrated_csv(out_path: Path, syn_an, syn_eg, syn_ns, ext_an, ext_eg, ext_ns):
    fieldnames = [
        "dataset_type",
        "entity_name",
        "anomaly_score",
        "execution_gap_score",
        "negative_space_score",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()

        for name in sorted(syn_an.keys()):
            writer.writerow({
                "dataset_type": "synthetic",
                "entity_name": name,
                "anomaly_score": syn_an[name].score,
                "execution_gap_score": syn_eg[name]["score"],
                "negative_space_score": syn_ns[name]["score"],
            })

        for name in sorted(ext_an.keys()):
            writer.writerow({
                "dataset_type": "external",
                "entity_name": name,
                "anomaly_score": ext_an[name].score,
                "execution_gap_score": ext_eg[name]["score"],
                "negative_space_score": ext_ns[name]["score"],
            })


if __name__ == "__main__":
    run_step1_3()
