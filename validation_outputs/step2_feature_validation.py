"""
STEP 2: INDEPENDENT SIX-FEATURE VALIDATION — DISHA
Independently calculate 6 entity-level ML features from raw external CSV datasets
and validate against Kriza's existing feature output.

Read-only: no data is modified.
"""
import csv
import os
import statistics
from collections import defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "external")
KZA_FEATURES_PATH = os.path.join(os.path.dirname(__file__), "..", "backend",
                                  "validation_outputs", "independent_features.csv")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "disha_external_features.csv")

COMPANIES = [
    ("Equifax", "soc_alerts_equifax.csv"),
    ("JPMorgan Chase", "soc_alerts_jpmorgan_chase.csv"),
    ("MGM Resorts", "soc_alerts_mgm_resorts.csv"),
    ("Microsoft", "soc_alerts_microsoft.csv"),
    ("T-Mobile", "soc_alerts_t-mobile.csv"),
]

EXPECTED_COLUMNS = [
    "alert_id", "entity_name", "severity", "category", "asset_type",
    "created_time", "closed_time", "closure_duration_minutes",
    "escalated", "status", "investigation_notes"
]

TOLERANCE = 0.01  # numerical tolerance for floating-point comparison


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_timestamp(ts_str):
    """Parse timestamp string into datetime object."""
    if not ts_str or ts_str.strip() == "":
        return None
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_str.strip(), fmt)
        except ValueError:
            continue
    return None


def load_csv(filepath):
    """Load CSV file and return list of row dicts."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_kriza_features():
    """Load Kriza's existing feature output."""
    if not os.path.isfile(KZA_FEATURES_PATH):
        return {}
    with open(KZA_FEATURES_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        kriza = {}
        for row in reader:
            entity = row.get("entity_name", "").strip()
            kriza[entity] = {
                "alert_count": float(row.get("alert_count", 0)),
                "avg_closure_seconds": float(row.get("avg_closure_seconds", 0)),
                "escalation_rate": float(row.get("escalation_rate", 0)),
                "critical_ratio": float(row.get("critical_ratio", 0)),
                "avg_note_length": float(row.get("avg_note_length", 0)),
                "unique_asset_types": float(row.get("unique_asset_types", 0)),
            }
        return kriza


# ---------------------------------------------------------------------------
# Feature Calculation — Disha's Independent Implementation
# ---------------------------------------------------------------------------

def calculate_features(rows):
    """
    Independently calculate the 6 entity-level ML features from raw CSV rows.

    Returns dict with feature values and supporting counts.
    """
    result = {}

    # 1. alert_count
    alert_count = len(rows)
    result["alert_count"] = alert_count

    # 2. avg_closure_seconds
    # Use closure_duration_minutes when available, convert to seconds.
    # Exclude rows where closure information is unavailable.
    closure_seconds_list = []
    excluded_closure = 0
    for r in rows:
        dur_str = r.get("closure_duration_minutes", "").strip()
        if dur_str:
            try:
                dur_min = float(dur_str)
                closure_seconds_list.append(dur_min * 60.0)
            except (ValueError, TypeError):
                excluded_closure += 1
        else:
            excluded_closure += 1

    avg_closure_seconds = (
        statistics.mean(closure_seconds_list) if closure_seconds_list else 0.0
    )
    result["avg_closure_seconds"] = round(avg_closure_seconds, 2)
    result["_closed_alerts"] = len(closure_seconds_list)
    result["_excluded_closure"] = excluded_closure

    # 3. escalation_rate
    # escalated field is "Yes" or "No" in the CSV
    escalated_count = sum(
        1 for r in rows if r.get("escalated", "").strip().lower() in ("yes", "true", "1")
    )
    escalation_rate = escalated_count / alert_count if alert_count else 0.0
    result["escalation_rate"] = round(escalation_rate, 6)
    result["_escalated_alerts"] = escalated_count

    # 4. critical_ratio
    critical_count = sum(
        1 for r in rows if r.get("severity", "").strip().lower() == "critical"
    )
    critical_ratio = critical_count / alert_count if alert_count else 0.0
    result["critical_ratio"] = round(critical_ratio, 6)
    result["_critical_alerts"] = critical_count

    # 5. avg_note_length
    # Handle missing/blank investigation_notes as length 0
    note_lengths = []
    valid_notes = 0
    for r in rows:
        note = r.get("investigation_notes", "")
        if note and note.strip():
            note_lengths.append(len(note.strip()))
            valid_notes += 1
        else:
            note_lengths.append(0)
    avg_note_length = statistics.mean(note_lengths) if note_lengths else 0.0
    result["avg_note_length"] = round(avg_note_length, 2)
    result["_valid_notes"] = valid_notes
    result["_total_notes"] = len(note_lengths)

    # 6. unique_asset_types
    asset_types = set()
    for r in rows:
        at = r.get("asset_type", "").strip()
        if at:
            asset_types.add(at)
    result["unique_asset_types"] = len(asset_types)
    result["_asset_type_values"] = sorted(asset_types)

    return result


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_values(disha_val, kriza_val, feature_name, tolerance=TOLERANCE):
    """Compare Disha's value with Kriza's value."""
    if kriza_val is None:
        return "WARN", "Kriza value not available"

    diff = abs(disha_val - kriza_val)
    if diff <= tolerance:
        return "PASS", f"diff={diff:.6f}"
    else:
        return "FAIL", f"diff={diff:.6f}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 80)
    print("STEP 2 — INDEPENDENT SIX-FEATURE VALIDATION")
    print("=" * 80)

    # Load Kriza's existing features
    kriza_features = load_kriza_features()
    print(f"\nKriza's existing features loaded: {len(kriza_features)} entities")
    print(f"Kriza entities: {list(kriza_features.keys())}")

    all_results = {}
    all_comparisons = []

    for company_name, filename in COMPANIES:
        filepath = os.path.join(DATASET_DIR, filename)
        if not os.path.isfile(filepath):
            print(f"\nERROR: File not found: {filepath}")
            continue

        rows = load_csv(filepath)
        print(f"\n{'=' * 80}")
        print(f"Entity: {company_name}")
        print(f"Source: {filename} ({len(rows)} rows)")
        print(f"{'=' * 80}")

        # Calculate features independently
        features = calculate_features(rows)
        all_results[company_name] = features

        # Check if entity exists in Kriza's output
        kriza = kriza_features.get(company_name)

        # Feature definitions for display
        feature_defs = [
            ("alert_count", "Count of alerts per entity"),
            ("avg_closure_seconds", "Average closure duration in seconds "
             f"(closed_alerts={features['_closed_alerts']}, "
             f"excluded={features['_excluded_closure']})"),
            ("escalation_rate", f"Escalated={features['_escalated_alerts']}"
             f" / total={features['alert_count']}"),
            ("critical_ratio", f"Critical={features['_critical_alerts']}"
             f" / total={features['alert_count']}"),
            ("avg_note_length", f"Valid notes={features['_valid_notes']}"
             f" / total={features['_total_notes']}"
             " (missing/blank notes count as length 0)"),
            ("unique_asset_types", f"Distinct types={features['unique_asset_types']}"
             f" values={features['_asset_type_values']}"),
        ]

        for feat_name, definition in feature_defs:
            disha_val = features[feat_name]
            kriza_val = kriza[feat_name] if kriza else None

            if kriza is None:
                status = "WARN"
                diff_str = "N/A — entity not in Kriza's output"
            else:
                status, diff_str = compare_values(disha_val, kriza_val, feat_name)

            all_comparisons.append({
                "entity": company_name,
                "feature": feat_name,
                "disha_value": disha_val,
                "kriza_value": kriza_val,
                "status": status,
                "diff": diff_str,
            })

            print(f"\n  {feat_name}:")
            print(f"    Definition: {definition}")
            print(f"    Disha = {disha_val}")
            print(f"    Kriza = {kriza_val if kriza is not None else 'N/A (entity not in Kriza output)'}")
            print(f"    {diff_str}")
            print(f"    Status: {status}")

    # Save Disha's independent output
    print(f"\n{'=' * 80}")
    print("SAVING DISHA'S INDEPENDENT OUTPUT")
    print(f"{'=' * 80}")

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "entity_name", "alert_count", "avg_closure_seconds",
            "escalation_rate", "critical_ratio", "avg_note_length",
            "unique_asset_types", "total_alerts", "closed_alerts",
            "escalated_alerts", "critical_alerts", "valid_notes"
        ])
        for company_name in [c[0] for c in COMPANIES]:
            r = all_results[company_name]
            writer.writerow([
                company_name,
                r["alert_count"],
                r["avg_closure_seconds"],
                r["escalation_rate"],
                r["critical_ratio"],
                r["avg_note_length"],
                r["unique_asset_types"],
                r["alert_count"],
                r["_closed_alerts"],
                r["_escalated_alerts"],
                r["_critical_alerts"],
                r["_valid_notes"],
            ])

    print(f"Saved to: {OUTPUT_PATH}")

    # Summary
    print(f"\n{'=' * 80}")
    print("COMPARISON SUMMARY")
    print(f"{'=' * 80}")

    pass_count = sum(1 for c in all_comparisons if c["status"] == "PASS")
    warn_count = sum(1 for c in all_comparisons if c["status"] == "WARN")
    fail_count = sum(1 for c in all_comparisons if c["status"] == "FAIL")
    total = len(all_comparisons)

    print(f"\nTotal feature comparisons: {total}")
    print(f"PASS:  {pass_count}")
    print(f"WARN:  {warn_count}")
    print(f"FAIL:  {fail_count}")

    # Detailed comparison table
    print(f"\n{'Entity':<20} {'Feature':<25} {'Disha':<15} {'Kriza':<15} {'Status':<8}")
    print("-" * 85)
    for c in all_comparisons:
        kriza_str = f"{c['kriza_value']:.4f}" if c['kriza_value'] is not None else "N/A"
        disha_str = f"{c['disha_value']:.4f}" if isinstance(c['disha_value'], float) else str(c['disha_value'])
        print(f"{c['entity']:<20} {c['feature']:<25} {disha_str:<15} {kriza_str:<15} {c['status']:<8}")

    # Overall result
    if fail_count > 0:
        overall = "FAIL"
    elif warn_count > 0:
        overall = "PASS WITH WARNINGS"
    else:
        overall = "PASS"

    print(f"\n{'=' * 80}")
    print("OVERALL STEP 2 RESULT")
    print(f"{'=' * 80}")
    print(f"\n  {overall}")

    print(f"\n  Per-Entity Breakdown:")
    for company_name in [c[0] for c in COMPANIES]:
        entity_comps = [c for c in all_comparisons if c["entity"] == company_name]
        e_pass = sum(1 for c in entity_comps if c["status"] == "PASS")
        e_warn = sum(1 for c in entity_comps if c["status"] == "WARN")
        e_fail = sum(1 for c in entity_comps if c["status"] == "FAIL")
        if e_fail > 0:
            e_status = "FAIL"
        elif e_warn > 0:
            e_status = "PASS WITH WARNINGS"
        else:
            e_status = "PASS"
        print(f"    {company_name}: {e_status} (PASS={e_pass}, WARN={e_warn}, FAIL={e_fail})")

    print(f"\n  What Passed:")
    for c in all_comparisons:
        if c["status"] == "PASS":
            print(f"    {c['entity']} | {c['feature']} | Disha={c['disha_value']}, Kriza={c['kriza_value']}")

    print(f"\n  What Produced Warnings:")
    for c in all_comparisons:
        if c["status"] == "WARN":
            print(f"    {c['entity']} | {c['feature']} | {c['diff']}")

    print(f"\n  What Produced Failures:")
    for c in all_comparisons:
        if c["status"] == "FAIL":
            print(f"    {c['entity']} | {c['feature']} | Disha={c['disha_value']}, Kriza={c['kriza_value']} | {c['diff']}")

    print(f"\n  Independent output saved to: {OUTPUT_PATH}")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    main()
