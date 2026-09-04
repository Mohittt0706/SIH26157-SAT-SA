"""STEP 2.2 — MODEL VALIDATION: Load persisted Isolation Forest, infer on 5 external CSVs."""
import csv
import math
import os
from collections import defaultdict
from datetime import datetime

import joblib
import numpy as np

# ── Config ──────────────────────────────────────────────────────────────────
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE, "backend", "anomaly_model.joblib")
EXT_DIR = os.path.join(BASE, "dataset", "external")
COMPANIES = [
    ("Equifax", "soc_alerts_equifax.csv"),
    ("JPMorgan Chase", "soc_alerts_jpmorgan_chase.csv"),
    ("MGM Resorts", "soc_alerts_mgm_resorts.csv"),
    ("Microsoft", "soc_alerts_microsoft.csv"),
    ("T-Mobile", "soc_alerts_t-mobile.csv"),
]
FEATURE_ORDER = [
    "alert_count", "avg_closure_seconds", "escalation_rate",
    "critical_ratio", "avg_note_length", "unique_asset_types",
]
REPORT_PATH = os.path.join(BASE, "validation_outputs", "step2_model_validation_report.md")
RESULTS_CSV = os.path.join(BASE, "validation_outputs", "step2_model_validation_results.csv")

# ── Helpers ─────────────────────────────────────────────────────────────────
def _parse_dt(s):
    if not s or not s.strip():
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


def compute_features(csv_path):
    """Independently compute 6-feature vector from a CSV (NO production imports)."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    if total == 0:
        raise ValueError(f"Empty CSV: {csv_path}")

    closure_secs = []
    escalated = 0
    critical = 0
    note_lens = []
    assets = set()

    for r in rows:
        sev = (r.get("severity") or "").strip().lower()
        if sev == "critical":
            critical += 1
        if (r.get("escalated") or "").strip().lower() in ("yes", "true", "1"):
            escalated += 1
        asset = (r.get("asset_type") or "").strip()
        if asset:
            assets.add(asset)
        note = (r.get("investigation_notes") or "").strip()
        note_lens.append(len(note) if note else 0)
        # closure_seconds: use closure_duration_minutes if available, else compute
        dur_str = (r.get("closure_duration_minutes") or "").strip()
        ct_str = (r.get("created_time") or "").strip()
        clt_str = (r.get("closed_time") or "").strip()
        cs = None
        if dur_str:
            try:
                v = float(dur_str)
                if v >= 0:
                    cs = v * 60.0
            except ValueError:
                pass
        if cs is None:
            ct = _parse_dt(ct_str)
            clt = _parse_dt(clt_str)
            if ct and clt:
                diff = (clt - ct).total_seconds()
                if diff >= 0:
                    cs = diff
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


# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    log = []

    def p(msg=""):
        print(msg)
        log.append(msg)

    p("=" * 70)
    p("STEP 2.2 — MODEL VALIDATION")
    p("=" * 70)

    # ── 1. Model File Existence ─────────────────────────────────────────────
    p("\n## 1. Model File")
    exists = os.path.isfile(MODEL_PATH)
    p(f"  Path: {MODEL_PATH}")
    p(f"  Exists: {exists}")
    if not exists:
        p("\n  FAIL — model file not found. Aborting.")
        _save(log)
        return

    # ── 2. Load Model ───────────────────────────────────────────────────────
    p("\n## 2. Load Model")
    try:
        model_dict = joblib.load(MODEL_PATH)
        p("  Loaded: OK")
    except Exception as e:
        p(f"  FAIL — could not load: {e}")
        _save(log)
        return

    # ── 3. Model Structure ──────────────────────────────────────────────────
    p("\n## 3. Model Structure")
    p(f"  Type: {type(model_dict).__name__}")
    if isinstance(model_dict, dict):
        p(f"  Keys: {sorted(model_dict.keys())}")
        for k in sorted(model_dict.keys()):
            v = model_dict[k]
            p(f"    {k}: {type(v).__name__}")
            if hasattr(v, "n_estimators"):
                p(f"      n_estimators={v.n_estimators}")
            if hasattr(v, "contamination"):
                p(f"      contamination={v.contamination}")
            if hasattr(v, "random_state"):
                p(f"      random_state={v.random_state}")
            if hasattr(v, "n_features_in_"):
                p(f"      n_features_in_={v.n_features_in_}")
    else:
        p(f"  WARNING — model_dict is {type(model_dict)}, not a dict")

    # Identify scaler and clf
    scaler = model_dict.get("scaler")
    clf = model_dict.get("clf") or model_dict.get("model")
    feature_names = model_dict.get("feature_names", FEATURE_ORDER)

    if scaler is None:
        p("  WARNING — no StandardScaler found in model artifact")
    else:
        p(f"  Scaler type: {type(scaler).__name__}")
        if hasattr(scaler, "n_features_in_"):
            p(f"    n_features_in_: {scaler.n_features_in_}")
        if hasattr(scaler, "mean_"):
            p(f"    mean_: {scaler.mean_}")
        if hasattr(scaler, "scale_"):
            p(f"    scale_: {scaler.scale_}")

    if clf is None:
        p("  FAIL — no IsolationForest estimator found")
        _save(log)
        return

    p(f"  Estimator type: {type(clf).__name__}")
    p(f"  Feature order: {feature_names}")

    # ── 4. Compute Features ─────────────────────────────────────────────────
    p("\n## 4. Feature Computation (independent)")
    company_features = {}
    for name, fname in COMPANIES:
        path = os.path.join(EXT_DIR, fname)
        if not os.path.isfile(path):
            p(f"  {name}: FAIL — file not found")
            continue
        try:
            fv = compute_features(path)
            company_features[name] = fv
            p(f"  {name}: OK  { {k: round(v, 4) for k, v in fv.items()} }")
        except Exception as e:
            p(f"  {name}: FAIL — {e}")

    # ── 5. Feature Shape / Sanity ───────────────────────────────────────────
    p("\n## 5. Feature Shape & Sanity")
    for name, fv in company_features.items():
        vec = [fv[f] for f in feature_names]
        has_nan = any(math.isnan(v) for v in vec)
        has_inf = any(math.isinf(v) for v in vec)
        all_numeric = all(isinstance(v, (int, float)) for v in vec)
        p(f"  {name}: len={len(vec)} numeric={all_numeric} nan={has_nan} inf={has_inf} vec={[round(v,4) for v in vec]}")
        if has_nan or has_inf or not all_numeric or len(vec) != 6:
            p(f"    WARNING — feature sanity issue detected")

    # ── 6. Inference ────────────────────────────────────────────────────────
    p("\n## 6. Model Inference")
    scores_raw = {}
    scores_converted = {}

    entity_names = sorted(company_features.keys())
    X = np.array([[company_features[n][f] for f in feature_names] for n in entity_names])

    # Scale
    if scaler is not None:
        X_scaled = scaler.transform(X)
        p("  Scaler.transform: OK")
    else:
        X_scaled = X
        p("  WARNING — no scaler used")

    # Decision function
    raw = clf.decision_function(X_scaled)
    p(f"  decision_function output shape: {raw.shape}")
    p(f"  decision_function output type: {type(raw)}")
    p(f"  raw scores: {dict(zip(entity_names, [round(float(s), 6) for s in raw]))}")

    # Convert to 0-1
    inverted = -raw
    min_v, max_v = float(inverted.min()), float(inverted.max())
    spread = max_v - min_v
    if spread == 0.0:
        converted = np.zeros_like(inverted, dtype=float)
        p("  Score conversion: spread=0, all scores set to 0.0")
    else:
        converted = (inverted - min_v) / spread
        p(f"  Score conversion: min_raw={min_v:.6f} max_raw={max_v:.6f} spread={spread:.6f}")
    p(f"  converted scores: {dict(zip(entity_names, [round(float(s), 4) for s in converted]))}")

    for i, n in enumerate(entity_names):
        scores_raw[n] = float(raw[i])
        scores_converted[n] = float(converted[i])

    # ── 7. Score Sanity ─────────────────────────────────────────────────────
    p("\n## 7. Score Sanity")
    all_finite = True
    for n in entity_names:
        r_ok = math.isfinite(scores_raw[n])
        c_ok = math.isfinite(scores_converted[n])
        if not r_ok or not c_ok:
            all_finite = False
            p(f"  {n}: FAIL — raw_finite={r_ok} converted_finite={c_ok}")
        else:
            p(f"  {n}: raw={scores_raw[n]:.6f}  converted={scores_converted[n]:.4f}")

    # ── 8. Pipeline Consistency ─────────────────────────────────────────────
    p("\n## 8. Pipeline Consistency")
    p(f"  Scaler present: {scaler is not None}")
    p(f"  Scaler type: {type(scaler).__name__ if scaler else 'N/A'}")
    p(f"  Estimator type: {type(clf).__name__}")
    p(f"  Feature names in artifact: {feature_names}")
    p(f"  Features used for inference: {feature_names}")

    # ── 9. Verdict ──────────────────────────────────────────────────────────
    p("\n" + "=" * 70)
    p("VERDICT")
    p("=" * 70)
    has_fail = False
    has_warn = False
    # Check for any warnings/fails from earlier sections
    for line in log:
        if "FAIL" in line and "##" not in line:
            has_fail = True
        if "WARNING" in line and "##" not in line:
            has_warn = True

    if not all_finite:
        has_fail = True

    if has_fail:
        verdict = "FAIL"
    elif has_warn:
        verdict = "PASS WITH WARNINGS"
    else:
        verdict = "PASS"

    p(f"\n  Final Verdict: {verdict}")
    p(f"  Model loading: {'PASS' if exists and clf is not None else 'FAIL'}")
    p(f"  Model structure: {'PASS' if isinstance(model_dict, dict) and clf is not None else 'FAIL'}")
    p(f"  Feature input: {'PASS' if len(company_features) == 5 else 'FAIL'}")
    p(f"  Inference: {'PASS' if len(entity_names) == 5 else 'FAIL'}")
    p(f"  Score sanity: {'PASS' if all_finite else 'FAIL'}")

    # ── 10. Proof of Independence ───────────────────────────────────────────
    p("\n" + "=" * 70)
    p("PROOF OF INDEPENDENCE")
    p("=" * 70)
    p("  - Production ML/analytics code NOT modified")
    p("  - anomaly_model.joblib NOT modified (read-only load)")
    p("  - Raw CSVs NOT modified")
    p("  - No production feature function imported for computing validation features")
    p("  - No model retraining performed")
    p("  - No commits created")

    # ── Save ────────────────────────────────────────────────────────────────
    _save(log)

    # ── Write CSV ───────────────────────────────────────────────────────────
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["company", "alert_count", "avg_closure_seconds", "escalation_rate",
                     "critical_ratio", "avg_note_length", "unique_asset_types",
                     "raw_score", "converted_score"])
        for n in entity_names:
            fv = company_features[n]
            w.writerow([n] + [round(fv[f], 4) for f in FEATURE_ORDER] +
                       [round(scores_raw[n], 6), round(scores_converted[n], 4)])
    print(f"\nResults CSV saved to: {RESULTS_CSV}")


def _save(log):
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(log))
    print(f"\nReport saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
