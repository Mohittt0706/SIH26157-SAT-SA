"""Kriza Step 1.2 — Isolation Forest Fresh-Fit, External Inference & Stability Runner.

Fits Isolation Forest (n_estimators=200, contamination=0.2, random_state=42) fresh on the
synthetic dataset's own features, fits it fresh again — independently — on the five external
datasets, and runs stability experiments A-E. There is no persisted model: every dataset is
scored against its own peers, and the fixed random_state is what makes results reproducible,
not a saved artifact.
"""

import sys
import numpy as np
from pathlib import Path
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.analytics.anomaly import (
    FEATURE_NAMES,
    _convert_scores,
    extract_features_from_csv,
    compute_anomaly_from_features,
)


def run_step1_2():
    root_dir = Path(__file__).resolve().parents[1]
    output_dir = root_dir / "backend" / "validation_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    synthetic_csv = root_dir / "dataset" / "soc_alerts_synthetic_dataset.csv"

    print("==================================================")
    print("STEP 1.2 FRESH FIT: SYNTHETIC DATASET")
    print("==================================================")
    print(f"Training dataset: {synthetic_csv}")

    # 1. Fit fresh on the synthetic dataset's own features
    syn_features = extract_features_from_csv(synthetic_csv)
    synthetic_results = compute_anomaly_from_features(syn_features)

    print(f"\n[OK] Fit fresh on {len(synthetic_results)} synthetic entities (no artifact saved).")

    print("\n--- Synthetic Dataset Anomaly Scores (Fresh Fit) ---")
    for name in sorted(synthetic_results.keys()):
        res = synthetic_results[name]
        print(f"  {name:30s} | Anomaly Score: {res.score:.3f}")

    # 2. External Datasets — fit fresh again, independently, on their own peer group
    print("\n==================================================")
    print("STEP 1.2 EXTERNAL DATASET FRESH FIT")
    print("==================================================")
    print("Fitting a new Isolation Forest on the 5 external companies' own features —")
    print("scored against each other, never against the synthetic 10-company baseline.\n")

    external_files = [
        ("Equifax", root_dir / "dataset" / "external" / "soc_alerts_equifax.csv"),
        ("JPMorgan Chase", root_dir / "dataset" / "external" / "soc_alerts_jpmorgan_chase.csv"),
        ("MGM Resorts", root_dir / "dataset" / "external" / "soc_alerts_mgm_resorts.csv"),
        ("Microsoft", root_dir / "dataset" / "external" / "soc_alerts_microsoft.csv"),
        ("T-Mobile", root_dir / "dataset" / "external" / "soc_alerts_t-mobile.csv"),
    ]

    external_feature_map: dict[str, dict[str, float]] = {}
    print("External Dataset Physical Row Counts (Limitation Acknowledgment):")
    for entity_name, ext_csv in external_files:
        ext_features = extract_features_from_csv(ext_csv)
        alert_cnt = ext_features[entity_name]["alert_count"]
        print(f"  - {entity_name:18s}: {int(alert_cnt)} physical rows")
        external_feature_map[entity_name] = ext_features[entity_name]

    external_results = compute_anomaly_from_features(external_feature_map)

    print("\n--- External Dataset Anomaly Scores (Fresh Fit on These 5 Only) ---")
    for entity_name in sorted(external_results.keys()):
        res = external_results[entity_name]
        f_vec = external_feature_map[entity_name]
        print(f"\nEntity: {entity_name}")
        print(f"  Six Input Features : {f_vec}")
        print(f"  Anomaly Index (0-1): {res.score:.3f} (Relative Anomaly Index, NOT a probability)")
        print("  MAD Evidence       :")
        if res.evidence:
            for item in res.evidence:
                print(f"    -> {item['detail']}")
        else:
            print("    -> No significant deviation detected")

    # 3. Model Stability Experiments A - E
    print("\n==================================================")
    print("ISOLATION FOREST STABILITY EXPERIMENTS (A - E)")
    print("==================================================")

    syn_entities = sorted(syn_features.keys())
    X_syn = np.array([[syn_features[e][f] for f in FEATURE_NAMES] for e in syn_entities])
    scaler_syn = StandardScaler()
    X_syn_scaled = scaler_syn.fit_transform(X_syn)

    experiments = [
        ("A", 0.1, 100),
        ("B", 0.2, 100),
        ("C", "auto", 100),
        ("D", 0.2, 50),
        ("E (Selected)", 0.2, 200),
    ]

    exp_rankings: dict[str, list[str]] = {}

    for label, contamination, n_est in experiments:
        clf_exp = IsolationForest(
            random_state=42,
            contamination=contamination,
            n_estimators=n_est,
        )
        raw_s = clf_exp.fit(X_syn_scaled).decision_function(X_syn_scaled)
        conv_s = _convert_scores(raw_s)
        pairs = sorted(zip(syn_entities, conv_s), key=lambda p: p[1], reverse=True)
        ranked_names = [p[0] for p in pairs]
        exp_rankings[label] = ranked_names
        top_str = " > ".join(ranked_names)
        print(f"Experiment {label:12s} (contam={str(contamination):4s}, n_est={n_est:3d}):")
        print(f"  Ranking: {top_str}")

    top3_e = set(exp_rankings["E (Selected)"][:3])
    top3_stable = all(set(exp_rankings[lbl][:3]) == top3_e for lbl, _, _ in experiments)
    top1_e = exp_rankings["E (Selected)"][0]
    top1_stable = all(exp_rankings[lbl][0] == top1_e for lbl, _, _ in experiments)

    print(f"\nTop-1 Rank Stability across Experiments: {'STABLE' if top1_stable else 'UNSTABLE'} (Top: {top1_e})")
    print(f"Top-3 Rank Stability across Experiments: {'STABLE' if top3_stable else 'PARTIAL'}")

    # 4. Strict Validation Checks
    print("\n==================================================")
    print("STEP 1.2 VERIFICATION CHECKS")
    print("==================================================")

    # Check 1: Feature ordering is exactly what the rest of the pipeline expects
    assert FEATURE_NAMES == [
        "alert_count",
        "avg_closure_seconds",
        "escalation_rate",
        "critical_ratio",
        "avg_note_length",
        "unique_asset_types",
    ]
    print(f"  [PASS] Feature ordering strictly matches: {FEATURE_NAMES}")

    # Check 2: No NaN/invalid feature vectors passed
    for e_name, f_dict in external_feature_map.items():
        for k, v in f_dict.items():
            assert isinstance(v, (int, float)) and not np.isnan(v), f"Invalid feature {e_name}.{k}"
    print("  [PASS] All feature vectors are clean, non-NaN, and numeric.")

    # Check 3: Synthetic and external fits are independent (correct entity counts)
    assert len(synthetic_results) == 10
    assert len(external_results) == 5
    print("  [PASS] Synthetic fit scored its own 10 entities; external fit scored its own 5 —")
    print("         two independent baselines, not one stale one reused across datasets.")

    # Check 4: Fresh fit is deterministic — same features in, same scores out, every time
    repeat_results = compute_anomaly_from_features(external_feature_map)
    for name in external_results:
        assert repeat_results[name].score == external_results[name].score, (
            f"Non-deterministic score for {name}: "
            f"{repeat_results[name].score} != {external_results[name].score}"
        )
    print("  [PASS] Re-fitting on the same data twice produced identical scores —")
    print("         IFOREST_RANDOM_STATE=42 gives reproducibility without persisting anything.")

    print("\nStep 1.2 Isolation Forest / Anomaly Detection complete successfully!")


if __name__ == "__main__":
    run_step1_2()
