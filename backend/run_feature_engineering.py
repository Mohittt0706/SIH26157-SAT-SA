"""Kriza Step 1.1 — Feature Engineering Runner & Verification Script.

Processes synthetic SOC alerts dataset and five external company datasets,
extracts the exact six entity-level features in consistent order, and saves
the feature output files for inspection without altering raw CSVs or existing validation files.
"""

import csv
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.analytics.anomaly import FEATURE_NAMES, extract_features_from_csv


def run_feature_engineering():
    root_dir = Path(__file__).resolve().parents[1]
    output_dir = root_dir / "backend" / "validation_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Main Synthetic Dataset
    synthetic_csv = root_dir / "dataset" / "soc_alerts_synthetic_dataset.csv"
    synthetic_output_csv = output_dir / "kriza_synthetic_features.csv"

    print("==================================================")
    print("STEP 1.1 FEATURE ENGINEERING: SYNTHETIC DATASET")
    print("==================================================")
    print(f"Loading raw dataset: {synthetic_csv}")

    syn_features = extract_features_from_csv(synthetic_csv)
    print(f"Entities detected ({len(syn_features)}): {list(syn_features.keys())}\n")

    _write_feature_csv(synthetic_output_csv, syn_features)
    print(f"Saved synthetic feature output: {synthetic_output_csv}\n")

    # 2. External Datasets
    external_dir = root_dir / "dataset" / "external"
    external_files = [
        external_dir / "soc_alerts_equifax.csv",
        external_dir / "soc_alerts_jpmorgan_chase.csv",
        external_dir / "soc_alerts_mgm_resorts.csv",
        external_dir / "soc_alerts_microsoft.csv",
        external_dir / "soc_alerts_t-mobile.csv",
    ]

    print("==================================================")
    print("STEP 1.1 FEATURE ENGINEERING: EXTERNAL DATASETS")
    print("==================================================")

    combined_external_features: dict[str, dict[str, float]] = {}

    for ext_csv in external_files:
        if not ext_csv.exists():
            print(f"ERROR: File not found: {ext_csv}", file=sys.stderr)
            sys.exit(1)

        print(f"\nProcessing external dataset: {ext_csv.name}")
        ext_feat_map = extract_features_from_csv(ext_csv)

        for entity, f_dict in ext_feat_map.items():
            combined_external_features[entity] = f_dict
            print(f"  Entity: {entity}")
            for feat_name in FEATURE_NAMES:
                val = f_dict[feat_name]
                print(f"    - {feat_name}: {val} (type={type(val).__name__})")

    external_output_csv = output_dir / "kriza_external_features.csv"
    _write_feature_csv(external_output_csv, combined_external_features)
    print(f"\nSaved combined external feature output: {external_output_csv}\n")

    # 3. Verification & Validation Checks
    print("==================================================")
    print("FEATURE ENGINEERING VERIFICATION")
    print("==================================================")
    
    all_datasets = [
        ("Synthetic Dataset", synthetic_csv, syn_features),
        ("Combined External", external_dir, combined_external_features),
    ]

    for name, path, feat_map in all_datasets:
        print(f"\nChecking dataset group: {name}")
        for entity, f_dict in feat_map.items():
            # Check 1: Feature keys match exact list & order
            keys = list(f_dict.keys())
            assert keys == FEATURE_NAMES, f"Mismatch in feature keys or order for {entity}: {keys}"
            
            # Check 2: All values numeric
            for k, v in f_dict.items():
                assert isinstance(v, (int, float)), f"Non-numeric value for {entity}.{k}: {v}"
                assert not (isinstance(v, float) and (v != v)), f"NaN value found for {entity}.{k}"
        
        print(f"  [PASS] All {len(feat_map)} entities in {name} passed validation.")

    print("\nFeature Engineering Step 1.1 complete successfully!")


def _write_feature_csv(output_path: Path, features_by_entity: dict[str, dict[str, float]]):
    fieldnames = ["entity_name"] + FEATURE_NAMES
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for entity_name in sorted(features_by_entity.keys()):
            row = {"entity_name": entity_name}
            row.update(features_by_entity[entity_name])
            writer.writerow(row)


if __name__ == "__main__":
    run_feature_engineering()
