"""Kriza Step 1.4 — Risk Score & Risk Band Integration Runner.

Combines Isolation Forest anomaly scores, Execution Gap scores, and Negative Space scores into
the unified 0-100 Risk Score and Risk Band system, executing boundary tests and arithmetic checks.
"""

import sys
import csv
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.analytics.risk_score import (
    WEIGHT_EXECUTION_GAP,
    WEIGHT_NEGATIVE_SPACE,
    WEIGHT_ANOMALY,
    FLOOR_ATTENUATION,
    RISK_BAND_CRITICAL_THRESHOLD,
    RISK_BAND_HIGH_THRESHOLD,
    RISK_BAND_MEDIUM_THRESHOLD,
    compute_risk_scores_from_csv,
    _risk_band,
    _combine_entity,
)


def run_step1_4():
    root_dir = Path(__file__).resolve().parents[1]
    output_dir = root_dir / "backend" / "validation_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    synthetic_csv = root_dir / "dataset" / "soc_alerts_synthetic_dataset.csv"
    output_csv = output_dir / "kriza_risk_scores.csv"

    print("==================================================")
    print("STEP 1.4 RISK SCORE INTEGRATION: SYNTHETIC DATASET")
    print("==================================================")
    print(f"Risk Score Formula: {WEIGHT_EXECUTION_GAP}*EG + {WEIGHT_NEGATIVE_SPACE}*NS + {WEIGHT_ANOMALY}*Anomaly")
    print(f"Soft Floor Rule   : max(weighted_sum, highest_score * {FLOOR_ATTENUATION}) * 100")
    print(f"Risk Bands        : Critical (>= {RISK_BAND_CRITICAL_THRESHOLD}), High (>= {RISK_BAND_HIGH_THRESHOLD}), Medium (>= {RISK_BAND_MEDIUM_THRESHOLD}), Low (< {RISK_BAND_MEDIUM_THRESHOLD})\n")

    syn_risk_rows = compute_risk_scores_from_csv(synthetic_csv)

    _print_risk_table("SYNTHETIC DATASET (10 Entities)", syn_risk_rows)

    # 2. External Datasets Risk Calculation
    print("\n==================================================")
    print("STEP 1.4 RISK SCORE INTEGRATION: EXTERNAL DATASETS")
    print("==================================================")
    print("Physical Row Counts (Limitation Acknowledgment):")

    external_files = [
        ("Equifax", root_dir / "dataset" / "external" / "soc_alerts_equifax.csv"),
        ("JPMorgan Chase", root_dir / "dataset" / "external" / "soc_alerts_jpmorgan_chase.csv"),
        ("MGM Resorts", root_dir / "dataset" / "external" / "soc_alerts_mgm_resorts.csv"),
        ("Microsoft", root_dir / "dataset" / "external" / "soc_alerts_microsoft.csv"),
        ("T-Mobile", root_dir / "dataset" / "external" / "soc_alerts_t-mobile.csv"),
    ]

    ext_risk_rows_all: list[dict] = []
    # Build a combined external CSV so Negative Space peer baseline operates across all external entities
    combined_ext_csv = _build_combined_external_csv(external_files, output_dir)
    ext_risk_rows_all = compute_risk_scores_from_csv(combined_ext_csv)

    _print_risk_table("EXTERNAL DATASETS (5 Companies)", ext_risk_rows_all)

    # Save output CSV
    _write_risk_csv(output_csv, syn_risk_rows, ext_risk_rows_all)
    print(f"\nSaved integrated risk score results: {output_csv}")

    # 3. Manual Arithmetic & Soft Floor Verification
    print("\n==================================================")
    print("ARITHMETIC & SOFT FLOOR VERIFICATION")
    print("==================================================")
    
    # Verify Delta Rail Systems (High Anomaly + High NS + Zero EG)
    delta_row = next(r for r in syn_risk_rows if r["entity_name"] == "Delta Rail Systems")
    eg = delta_row["execution_gap_score"]
    ns = delta_row["negative_space_score"]
    an = delta_row["anomaly_score"]
    w_sum = WEIGHT_EXECUTION_GAP * eg + WEIGHT_NEGATIVE_SPACE * ns + WEIGHT_ANOMALY * an
    highest = max(eg, ns, an)
    soft_fl = highest * FLOOR_ATTENUATION
    expected_combined = max(w_sum, soft_fl)
    expected_score = round(expected_combined * 100, 1)

    print(f"Delta Rail Systems Verification:")
    print(f"  EG={eg:.3f}, NS={ns:.3f}, Anomaly={an:.3f}")
    print(f"  Weighted Sum: 0.40*{eg:.3f} + 0.35*{ns:.3f} + 0.25*{an:.3f} = {w_sum:.4f}")
    print(f"  Soft Floor  : max({eg:.3f}, {ns:.3f}, {an:.3f}) * 0.85 = {soft_fl:.4f}")
    print(f"  Expected Risk Score: max({w_sum:.4f}, {soft_fl:.4f}) * 100 = {expected_score}")
    print(f"  Actual Risk Score  : {delta_row['risk_score']}")
    assert delta_row["risk_score"] == expected_score, "Delta Rail arithmetic mismatch"
    print("  [PASS] Soft floor arithmetic verified successfully.")

    # 4. Boundary Tests
    print("\n==================================================")
    print("RISK BAND BOUNDARY TESTS")
    print("==================================================")
    boundary_tests = [
        (0.0, "low"),
        (19.9, "low"),
        (20.0, "medium"),
        (44.9, "medium"),
        (45.0, "high"),
        (69.9, "high"),
        (70.0, "critical"),
        (85.0, "critical"),
        (100.0, "critical"),
    ]

    for score_val, expected_band in boundary_tests:
        band = _risk_band(score_val)
        print(f"  Score: {score_val:5.1f} => Band: '{band}' (Expected: '{expected_band}')")
        assert band == expected_band, f"Boundary test failed for {score_val}"

    print("\n  [PASS] All 9 risk band boundary tests passed.")
    print("\nStep 1.4 Risk Score + Risk Band Integration complete successfully!")


def _print_risk_table(title: str, rows: list[dict]):
    print(f"\n--- {title} ---")
    header = f"{'Entity Name':30s} | {'EG':5s} | {'NS':5s} | {'AN':5s} | {'Risk Score':10s} | {'Risk Band':10s} | {'Primary Driver':15s}"
    print(header)
    print("-" * len(header))

    for r in rows:
        print(
            f"{r['entity_name']:30s} | "
            f"{r['execution_gap_score']:5.3f} | "
            f"{r['negative_space_score']:5.3f} | "
            f"{r['anomaly_score']:5.3f} | "
            f"{r['risk_score']:10.1f} | "
            f"{r['risk_band']:10s} | "
            f"{r['primary_driver']:15s}"
        )


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


def _write_risk_csv(out_path: Path, syn_rows: list, ext_rows: list):
    fieldnames = [
        "dataset_type",
        "entity_name",
        "execution_gap_score",
        "negative_space_score",
        "anomaly_score",
        "risk_score",
        "risk_band",
        "primary_driver",
        "flags",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()

        for r in syn_rows:
            writer.writerow({
                "dataset_type": "synthetic",
                "entity_name": r["entity_name"],
                "execution_gap_score": r["execution_gap_score"],
                "negative_space_score": r["negative_space_score"],
                "anomaly_score": r["anomaly_score"],
                "risk_score": r["risk_score"],
                "risk_band": r["risk_band"],
                "primary_driver": r["primary_driver"],
                "flags": "; ".join(r.get("flags", [])),
            })

        for r in ext_rows:
            writer.writerow({
                "dataset_type": "external",
                "entity_name": r["entity_name"],
                "execution_gap_score": r["execution_gap_score"],
                "negative_space_score": r["negative_space_score"],
                "anomaly_score": r["anomaly_score"],
                "risk_score": r["risk_score"],
                "risk_band": r["risk_band"],
                "primary_driver": r["primary_driver"],
                "flags": "; ".join(r.get("flags", [])),
            })


if __name__ == "__main__":
    run_step1_4()
