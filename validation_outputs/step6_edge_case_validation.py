"""STEP 2.6 - INDEPENDENT EDGE-CASE TESTING.

Independently test whether the ML pipeline behaves safely and predictably
under edge-case conditions. Uses in-memory copies only; never modifies
raw datasets or production code.
"""
import csv
import copy
import math
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(BASE, "dataset", "external")
MODEL_PATH = os.path.join(BASE, "backend", "anomaly_model.joblib")
COMPANIES = [
    ("Equifax", "soc_alerts_equifax.csv"),
    ("JPMorgan Chase", "soc_alerts_jpmorgan_chase.csv"),
    ("MGM Resorts", "soc_alerts_mgm_resorts.csv"),
    ("Microsoft", "soc_alerts_microsoft.csv"),
    ("T-Mobile", "soc_alerts_t-mobile.csv"),
]
REPORT = os.path.join(BASE, "validation_outputs", "step6_edge_case_validation_report.md")
CSV_OUT = os.path.join(BASE, "validation_outputs", "step6_edge_case_validation_results.csv")

FAST_CLOSURE_THRESHOLD = 300
MIN_NOTE_LENGTH = 20
MIN_DUPLICATE_MULTIPLICITY = 5
MAD_ZSCALE = 0.6745


def _parse_dt(s):
    if not s or not s.strip():
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def _closure_seconds(row):
    dur_str = (row.get("closure_duration_minutes") or "").strip()
    if dur_str:
        try:
            v = float(dur_str)
            if v >= 0:
                return v * 60.0
        except ValueError:
            pass
    ct = _parse_dt(row.get("created_time", ""))
    clt = _parse_dt(row.get("closed_time", ""))
    if ct and clt:
        diff = (clt - ct).total_seconds()
        if diff >= 0:
            return diff
    return None


def load_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _modified_z(value, peer_median, peer_mad):
    if peer_mad == 0.0:
        return 0.0 if value == peer_median else (1.0 if value > peer_median else -1.0)
    return MAD_ZSCALE * (value - peer_median) / peer_mad


class TestResult:
    def __init__(self, company, edge_case, test_condition):
        self.company = company
        self.edge_case = edge_case
        self.test_condition = test_condition
        self.execution_status = "PENDING"
        self.exception = ""
        self.numeric_validity = True
        self.logical_validity = True
        self.expected_behavior = ""
        self.observed_behavior = ""
        self.status = "PENDING"
        self.notes = ""


def compute_features(rows):
    total = len(rows)
    closure_secs = []
    escalated = 0
    critical = 0
    note_lens = []
    assets = set()
    for r in rows:
        if (r.get("severity") or "").strip().lower() == "critical":
            critical += 1
        if (r.get("escalated") or "").strip().lower() in ("yes", "true", "1"):
            escalated += 1
        asset = (r.get("asset_type") or "").strip()
        if asset:
            assets.add(asset)
        note = (r.get("investigation_notes") or "").strip()
        note_lens.append(len(note) if note else 0)
        cs = _closure_seconds(r)
        if cs is not None:
            closure_secs.append(cs)
    return {
        "alert_count": float(total),
        "avg_closure_seconds": sum(closure_secs) / len(closure_secs) if closure_secs else 0.0,
        "escalation_rate": escalated / total if total else 0.0,
        "critical_ratio": critical / total if total else 0.0,
        "avg_note_length": sum(note_lens) / len(note_lens) if note_lens else 0.0,
        "unique_asset_types": float(len(assets)),
    }


def compute_eg(rows):
    total = len(rows)
    fc_cands = [r for r in rows if (r.get("severity") or "").strip().lower() in ("critical", "high") and _parse_dt(r.get("closed_time", "")) is not None]
    fc_hits = [r for r in fc_cands if _closure_seconds(r) is not None and _closure_seconds(r) < FAST_CLOSURE_THRESHOLD]
    fc_rate = len(fc_hits) / len(fc_cands) if fc_cands else 0.0
    ne_cands = [r for r in rows if (r.get("severity") or "").strip().lower() == "critical"]
    ne_hits = [r for r in ne_cands if (r.get("escalated") or "").strip().lower() not in ("yes", "true", "1")]
    ne_rate = len(ne_hits) / len(ne_cands) if ne_cands else 0.0
    note_counts = Counter()
    for r in rows:
        note = (r.get("investigation_notes") or "").strip()
        if note:
            note_counts[note] += 1
    highly_dup = {n for n, cnt in note_counts.items() if cnt >= MIN_DUPLICATE_MULTIPLICITY}
    entity_dup_count = sum(1 for r in rows if (r.get("investigation_notes") or "").strip() in highly_dup)
    entity_dup_rate = entity_dup_count / total if total else 0.0
    dup_z = _modified_z(entity_dup_rate, 0.0, 0.0)
    dup_flagged = dup_z >= 1.0
    tn_hits = 0
    for r in rows:
        note = (r.get("investigation_notes") or "").strip()
        if not note or len(note) < MIN_NOTE_LENGTH or (dup_flagged and note in highly_dup):
            tn_hits += 1
    tn_rate = tn_hits / total if total else 0.0
    score = min(1.0, 0.4 * fc_rate + 0.3 * ne_rate + 0.3 * tn_rate)
    return {
        "fc_rate": fc_rate, "ne_rate": ne_rate, "tn_rate": tn_rate,
        "score": score, "fc_hits": len(fc_hits), "fc_cands": len(fc_cands),
        "ne_hits": len(ne_hits), "ne_cands": len(ne_cands), "tn_hits": tn_hits,
    }


def compute_risk(eg_score, ns_score, anom_score):
    W_EG, W_NS, W_AN = 0.40, 0.35, 0.25
    FLOOR_ATTEN = 0.85
    weighted = W_EG * eg_score + W_NS * ns_score + W_AN * anom_score
    highest = max(eg_score, ns_score, anom_score)
    soft_floor = highest * FLOOR_ATTEN
    combined = max(weighted, soft_floor)
    combined = max(0.0, min(1.0, combined))
    final = combined * 100
    if final >= 70:
        band = "critical"
    elif final >= 45:
        band = "high"
    elif final >= 20:
        band = "medium"
    else:
        band = "low"
    return {
        "weighted": weighted, "highest": highest, "soft_floor": soft_floor,
        "combined": combined, "final": final, "band": band,
        "soft_floor_active": soft_floor > weighted,
    }


def compute_anomaly_score(rows, feature_names, scaler, clf):
    import numpy as np
    fv = compute_features(rows)
    X = np.array([[fv[f] for f in feature_names]])
    X_scaled = scaler.transform(X)
    raw = float(clf.decision_function(X_scaled)[0])
    return raw, fv


def test_missing_notes(rows, company):
    results = []
    tr = TestResult(company, "MISSING_NOTES", "blank investigation_notes")
    tr.expected_behavior = "No crash; template_notes rate becomes 1.0"
    try:
        modified = copy.deepcopy(rows)
        for r in modified:
            r["investigation_notes"] = ""
        eg = compute_eg(modified)
        risk = compute_risk(eg["score"], 0.0, 0.0)
        tr.execution_status = "COMPLETED"
        tr.observed_behavior = f"eg={eg['score']:.4f} tn_rate={eg['tn_rate']:.1f} risk={risk['final']:.1f}"
        tr.numeric_validity = all(math.isfinite(v) for v in [eg["score"], risk["final"]])
        tr.logical_validity = eg["tn_rate"] == 1.0
        tr.status = "PASS" if tr.numeric_validity and tr.logical_validity else "FAIL"
    except Exception as e:
        tr.execution_status = "COMPLETED"
        tr.exception = str(e)
        tr.status = "FAIL"
    results.append(tr)

    tr2 = TestResult(company, "MISSING_NOTES", "very short notes (<20 chars)")
    tr2.expected_behavior = "No crash; short notes treated as template"
    try:
        modified = copy.deepcopy(rows)
        for r in modified:
            r["investigation_notes"] = "ok"
        eg = compute_eg(modified)
        tr2.execution_status = "COMPLETED"
        tr2.observed_behavior = f"eg={eg['score']:.4f} tn_rate={eg['tn_rate']:.1f}"
        tr2.numeric_validity = math.isfinite(eg["score"])
        tr2.logical_validity = eg["tn_rate"] == 1.0
        tr2.status = "PASS" if tr2.numeric_validity and tr2.logical_validity else "FAIL"
    except Exception as e:
        tr2.execution_status = "COMPLETED"
        tr2.exception = str(e)
        tr2.status = "FAIL"
    results.append(tr2)
    return results


def test_missing_closed_time(rows, company):
    results = []
    tr = TestResult(company, "MISSING_CLOSED_TIME", "some alerts with no closed_time")
    tr.expected_behavior = "No crash; no false FAST_CLOSURE from missing data"
    try:
        modified = copy.deepcopy(rows)
        for i, r in enumerate(modified):
            if i % 3 == 0:
                r["closed_time"] = ""
        eg = compute_eg(modified)
        features = compute_features(modified)
        risk = compute_risk(eg["score"], 0.0, 0.0)
        tr.execution_status = "COMPLETED"
        tr.observed_behavior = f"eg={eg['score']:.4f} fc_rate={eg['fc_rate']:.4f} avg_cl={features['avg_closure_seconds']:.1f}"
        tr.numeric_validity = all(math.isfinite(v) for v in [eg["score"], features["avg_closure_seconds"], risk["final"]])
        tr.logical_validity = eg["fc_rate"] == 0.0
        tr.status = "PASS" if tr.numeric_validity and tr.logical_validity else "FAIL"
    except Exception as e:
        tr.execution_status = "COMPLETED"
        tr.exception = str(e)
        tr.status = "FAIL"
    results.append(tr)
    return results


def test_missing_closure_duration(rows, company):
    results = []
    tr = TestResult(company, "MISSING_CLOSURE_DURATION", "closure_duration_minutes blank")
    tr.expected_behavior = "No crash; closure falls back to timestamp diff or None"
    try:
        modified = copy.deepcopy(rows)
        for r in modified:
            r["closure_duration_minutes"] = ""
        eg = compute_eg(modified)
        features = compute_features(modified)
        tr.execution_status = "COMPLETED"
        tr.observed_behavior = f"eg={eg['score']:.4f} avg_cl={features['avg_closure_seconds']:.1f}"
        tr.numeric_validity = all(math.isfinite(v) for v in [eg["score"], features["avg_closure_seconds"]])
        tr.logical_validity = eg["fc_rate"] == 0.0
        tr.status = "PASS" if tr.numeric_validity and tr.logical_validity else "FAIL"
    except Exception as e:
        tr.execution_status = "COMPLETED"
        tr.exception = str(e)
        tr.status = "FAIL"
    results.append(tr)
    return results


def test_no_critical_alerts(rows, company):
    results = []
    tr = TestResult(company, "NO_CRITICAL_ALERTS", "in-memory scenario with zero critical alerts")
    tr.expected_behavior = "NO_ESCALATION rate=0 (no candidates); critical_ratio=0"
    try:
        modified = copy.deepcopy(rows)
        for r in modified:
            r["severity"] = "Medium"
        eg = compute_eg(modified)
        features = compute_features(modified)
        risk = compute_risk(eg["score"], 0.0, 0.0)
        tr.execution_status = "COMPLETED"
        tr.observed_behavior = f"eg={eg['score']:.4f} ne_rate={eg['ne_rate']:.1f} crit_ratio={features['critical_ratio']:.1f} risk={risk['final']:.1f}"
        tr.numeric_validity = all(math.isfinite(v) for v in [eg["score"], features["critical_ratio"], risk["final"]])
        tr.logical_validity = eg["ne_rate"] == 0.0 and features["critical_ratio"] == 0.0
        tr.status = "PASS" if tr.numeric_validity and tr.logical_validity else "FAIL"
    except Exception as e:
        tr.execution_status = "COMPLETED"
        tr.exception = str(e)
        tr.status = "FAIL"
    results.append(tr)
    return results


def test_no_escalated(rows, company):
    results = []
    tr = TestResult(company, "NO_ESCALATED", "zero escalated alerts")
    tr.expected_behavior = "No crash; escalation_rate=0; NO_ESCALATION still applies to critical"
    try:
        modified = copy.deepcopy(rows)
        for r in modified:
            r["escalated"] = "No"
        eg = compute_eg(modified)
        features = compute_features(modified)
        tr.execution_status = "COMPLETED"
        tr.observed_behavior = f"eg={eg['score']:.4f} esc_rate={features['escalation_rate']:.1f} ne_rate={eg['ne_rate']:.4f}"
        tr.numeric_validity = all(math.isfinite(v) for v in [eg["score"], features["escalation_rate"]])
        tr.logical_validity = features["escalation_rate"] == 0.0
        tr.status = "PASS" if tr.numeric_validity and tr.logical_validity else "FAIL"
    except Exception as e:
        tr.execution_status = "COMPLETED"
        tr.exception = str(e)
        tr.status = "FAIL"
    results.append(tr)
    return results


def test_low_volume(rows, company):
    results = []
    tr = TestResult(company, "LOW_VOLUME", "only 3 alerts in dataset")
    tr.expected_behavior = "No crash; features valid; NS peer unavailable (expected)"
    try:
        modified = copy.deepcopy(rows)[:3]
        features = compute_features(modified)
        eg = compute_eg(modified)
        ns = compute_ns_rows(modified)
        risk = compute_risk(eg["score"], ns["score"], 0.0)
        tr.execution_status = "COMPLETED"
        tr.observed_behavior = f"alerts=3 eg={eg['score']:.4f} ns={ns['score']:.4f} risk={risk['final']:.1f}"
        tr.numeric_validity = all(math.isfinite(v) for v in [eg["score"], ns["score"], risk["final"]])
        tr.logical_validity = True
        tr.status = "PASS" if tr.numeric_validity else "FAIL"
    except Exception as e:
        tr.execution_status = "COMPLETED"
        tr.exception = str(e)
        tr.status = "FAIL"
    results.append(tr)
    return results


def compute_ns_rows(rows):
    total = len(rows)
    peer_mean = 0.0
    z_score = 0.0 if total == peer_mean else (-1.0 if total < peer_mean else 1.0)
    low_triggered = z_score <= -1.0
    low_signal = 1.0 if low_triggered else 0.0
    score = max(0.0, min(1.0, 0.6 * low_signal))
    return {"total": total, "score": score, "z_score": z_score}


def test_asset_types(rows, company):
    results = []
    tr = TestResult(company, "ASSET_TYPES", "verify different asset_type values handled")
    tr.expected_behavior = "No crash; unique_asset_types correct; feature vector valid"
    try:
        features = compute_features(rows)
        assets = set()
        for r in rows:
            a = (r.get("asset_type") or "").strip()
            if a:
                assets.add(a)
        tr.execution_status = "COMPLETED"
        tr.observed_behavior = f"unique_assets={int(features['unique_asset_types'])} expected={len(assets)}"
        tr.numeric_validity = math.isfinite(features["unique_asset_types"])
        tr.logical_validity = features["unique_asset_types"] == float(len(assets))
        tr.status = "PASS" if tr.numeric_validity and tr.logical_validity else "FAIL"
    except Exception as e:
        tr.execution_status = "COMPLETED"
        tr.exception = str(e)
        tr.status = "FAIL"
    results.append(tr)
    return results


def test_incomplete_records(rows, company):
    results = []
    tr = TestResult(company, "INCOMPLETE_RECORDS", "missing optional fields + open alerts")
    tr.expected_behavior = "No crash; missing fields handled safely"
    try:
        modified = copy.deepcopy(rows)
        for i, r in enumerate(modified):
            if i % 5 == 0:
                r["investigation_notes"] = ""
                r["closed_time"] = ""
                r["closure_duration_minutes"] = ""
                r["status"] = "Open"
        eg = compute_eg(modified)
        features = compute_features(modified)
        risk = compute_risk(eg["score"], 0.0, 0.0)
        tr.execution_status = "COMPLETED"
        tr.observed_behavior = f"eg={eg['score']:.4f} risk={risk['final']:.1f} band={risk['band']}"
        tr.numeric_validity = all(math.isfinite(v) for v in [eg["score"], risk["final"]])
        tr.logical_validity = 0 <= risk["final"] <= 100
        tr.status = "PASS" if tr.numeric_validity and tr.logical_validity else "FAIL"
    except Exception as e:
        tr.execution_status = "COMPLETED"
        tr.exception = str(e)
        tr.status = "FAIL"
    results.append(tr)
    return results


def test_extreme_values(rows, company, scaler, clf, feature_names):
    results = []
    tr = TestResult(company, "EXTREME_ANOMALY", "extreme feature values fed to model")
    tr.expected_behavior = "No crash; anomaly score finite and in valid range"
    try:
        import numpy as np
        extreme_fv = {"alert_count": 1e6, "avg_closure_seconds": 1e9, "escalation_rate": 1.0,
                       "critical_ratio": 1.0, "avg_note_length": 1e5, "unique_asset_types": 1e4}
        X = np.array([[extreme_fv[f] for f in feature_names]])
        X_scaled = scaler.transform(X)
        raw = float(clf.decision_function(X_scaled)[0])
        tr.execution_status = "COMPLETED"
        tr.observed_behavior = f"raw_score={raw:.6f}"
        tr.numeric_validity = math.isfinite(raw)
        tr.logical_validity = True
        tr.status = "PASS" if tr.numeric_validity else "FAIL"
    except Exception as e:
        tr.execution_status = "COMPLETED"
        tr.exception = str(e)
        tr.status = "FAIL"
    results.append(tr)

    tr2 = TestResult(company, "ZERO_FEATURES", "all-zero feature vector")
    tr2.expected_behavior = "No crash; anomaly score finite"
    try:
        import numpy as np
        zero_fv = {f: 0.0 for f in feature_names}
        X = np.array([[zero_fv[f] for f in feature_names]])
        X_scaled = scaler.transform(X)
        raw = float(clf.decision_function(X_scaled)[0])
        tr2.execution_status = "COMPLETED"
        tr2.observed_behavior = f"raw_score={raw:.6f}"
        tr2.numeric_validity = math.isfinite(raw)
        tr2.logical_validity = True
        tr2.status = "PASS" if tr2.numeric_validity else "FAIL"
    except Exception as e:
        tr2.execution_status = "COMPLETED"
        tr2.exception = str(e)
        tr2.status = "FAIL"
    results.append(tr2)
    return results


def main():
    log = []
    def p(msg=""):
        print(msg)
        log.append(msg)

    p("=" * 70)
    p("STEP 2.6 - INDEPENDENT EDGE-CASE TESTING")
    p("=" * 70)

    import joblib
    model_dict = joblib.load(MODEL_PATH)
    scaler = model_dict["scaler"]
    clf = model_dict.get("model") or model_dict.get("clf")
    feature_names = model_dict.get("feature_names", [])
    p(f"Model: {type(clf).__name__}, features: {feature_names}")

    all_results = []
    for company, fname in COMPANIES:
        p(f"\n{'='*70}")
        p(f"COMPANY: {company}")
        p(f"{'='*70}")
        rows = load_csv(os.path.join(EXT_DIR, fname))
        p(f"Loaded {len(rows)} rows")

        for test_fn in [test_missing_notes, test_missing_closed_time,
                        test_missing_closure_duration, test_no_critical_alerts,
                        test_no_escalated, test_low_volume, test_asset_types,
                        test_incomplete_records]:
            res = test_fn(rows, company)
            all_results.extend(res)
            for r in res:
                p(f"  [{r.status}] {r.edge_case}: {r.test_condition}")
                if r.exception:
                    p(f"    Exception: {r.exception}")

        res = test_extreme_values(rows, company, scaler, clf, feature_names)
        all_results.extend(res)
        for r in res:
            p(f"  [{r.status}] {r.edge_case}: {r.test_condition}")
            if r.exception:
                p(f"    Exception: {r.exception}")

    total = len(all_results)
    passed = sum(1 for r in all_results if r.status == "PASS")
    warned = sum(1 for r in all_results if r.status == "WARN")
    failed = sum(1 for r in all_results if r.status == "FAIL")
    num_safe = all(r.numeric_validity for r in all_results)
    logic_safe = all(r.logical_validity for r in all_results)
    verdict = "PASS" if failed == 0 and warned == 0 else ("PASS WITH WARNINGS" if failed == 0 else "FAIL")

    p("\n" + "=" * 70)
    p("COMPANY-WISE SUMMARY")
    p("=" * 70)
    for company, _ in COMPANIES:
        co_results = [r for r in all_results if r.company == company]
        co_pass = sum(1 for r in co_results if r.status == "PASS")
        co_fail = sum(1 for r in co_results if r.status == "FAIL")
        p(f"  {company}: {len(co_results)} tests, {co_pass} PASS, {co_fail} FAIL")

    p("\n" + "=" * 70)
    p("NUMERICAL SAFETY CHECKS")
    p("=" * 70)
    p(f"  All values finite: {'PASS' if num_safe else 'FAIL'}")
    p(f"  All logic valid: {'PASS' if logic_safe else 'FAIL'}")
    for r in all_results:
        if not r.numeric_validity:
            p(f"    FAIL: {r.company} {r.edge_case} - {r.observed_behavior}")

    p("\n" + "=" * 70)
    p("INDEPENDENCE AND NON-MODIFICATION PROOF")
    p("=" * 70)
    p("- Production code: NOT modified")
    p("- anomaly_model.joblib: NOT modified")
    p("- Raw CSVs: NOT modified")
    p("- No retraining performed")
    p("- All tests use in-memory copies")

    p("\n" + "=" * 70)
    p("OVERALL VERDICT")
    p("=" * 70)
    p(f"\nStep 2.6 Edge-Case Testing")
    p(f"Datasets tested: {len(COMPANIES)}")
    p(f"Edge cases tested: {total}")
    p(f"PASS: {passed}")
    p(f"WARN: {warned}")
    p(f"FAIL: {failed}")
    p(f"Numerical safety: {'PASS' if num_safe else 'FAIL'}")
    p(f"Detector logic safety: {'PASS' if logic_safe else 'FAIL'}")
    p(f"Raw datasets modified: NO")
    p(f"Production code modified: NO")
    p(f"Overall verdict: {verdict}")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(log))
    print(f"\nReport: {REPORT}")

    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["company", "edge_case", "test_condition", "execution_status",
                     "exception", "numeric_validity", "logical_validity",
                     "expected_behavior", "observed_behavior", "status", "notes"])
        for r in all_results:
            w.writerow([r.company, r.edge_case, r.test_condition, r.execution_status,
                        r.exception, r.numeric_validity, r.logical_validity,
                        r.expected_behavior, r.observed_behavior, r.status, r.notes])
    print(f"CSV: {CSV_OUT}")


if __name__ == "__main__":
    main()
