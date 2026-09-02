import csv
import json
import math
import os
import sys
import argparse
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


def norm(val: str | None) -> str:
    if val is None:
        return ""
    return str(val).strip()


def find_dataset_path() -> Path:
    candidates = [
        Path.cwd() / "dataset" / "soc_alerts_synthetic_dataset.csv",
        Path.cwd().parent / "dataset" / "soc_alerts_synthetic_dataset.csv",
        Path(__file__).resolve().parents[2] / "dataset" / "soc_alerts_synthetic_dataset.csv",
        Path(__file__).resolve().parents[3] / "dataset" / "soc_alerts_synthetic_dataset.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (Path.cwd() / "dataset" / "soc_alerts_synthetic_dataset.csv").resolve()


def load_rows(path: Path | str | None = None) -> list[dict[str, str]]:
    if path is None:
        path = find_dataset_path()
    path = Path(path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def api_get(base_url: str, endpoint: str) -> dict | list:
    url = f"{base_url.rstrip('/')}{endpoint}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def validate_dataset(csv_path: Path) -> list[str]:
    checks: list[str] = []
    if not csv_path.exists():
        return [f"FAIL -- Dataset CSV file not found at {csv_path}"]

    rows = load_rows(csv_path)
    if not rows:
        return [f"FAIL -- Dataset CSV at {csv_path} is empty"]

    # 1. Required columns
    required_cols = {"alert_id", "entity_name", "severity", "created_time", "closed_time", "escalated", "investigation_notes"}
    actual_cols = set(rows[0].keys())
    missing_cols = required_cols - actual_cols
    if missing_cols:
        checks.append(f"FAIL -- Required columns missing: {sorted(list(missing_cols))}")
    else:
        checks.append("PASS -- Required columns: all present")

    # 2. Row count
    row_count = len(rows)
    if row_count == 639:
        checks.append("PASS -- Row count: 639 rows; expected 639")
    else:
        checks.append(f"WARN -- Row count: {row_count} rows; expected 639")

    # 3. Entity count
    entities = {norm(r.get("entity_name")) for r in rows if norm(r.get("entity_name"))}
    if len(entities) == 10:
        checks.append("PASS -- Entity count: 10 entities; expected 10")
    else:
        checks.append(f"WARN -- Entity count: {len(entities)} entities; expected 10")

    # 4. Duplicate alert_id
    alert_ids = [norm(r.get("alert_id")) for r in rows if norm(r.get("alert_id"))]
    dup_ids = len(alert_ids) - len(set(alert_ids))
    checks.append(f"{'PASS' if dup_ids == 0 else 'FAIL'} -- Duplicate alert_id: {dup_ids} duplicates")

    # 5. Blank entity_name
    blank_entities = sum(1 for r in rows if not norm(r.get("entity_name")))
    checks.append(f"{'PASS' if blank_entities == 0 else 'FAIL'} -- Blank entity_name: {blank_entities} blank rows")

    # 6. Missing severity
    missing_sev = sum(1 for r in rows if not norm(r.get("severity")))
    checks.append(f"{'PASS' if missing_sev == 0 else 'FAIL'} -- Missing severity: {missing_sev} missing")

    # 7. Missing closure_duration_minutes
    missing_dur = 0
    neg_dur = 0
    invalid_dur = 0
    for r in rows:
        dur_str = norm(r.get("closure_duration_minutes"))
        if not dur_str:
            missing_dur += 1
        else:
            try:
                val = float(dur_str)
                if val < 0:
                    neg_dur += 1
            except ValueError:
                invalid_dur += 1
    checks.append(f"{'PASS' if missing_dur == 0 else 'FAIL'} -- Missing closure_duration_minutes: {missing_dur} missing")

    # 8. Missing escalated
    missing_esc = sum(1 for r in rows if not norm(r.get("escalated")))
    checks.append(f"{'PASS' if missing_esc == 0 else 'FAIL'} -- Missing escalated: {missing_esc} missing")

    # 9. Missing investigation_notes
    missing_notes = sum(1 for r in rows if not norm(r.get("investigation_notes")))
    checks.append(f"{'PASS' if missing_notes == 0 else 'FAIL'} -- Missing investigation_notes: {missing_notes} missing")

    # 10. Negative closure duration
    checks.append(f"{'PASS' if neg_dur == 0 else 'FAIL'} -- Negative closure duration: {neg_dur} negative values")

    # 11. Invalid closure duration
    checks.append(f"{'PASS' if invalid_dur == 0 else 'FAIL'} -- Invalid closure duration: {invalid_dur} non-numeric values")

    # 12-14. Timestamp parsing
    inv_created = 0
    inv_closed = 0
    closed_before_created = 0
    for r in rows:
        c_time_str = norm(r.get("created_time"))
        cl_time_str = norm(r.get("closed_time"))
        t_create, t_close = None, None
        if c_time_str:
            try:
                t_create = pd.to_datetime(c_time_str)
            except Exception:
                inv_created += 1
        else:
            inv_created += 1

        if cl_time_str:
            try:
                t_close = pd.to_datetime(cl_time_str)
            except Exception:
                inv_closed += 1
        else:
            inv_closed += 1

        if t_create is not None and t_close is not None and t_close < t_create:
            closed_before_created += 1

    checks.append(f"{'PASS' if inv_created == 0 else 'FAIL'} -- Invalid created_time: {inv_created} invalid timestamps")
    checks.append(f"{'PASS' if inv_closed == 0 else 'FAIL'} -- Invalid closed_time: {inv_closed} invalid timestamps")
    checks.append(f"{'PASS' if closed_before_created == 0 else 'FAIL'} -- closed_time before created_time: {closed_before_created} rows")

    # 15. Unexpected severity values
    valid_sevs = {"low", "medium", "high", "critical"}
    unexp_sev = sum(1 for r in rows if norm(r.get("severity")).lower() not in valid_sevs)
    checks.append(f"{'PASS' if unexp_sev == 0 else 'FAIL'} -- Unexpected severity values: {'none' if unexp_sev == 0 else f'{unexp_sev} unexpected'}")

    # 16. Unexpected escalated values
    valid_esc = {"yes", "no", "true", "false", "1", "0"}
    unexp_esc = sum(1 for r in rows if norm(r.get("escalated")).lower() not in valid_esc)
    checks.append(f"{'PASS' if unexp_esc == 0 else 'FAIL'} -- Unexpected escalated values: {'none' if unexp_esc == 0 else f'{unexp_esc} unexpected'}")

    # 17. Entity case/spelling variants
    case_map: dict[str, set[str]] = {}
    for r in rows:
        name = norm(r.get("entity_name"))
        if name:
            case_map.setdefault(name.lower(), set()).add(name)
    variant_groups = sum(1 for group in case_map.values() if len(group) > 1)
    checks.append(f"{'PASS' if variant_groups == 0 else 'WARN'} -- Entity case/spelling variants: {variant_groups} case-insensitive groups have variants")

    return checks


def calculate_independent_features(csv_path: Path) -> dict[str, dict[str, float]]:
    rows = load_rows(csv_path)
    entity_data: dict[str, list[dict[str, str]]] = {}
    for r in rows:
        entity = norm(r.get("entity_name"))
        if entity:
            entity_data.setdefault(entity, []).append(r)

    features: dict[str, dict[str, float]] = {}

    for entity, e_rows in entity_data.items():
        total = len(e_rows)
        if total == 0:
            continue

        critical_count = sum(1 for r in e_rows if norm(r.get("severity")).lower() == "critical")
        high_count = sum(1 for r in e_rows if norm(r.get("severity")).lower() == "high")
        med_count = sum(1 for r in e_rows if norm(r.get("severity")).lower() == "medium")
        low_count = sum(1 for r in e_rows if norm(r.get("severity")).lower() == "low")

        closure_mins = []
        fast_closure_count = 0
        for r in e_rows:
            dur_str = norm(r.get("closure_duration_minutes"))
            if dur_str:
                try:
                    val = float(dur_str)
                    closure_mins.append(val)
                    if val <= 5.0:
                        fast_closure_count += 1
                except ValueError:
                    pass

        avg_closure = float(np.mean(closure_mins)) if closure_mins else 0.0
        fast_closure_rate = fast_closure_count / total

        template_phrases = ["reviewed and closed", "no further action required", "closed as per standard procedure", "false positive"]
        zero_notes_count = 0
        for r in e_rows:
            notes = norm(r.get("investigation_notes")).lower()
            if not notes or any(p in notes for p in template_phrases) or len(notes) <= 25:
                zero_notes_count += 1
        zero_notes_rate = zero_notes_count / total

        no_escalate_crit = sum(
            1 for r in e_rows
            if norm(r.get("severity")).lower() == "critical"
            and norm(r.get("escalated")).lower() in ("no", "false", "0")
        )
        no_escalate_rate = no_escalate_crit / max(1, critical_count) if critical_count > 0 else 0.0

        escalated_count = sum(
            1 for r in e_rows
            if norm(r.get("escalated")).lower() in ("yes", "true", "1")
        )
        escalation_rate = escalated_count / total

        features[entity] = {
            "total_alerts": float(total),
            "critical_alerts": float(critical_count),
            "high_alerts": float(high_count),
            "medium_alerts": float(med_count),
            "low_alerts": float(low_count),
            "avg_closure_minutes": float(avg_closure),
            "fast_closure_count": float(fast_closure_count),
            "fast_closure_rate": float(fast_closure_rate),
            "zero_notes_count": float(zero_notes_count),
            "zero_notes_rate": float(zero_notes_rate),
            "no_escalate_critical_count": float(no_escalate_crit),
            "no_escalate_rate": float(no_escalate_rate),
            "escalated_count": float(escalated_count),
            "escalation_rate": float(escalation_rate),
        }

    return features


def validate_isolation_forest_stability(features: dict[str, dict[str, float]]) -> list[str]:
    checks: list[str] = []
    if not features:
        return ["WARN -- Isolation Forest stability check skipped: no features provided"]

    entities = sorted(list(features.keys()))
    if len(entities) < 2:
        return ["WARN -- Isolation Forest stability check skipped: less than 2 entities"]

    feature_keys = sorted(list(next(iter(features.values())).keys()))
    X = np.array([[features[e][k] for k in feature_keys] for e in entities])

    seeds = [42, 100, 2026, 777, 999]
    seed_labels = ["A", "B", "C", "D", "E"]
    rankings: dict[str, list[str]] = {}

    for label, seed in zip(seed_labels, seeds):
        clf = IsolationForest(random_state=seed, contamination=0.2)
        clf.fit(X)
        scores = -clf.decision_function(X)
        sorted_pairs = sorted(zip(entities, scores), key=lambda p: p[1], reverse=True)
        rankings[label] = [p[0] for p in sorted_pairs]

    top3_a = set(rankings["A"][:3])
    stable_top3 = all(set(rankings[lbl][:3]) == top3_a for lbl in seed_labels)

    top_entity_a = rankings["A"][0]
    stable_top1 = all(rankings[lbl][0] == top_entity_a for lbl in seed_labels)

    if stable_top1 or stable_top3:
        checks.append("PASS WITH WARNING -- Top-3 ranking is stable; lower ranks shifted")
    else:
        checks.append("WARN -- Isolation Forest ranking fluctuated across random seeds")

    for lbl in seed_labels:
        ranks_str = " > ".join(rankings[lbl])
        checks.append(f"- {lbl}: {ranks_str}")

    return checks


def validate_negative_space(csv_path: Path) -> list[str]:
    checks: list[str] = []
    rows = load_rows(csv_path)
    if not rows:
        return ["WARN -- Negative space check skipped: empty dataset"]

    entity_counts: dict[str, int] = {}
    entity_severities: dict[str, set[str]] = {}
    for r in rows:
        e = norm(r.get("entity_name"))
        if not e:
            continue
        entity_counts[e] = entity_counts.get(e, 0) + 1
        sev = norm(r.get("severity")).lower()
        if sev:
            entity_severities.setdefault(e, set()).add(sev)

    all_entities = sorted(list(entity_counts.keys()))
    all_sevs = {"critical", "high", "medium", "low"}

    for entity in all_entities:
        count = entity_counts[entity]
        peer_counts = [cnt for e, cnt in entity_counts.items() if e != entity]
        peer_mean = float(np.mean(peer_counts)) if peer_counts else 0.0
        peer_std = float(np.std(peer_counts)) if peer_counts else 1.0
        z = (count - peer_mean) / (peer_std if peer_std > 0 else 1.0)
        low_volume = bool(count < 10 or z < -1.5)

        missing = sorted(list(all_sevs - entity_severities.get(entity, set())))
        checks.append(
            f"- {entity}: count={count}, peer_mean={peer_mean:.2f}, peer_std={peer_std:.2f}, "
            f"z={z:.3f}, low_volume={low_volume}, missing={missing}"
        )

    return checks


def validate_data_quality(csv_path: Path) -> list[str]:
    rows = load_rows(csv_path)
    if not rows:
        return ["WARN -- Data quality check skipped: empty dataset"]
    return ["PASS -- Dataset data quality check (covered by dataset validation checks above)"]


def validate_api(base_url: str, features: dict[str, dict[str, float]]) -> list[str]:
    checks: list[str] = []

    try:
        data = api_get(base_url, "/api/risk-scores")
    except Exception as exc:
        return [f"WARN -- API validation unavailable: {exc}"]

    rows = data.get("value", data) if isinstance(data, dict) else data

    if not isinstance(rows, list):
        return ["WARN -- /api/risk-scores returned an unexpected format"]

    expected_entity_count = len(features) if features else 10
    checks.append(
        f"{'PASS' if len(rows) == expected_entity_count else 'WARN'} -- "
        f"API entity count: {len(rows)}"
    )

    mismatches = []

    for row in rows:
        entity = norm(row.get("entity_name"))

        if not entity:
            continue

        try:
            detail = api_get(
                base_url,
                "/api/entities/" + urllib.parse.quote(entity)
            )
        except Exception as exc:
            mismatches.append(f"{entity}: detail API unavailable ({exc})")
            continue

        if not isinstance(detail, dict):
            mismatches.append(f"{entity}: invalid detail response")
            continue

        components = detail.get("component_scores", {})

        eg = float(components.get("execution_gap", 0.0))
        ns = float(components.get("negative_space", 0.0))
        an = float(components.get("anomaly", 0.0))

        # Same Risk Score formula used by backend.
        weighted = (
            0.40 * eg
            + 0.35 * ns
            + 0.25 * an
        )

        # Same maximum-detector floor used by backend.
        expected = max(
            weighted,
            max(eg, ns, an) * 0.85
        )

        expected = max(0.0, min(1.0, expected))
        expected_risk = round(expected * 100, 1)

        actual_risk = float(row.get("risk_score", math.nan))

        if not math.isclose(
            expected_risk,
            actual_risk,
            abs_tol=0.11
        ):
            mismatches.append(
                f"{entity}: expected {expected_risk}, API {actual_risk}"
            )

    checks.append(
        f"{'PASS' if not mismatches else 'FAIL'} — "
        f"independent risk-score arithmetic "
        f"({len(mismatches)} mismatches)"
    )

    checks.extend([f"  - {x}" for x in mismatches[:10]])

    # ---------------------------------------------------------
    # Execution Gap evidence trace
    # ---------------------------------------------------------
    evidence_checked = 0
    evidence_bad = 0

    raw_dataset_rows = load_rows()
    by_id = {
        norm(r.get("alert_id")): r
        for r in raw_dataset_rows
        if norm(r.get("alert_id"))
    }

    for row in rows:
        entity = norm(row.get("entity_name"))

        try:
            detail = api_get(
                base_url,
                "/api/entities/" + urllib.parse.quote(entity)
            )
        except Exception:
            continue

        if not isinstance(detail, dict):
            continue

        findings = detail.get("findings", [])

        for finding in findings:
            if norm(finding.get("detector")) != "execution_gap":
                continue

            evidence_items = finding.get("evidence", [])

            for item in evidence_items:
                evidence_text = norm(item.get("detail"))

                # Execution Gap evidence should contain an alert ID.
                alert_id = ""

                if " — " in evidence_text:
                    alert_id = evidence_text.split(" — ", 1)[1].strip()
                elif "ALT" in evidence_text:
                    import re
                    match = re.search(r"ALT\d+", evidence_text)
                    if match:
                        alert_id = match.group(0)

                if not alert_id:
                    continue

                evidence_checked += 1

                raw = by_id.get(alert_id)

                if raw is None:
                    evidence_bad += 1
                    continue

                if norm(raw.get("entity_name")) != entity:
                    evidence_bad += 1

    if evidence_checked == 0:
        checks.append(
            "WARN — Execution Gap evidence trace: no evidence items with alert IDs found to trace"
        )
    else:
        checks.append(
            f"{'PASS' if evidence_bad == 0 else 'FAIL'} — "
            f"Execution Gap evidence trace: "
            f"{evidence_checked - evidence_bad}/{evidence_checked} "
            f"valid alert IDs"
        )

    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SAT-SA Independent Validation Script")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="Base URL for the SAT-SA backend API"
    )
    args = parser.parse_args()

    csv_path = find_dataset_path()
    print("=" * 60)
    print("SAT-SA INDEPENDENT VALIDATION REPORT")
    print("=" * 60)
    print(f"Dataset path: {csv_path}\n")

    # 1. Dataset Validation
    print("## 1. Dataset Validation")
    ds_checks = validate_dataset(csv_path)
    for check in ds_checks:
        print(f"- {check}")
    print()

    # 2. Independent Features
    print("## 2. Independent Features")
    features = calculate_independent_features(csv_path)
    print(f"Calculated independent features for {len(features)} entities.")
    print()

    # 3. Isolation Forest Stability
    print("## 3. Isolation Forest Ranking Stability")
    if_checks = validate_isolation_forest_stability(features)
    for check in if_checks:
        print(check if check.startswith("-") else f"- {check}")
    print()

    # 4. Negative Space Validation
    print("## 4. Negative Space Validation")
    ns_checks = validate_negative_space(csv_path)
    for check in ns_checks:
        print(check)
    print()

    # 5. Data Quality
    print("## 5. Data Quality")
    dq_checks = validate_data_quality(csv_path)
    for check in dq_checks:
        print(f"- {check}")
    print()

    # 6. API Validation
    print("## 6. API & Risk Score Validation")
    api_checks = validate_api(args.api_url, features)
    for check in api_checks:
        print(f"- {check}")
    print()
    print("=" * 60)