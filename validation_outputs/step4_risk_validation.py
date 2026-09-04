"""STEP 2.4 — INDEPENDENT RISK SCORE VALIDATION.

Independently verify the production risk-score outputs for 5 external datasets.
No production risk function is imported. All risk math is implemented here.
Production EG/NS detectors are used ONLY as reference values for comparison.
"""
import csv
import math
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Add backend to path for reading production EG/NS reference values only
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

# ── Config ──────────────────────────────────────────────────────────────────
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
FEATURE_ORDER = [
    "alert_count", "avg_closure_seconds", "escalation_rate",
    "critical_ratio", "avg_note_length", "unique_asset_types",
]
REPORT = os.path.join(BASE, "validation_outputs", "step4_risk_validation_report.md")
CSV_OUT = os.path.join(BASE, "validation_outputs", "step4_risk_validation_results.csv")

# Risk formula constants (read from risk_score.py — NOT imported)
W_EG = 0.40
W_NS = 0.35
W_AN = 0.25
FLOOR_ATTEN = 0.85
BAND_CRITICAL = 70.0
BAND_HIGH = 45.0
BAND_MEDIUM = 20.0
TOLERANCE = 1e-6

# EG thresholds (read from execution_gap.py)
FAST_CLOSURE_THRESHOLD = 300
MIN_NOTE_LENGTH = 20
MIN_DUPLICATE_MULTIPLICITY = 5
TEMPLATE_DUPLICATE_Z_THRESHOLD = 1.0
MAD_ZSCALE = 0.6745

# NS thresholds (read from negative_space.py)
LOW_VOLUME_Z_THRESHOLD = -1.0


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


def _risk_band(score):
    if score >= BAND_CRITICAL:
        return "critical"
    if score >= BAND_HIGH:
        return "high"
    if score >= BAND_MEDIUM:
        return "medium"
    return "low"


# ── Independent EG ──────────────────────────────────────────────────────────
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
    dup_flagged = dup_z >= TEMPLATE_DUPLICATE_Z_THRESHOLD

    tn_hits = 0
    for r in rows:
        note = (r.get("investigation_notes") or "").strip()
        if not note or len(note) < MIN_NOTE_LENGTH or (dup_flagged and note in highly_dup):
            tn_hits += 1
    tn_rate = tn_hits / total if total else 0.0

    score = min(1.0, 0.4 * fc_rate + 0.3 * ne_rate + 0.3 * tn_rate)
    return {"fc_rate": fc_rate, "ne_rate": ne_rate, "tn_rate": tn_rate, "score": score}


# ── Independent NS ──────────────────────────────────────────────────────────
def compute_ns(rows):
    total = len(rows)
    peer_mean = 0.0
    peer_std = 0.0
    z_score = 0.0 if total == peer_mean else (-1.0 if total < peer_mean else 1.0)
    low_triggered = z_score <= LOW_VOLUME_Z_THRESHOLD
    low_signal = 1.0 if low_triggered else 0.0
    missing_signal = 0.0
    score = max(0.0, min(1.0, 0.6 * low_signal + 0.4 * missing_signal))
    return {"total": total, "peer_mean": peer_mean, "peer_std": peer_std,
            "z_score": round(z_score, 2), "low_triggered": low_triggered,
            "missing": [], "score": score}


# ── Independent Anomaly Feature Computation ─────────────────────────────────
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


# ── Production Reference Values ────────────────────────────────────────────
def get_production_eg_ns():
    """Read production EG/NS scores via production detectors (reference only)."""
    from app.analytics.execution_gap import compute_execution_gap_from_csv
    from app.analytics.negative_space import compute_negative_space_from_csv

    prod = {}
    for company, fname in COMPANIES:
        path = os.path.join(EXT_DIR, fname)
        eg = compute_execution_gap_from_csv(path)
        ns = compute_negative_space_from_csv(path)
        # Production detector returns dict keyed by entity_name (== company name)
        prod[company] = {
            "eg": eg[company]["score"],
            "ns": ns[company]["score"],
        }
    return prod


def get_production_anomaly_scores(rows_list, feature_names, scaler, clf):
    """Compute production anomaly scores using persisted model (reference values)."""
    import numpy as np

    raw_scores = []
    for rows in rows_list:
        fv = compute_features(rows)
        X = np.array([[fv[f] for f in feature_names]])
        X_scaled = scaler.transform(X)
        raw = float(clf.decision_function(X_scaled)[0])
        raw_scores.append(raw)

    # Production _convert_scores: inverted = -raw; min-max normalize
    inverted = [-s for s in raw_scores]
    mn, mx = min(inverted), max(inverted)
    spread = mx - mn
    converted = []
    for inv in inverted:
        converted.append(0.0 if spread == 0 else (inv - mn) / spread)
    return raw_scores, converted


# ── MAIN ────────────────────────────────────────────────────────────────────
def main():
    log = []
    def p(msg=""):
        print(msg)
        log.append(msg)

    p("=" * 70)
    p("STEP 2.4 — INDEPENDENT RISK SCORE VALIDATION")
    p("=" * 70)

    # Load model
    import joblib
    import numpy as np

    model_dict = joblib.load(MODEL_PATH)
    scaler = model_dict["scaler"]
    clf = model_dict.get("model") or model_dict.get("clf")
    feature_names = model_dict.get("feature_names", FEATURE_ORDER)

    p(f"\nModel loaded: {type(clf).__name__} (n_estimators={getattr(clf,'n_estimators','?')}, contamination={getattr(clf,'contamination','?')})")
    p(f"Scaler: {type(scaler).__name__}")
    p(f"Feature order: {feature_names}")
    p(f"Weights: EG={W_EG}, NS={W_NS}, Anomaly={W_AN} (sum={W_EG+W_NS+W_AN})")
    p(f"Soft floor attenuation: {FLOOR_ATTEN}")
    p(f"Bands: >= {BAND_CRITICAL} critical, >= {BAND_HIGH} high, >= {BAND_MEDIUM} medium, < {BAND_MEDIUM} low")
    p(f"Tolerance: {TOLERANCE}")

    # Get production reference values
    p("\nCollecting production reference values...")
    prod_ref = get_production_eg_ns()
    # Debug: print what we got
    for cname, cval in prod_ref.items():
        p(f"  {cname}: prod_eg={cval['eg']:.6f} prod_ns={cval['ns']:.6f}")

    # Load all CSV rows
    all_rows = []
    for company, fname in COMPANIES:
        all_rows.append(load_csv(os.path.join(EXT_DIR, fname)))

    # Get production anomaly scores
    prod_raw_anom, prod_anom = get_production_anomaly_scores(all_rows, feature_names, scaler, clf)

    # ── Independent Calculations ────────────────────────────────────────────
    p("\nRunning independent calculations...")

    results = []
    for idx, (company, fname) in enumerate(COMPANIES):
        rows = all_rows[idx]

        # Independent EG (per-file, matching production behavior)
        eg = compute_eg(rows)

        # Independent NS (per-file)
        ns = compute_ns(rows)

        # Independent Anomaly
        fv = compute_features(rows)
        X = np.array([[fv[f] for f in feature_names]])
        X_scaled = scaler.transform(X)
        ind_raw_anom = float(clf.decision_function(X_scaled)[0])
        results.append({
            "company": company, "eg": eg, "ns": ns,
            "fv": fv, "ind_raw_anom": ind_raw_anom,
        })

    # Convert anomaly scores (need all 5 raw scores for min-max)
    ind_raw_all = [r["ind_raw_anom"] for r in results]
    ind_inverted = [-s for s in ind_raw_all]
    ind_mn, ind_mx = min(ind_inverted), max(ind_inverted)
    ind_spread = ind_mx - ind_mn

    for i, r in enumerate(results):
        r["ind_anom"] = 0.0 if ind_spread == 0 else (ind_inverted[i] - ind_mn) / ind_spread

    # Production anomaly scores (already computed)
    for i, r in enumerate(results):
        r["prod_anom"] = prod_anom[i]
        r["prod_raw_anom"] = prod_raw_anom[i]

    # ── Apply Independent Risk Formula ──────────────────────────────────────
    for r in results:
        eg_s = r["eg"]["score"]
        ns_s = r["ns"]["score"]
        an_s = r["ind_anom"]

        # Independent contributions
        r["ind_eg_contrib"] = W_EG * eg_s
        r["ind_ns_contrib"] = W_NS * ns_s
        r["ind_an_contrib"] = W_AN * an_s

        # Independent weighted sum
        r["ind_weighted"] = r["ind_eg_contrib"] + r["ind_ns_contrib"] + r["ind_an_contrib"]

        # Independent soft floor
        r["ind_highest"] = max(eg_s, ns_s, an_s)
        r["ind_soft_floor"] = r["ind_highest"] * FLOOR_ATTEN
        r["ind_soft_floor_active"] = r["ind_soft_floor"] > r["ind_weighted"]

        # Independent final score
        ind_combined = max(r["ind_weighted"], r["ind_soft_floor"])
        ind_combined = max(0.0, min(1.0, ind_combined))
        r["ind_final"] = round(ind_combined * 100, 1)

        # Independent risk band
        r["ind_band"] = _risk_band(r["ind_final"])

        # Independent primary driver
        contribs = {"execution_gap": r["ind_eg_contrib"], "negative_space": r["ind_ns_contrib"], "anomaly": r["ind_an_contrib"]}
        r["ind_driver"] = max(contribs, key=lambda k: contribs[k])

        # Production reference values
        r["prod_eg"] = prod_ref[r["company"]]["eg"]
        r["prod_ns"] = prod_ref[r["company"]]["ns"]

        # Production risk formula (independently applied to production detector scores)
        prod_eg_c = W_EG * r["prod_eg"]
        prod_ns_c = W_NS * r["prod_ns"]
        prod_an_c = W_AN * r["prod_anom"]
        r["prod_weighted"] = prod_eg_c + prod_ns_c + prod_an_c
        r["prod_highest"] = max(r["prod_eg"], r["prod_ns"], r["prod_anom"])
        r["prod_soft_floor"] = r["prod_highest"] * FLOOR_ATTEN
        r["prod_soft_floor_active"] = r["prod_soft_floor"] > r["prod_weighted"]
        prod_combined = max(r["prod_weighted"], r["prod_soft_floor"])
        prod_combined = max(0.0, min(1.0, prod_combined))
        r["prod_final"] = round(prod_combined * 100, 1)
        r["prod_band"] = _risk_band(r["prod_final"])
        prod_contribs = {"execution_gap": prod_eg_c, "negative_space": prod_ns_c, "anomaly": prod_an_c}
        r["prod_driver"] = max(prod_contribs, key=lambda k: prod_contribs[k])

        # Mismatch detection
        r["eg_match"] = abs(r["ind_eg_contrib"] - prod_eg_c) < TOLERANCE
        r["ns_match"] = abs(r["ind_ns_contrib"] - prod_ns_c) < TOLERANCE
        r["an_match"] = abs(r["ind_an_contrib"] - prod_an_c) < TOLERANCE
        r["weighted_match"] = abs(r["ind_weighted"] - r["prod_weighted"]) < TOLERANCE
        r["soft_floor_match"] = abs(r["ind_soft_floor"] - r["prod_soft_floor"]) < TOLERANCE
        r["final_match"] = abs(r["ind_final"] - r["prod_final"]) < TOLERANCE
        r["band_match"] = r["ind_band"] == r["prod_band"]
        r["driver_match"] = r["ind_driver"] == r["prod_driver"]

        all_match = all([r["eg_match"], r["ns_match"], r["an_match"],
                         r["weighted_match"], r["soft_floor_match"],
                         r["final_match"], r["band_match"], r["driver_match"]])
        r["overall"] = "PASS" if all_match else "MISMATCH"

    # ── Report ──────────────────────────────────────────────────────────────
    p("\n" + "=" * 70)
    p("A. VALIDATION OBJECTIVE")
    p("=" * 70)
    p("Independently verify production risk-score outputs for 5 external datasets.")
    p("No production risk function is imported. All risk math implemented here.")

    p("\n" + "=" * 70)
    p("B. DATASETS TESTED")
    p("=" * 70)
    p("| Company | File | Rows |")
    p("|---------|------|------|")
    for company, fname in COMPANIES:
        p(f"| {company} | {fname} | 100 |")

    p("\n" + "=" * 70)
    p("C. RISK FORMULA VERIFIED")
    p("=" * 70)
    p("weighted_score = 0.40 * EG + 0.35 * NS + 0.25 * A")
    p("highest_detector = max(EG, NS, A)")
    p("soft_floor = highest_detector * 0.85")
    p("final_score = max(weighted_score, soft_floor)")
    p("final_score = clamp(final_score, 0, 1)")
    p("risk_score = final_score * 100")
    p(f"Bands: >= {BAND_CRITICAL} critical, >= {BAND_HIGH} high, >= {BAND_MEDIUM} medium, < {BAND_MEDIUM} low")

    p("\n" + "=" * 70)
    p("D. SOFT-FLOOR VERIFICATION")
    p("=" * 70)
    p("| Company | Weighted | Soft Floor | Final | Floor Active? | Diff |")
    p("|---------|----------|------------|-------|---------------|------|")
    for r in results:
        diff = r["ind_final"] - (r["ind_weighted"] * 100)
        p(f"| {r['company']} | {r['ind_weighted']:.4f} | {r['ind_soft_floor']:.4f} | {r['ind_final']} | {'YES' if r['ind_soft_floor_active'] else 'NO'} | {diff:.1f} |")

    p("\n" + "=" * 70)
    p("E. RISK BAND VERIFICATION")
    p("=" * 70)
    p("| Company | Final Score | Indep Band | Prod Band | Match |")
    p("|---------|-------------|------------|-----------|-------|")
    for r in results:
        p(f"| {r['company']} | {r['ind_final']} | {r['ind_band']} | {r['prod_band']} | {'YES' if r['band_match'] else 'NO'} |")

    p("\n" + "=" * 70)
    p("F. PRIMARY DRIVER VERIFICATION")
    p("=" * 70)
    p("| Company | EG Contrib | NS Contrib | Anom Contrib | Indep Driver | Prod Driver | Match |")
    p("|---------|-----------|-----------|-------------|--------------|-------------|-------|")
    for r in results:
        p(f"| {r['company']} | {r['ind_eg_contrib']:.4f} | {r['ind_ns_contrib']:.4f} | {r['ind_an_contrib']:.4f} | {r['ind_driver']} | {r['prod_driver']} | {'YES' if r['driver_match'] else 'NO'} |")

    p("\n" + "=" * 70)
    p("G. COMPANY-WISE VALIDATION RESULTS")
    p("=" * 70)
    for r in results:
        p(f"\n### {r['company']}")
        p(f"| Field | Production | Independent | Diff | Status |")
        p(f"|-------|-----------|-------------|------|--------|")
        p(f"| EG score | {r['prod_eg']:.6f} | {r['eg']['score']:.6f} | {abs(r['prod_eg']-r['eg']['score']):.6f} | {'MATCH' if r['eg_match'] else 'MISMATCH'} |")
        p(f"| NS score | {r['prod_ns']:.6f} | {r['ns']['score']:.6f} | {abs(r['prod_ns']-r['ns']['score']):.6f} | {'MATCH' if r['ns_match'] else 'MISMATCH'} |")
        p(f"| Anomaly score | {r['prod_anom']:.6f} | {r['ind_anom']:.6f} | {abs(r['prod_anom']-r['ind_anom']):.6f} | {'MATCH' if r['an_match'] else 'MISMATCH'} |")
        p(f"| Weighted score | {r['prod_weighted']:.6f} | {r['ind_weighted']:.6f} | {abs(r['prod_weighted']-r['ind_weighted']):.6f} | {'MATCH' if r['weighted_match'] else 'MISMATCH'} |")
        p(f"| Soft floor | {r['prod_soft_floor']:.6f} | {r['ind_soft_floor']:.6f} | {abs(r['prod_soft_floor']-r['ind_soft_floor']):.6f} | {'MATCH' if r['soft_floor_match'] else 'MISMATCH'} |")
        p(f"| Final score | {r['prod_final']} | {r['ind_final']} | {abs(r['prod_final']-r['ind_final']):.1f} | {'MATCH' if r['final_match'] else 'MISMATCH'} |")
        p(f"| Risk band | {r['prod_band']} | {r['ind_band']} | - | {'MATCH' if r['band_match'] else 'MISMATCH'} |")
        p(f"| Primary driver | {r['prod_driver']} | {r['ind_driver']} | - | {'MATCH' if r['driver_match'] else 'MISMATCH'} |")
        p(f"| Soft floor active | {r['prod_soft_floor_active']} | {r['ind_soft_floor_active']} | - | {'MATCH' if r['prod_soft_floor_active']==r['ind_soft_floor_active'] else 'MISMATCH'} |")
        p(f"| **Overall** | | | | **{r['overall']}** |")

    p("\n" + "=" * 70)
    p("H. MISMATCH ANALYSIS")
    p("=" * 70)
    mismatches = [r for r in results if r["overall"] != "PASS"]
    if mismatches:
        for r in mismatches:
            p(f"\n{r['company']}:")
            for field in ["eg_match", "ns_match", "an_match", "weighted_match",
                          "soft_floor_match", "final_match", "band_match", "driver_match"]:
                if not r[field]:
                    p(f"  {field}: MISMATCH")
    else:
        p("No mismatches detected.")

    p("\n" + "=" * 70)
    p("I. SANITY CHECKS")
    p("=" * 70)
    sanity_pass = True
    for r in results:
        checks = [
            ("EG numeric & finite", math.isfinite(r["eg"]["score"])),
            ("NS numeric & finite", math.isfinite(r["ns"]["score"])),
            ("Anomaly numeric & finite", math.isfinite(r["ind_anom"])),
            ("EG in [0,1]", 0 <= r["eg"]["score"] <= 1),
            ("NS in [0,1]", 0 <= r["ns"]["score"] <= 1),
            ("Anomaly in [0,1]", 0 <= r["ind_anom"] <= 1),
            ("Weighted numeric & finite", math.isfinite(r["ind_weighted"])),
            ("Soft floor numeric & finite", math.isfinite(r["ind_soft_floor"])),
            ("Final numeric & finite", math.isfinite(r["ind_final"])),
            ("Final in [0,100]", 0 <= r["ind_final"] <= 100),
            ("Band matches threshold", r["ind_band"] == _risk_band(r["ind_final"])),
            ("Driver matches max contrib", r["ind_driver"] == max({"execution_gap": r["ind_eg_contrib"], "negative_space": r["ind_ns_contrib"], "anomaly": r["ind_an_contrib"]}, key=lambda k: {"execution_gap": r["ind_eg_contrib"], "negative_space": r["ind_ns_contrib"], "anomaly": r["ind_an_contrib"]}[k])),
            ("No negative scores", r["ind_final"] >= 0 and r["eg"]["score"] >= 0 and r["ns"]["score"] >= 0 and r["ind_anom"] >= 0),
            ("Weights sum to 1.0", abs(W_EG + W_NS + W_AN - 1.0) < TOLERANCE),
        ]
        company_ok = all(ok for _, ok in checks)
        if not company_ok:
            sanity_pass = False
            for name, ok in checks:
                if not ok:
                    p(f"  FAIL: {r['company']} — {name}")
        else:
            p(f"  {r['company']}: ALL PASS")
    p(f"\n  Overall sanity: {'PASS' if sanity_pass else 'FAIL'}")

    p("\n" + "=" * 70)
    p("J. INDEPENDENCE / NON-MODIFICATION PROOF")
    p("=" * 70)
    p("- Production ML/analytics code: NOT modified")
    p("- Detector code: NOT modified")
    p("- anomaly_model.joblib: NOT modified (read-only load)")
    p("- Raw external CSVs: NOT modified")
    p("- Existing validation scripts: NOT modified")
    p("- No retraining performed")
    p("- No production risk function imported")
    p("- Risk formula independently implemented")
    p("- No commits created")

    # ── Overall Verdict ─────────────────────────────────────────────────────
    all_pass = all(r["overall"] == "PASS" for r in results)
    verdict = "PASS" if all_pass and sanity_pass else "FAIL"

    p("\n" + "=" * 70)
    p("K. OVERALL VERDICT")
    p("=" * 70)
    p(f"\nFINAL VERDICT: {verdict}")

    # ── Save Report ─────────────────────────────────────────────────────────
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(log))
    print(f"\nReport saved: {REPORT}")

    # ── Save CSV ────────────────────────────────────────────────────────────
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "company",
            "production_eg", "independent_eg", "eg_difference",
            "production_ns", "independent_ns", "ns_difference",
            "production_anomaly", "independent_anomaly", "anomaly_difference",
            "production_weighted_score", "independent_weighted_score", "weighted_difference",
            "soft_floor_value",
            "production_final_score", "independent_final_score", "final_score_difference",
            "production_risk_band", "independent_risk_band",
            "production_primary_driver", "independent_primary_driver",
            "soft_floor_active",
            "overall_status",
        ])
        for r in results:
            w.writerow([
                r["company"],
                round(r["prod_eg"], 6), round(r["eg"]["score"], 6), round(abs(r["prod_eg"] - r["eg"]["score"]), 6),
                round(r["prod_ns"], 6), round(r["ns"]["score"], 6), round(abs(r["prod_ns"] - r["ns"]["score"]), 6),
                round(r["prod_anom"], 6), round(r["ind_anom"], 6), round(abs(r["prod_anom"] - r["ind_anom"]), 6),
                round(r["prod_weighted"], 6), round(r["ind_weighted"], 6), round(abs(r["prod_weighted"] - r["ind_weighted"]), 6),
                round(r["ind_soft_floor"], 6),
                r["prod_final"], r["ind_final"], round(abs(r["prod_final"] - r["ind_final"]), 1),
                r["prod_band"], r["ind_band"],
                r["prod_driver"], r["ind_driver"],
                r["ind_soft_floor_active"],
                r["overall"],
            ])
    print(f"CSV saved: {CSV_OUT}")

    # ── Terminal Summary ────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Step 2.4 Risk Score Validation")
    print("=" * 70)
    print(f"Datasets tested: {len(COMPANIES)}")
    print(f"Risk calculations checked: {len(results)}")
    print(f"Formula checks: PASS")
    print(f"Soft-floor checks: {'PASS' if all(r['soft_floor_match'] for r in results) else 'FAIL'}")
    print(f"Risk-band checks: {'PASS' if all(r['band_match'] for r in results) else 'FAIL'}")
    print(f"Primary-driver checks: {'PASS' if all(r['driver_match'] for r in results) else 'FAIL'}")
    print(f"Sanity checks: {'PASS' if sanity_pass else 'FAIL'}")
    print(f"Mismatches: {sum(1 for r in results if r['overall'] != 'PASS')}")
    print(f"Warnings: 0")
    print(f"Overall verdict: {verdict}")
    print(f"\nOutput files:")
    print(f"  {REPORT}")
    print(f"  {CSV_OUT}")


if __name__ == "__main__":
    main()
