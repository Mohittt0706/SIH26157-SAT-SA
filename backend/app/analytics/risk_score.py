"""Risk Score combiner — merges the three detectors into one per-entity risk score.

Reads the shared detector contract documented in project.md from
execution_gap.py, negative_space.py, and anomaly.py — each exposes
``compute_<name>(db: Session) -> dict[str, dict]`` where every value is
``{"score": float, "metrics": dict, "evidence": list[{"detail": str, "reason": str}]}``.
This module only calls those public functions; it never imports or touches
detector internals.

IMPORTANT — risk_band is an investigative priority ranking, not a verdict.
It tells a reviewer where to look first, not who is guilty:
  - critical / high: strong evidence of supervisory failure — the entity's
    behaviour diverges from its peers in a way the underlying detectors can
    point to specific alerts for.
  - medium: an elevated signal warranting human review — not proof of
    wrongdoing, just enough deviation from peers that it shouldn't be
    ignored.
  - low: no significant deviation from peers on any detector.
This distinction matters in practice: a normal, non-performative entity can
still land at "medium" (see the soft-floor trade-off discussion around
FLOOR_ATTENUATION below) without that being a false positive in the sense of
a wrong verdict — it is the tool correctly flagging borderline signal for a
human to look at, exactly as intended.
"""

from typing import Literal

from sqlalchemy.orm import Session

from app.analytics.anomaly import compute_anomaly
from app.analytics.execution_gap import compute_execution_gap
from app.analytics.negative_space import compute_negative_space

# --- Tunable weights and thresholds -----------------------------------------

WEIGHT_EXECUTION_GAP: float = 0.40
WEIGHT_NEGATIVE_SPACE: float = 0.35
WEIGHT_ANOMALY: float = 0.25
# Must sum to 1.0.

FLOOR_ATTENUATION: float = 0.85
"""MAX_DETECTOR_FLOOR rule strength (see _apply_max_detector_floor).

The combined score is floored at ``highest_raw_detector_score * FLOOR_ATTENUATION``
— a continuous soft floor with no threshold, so there is no cliff to fall
off of. Every entity gets the same treatment regardless of how close its
highest detector score happens to land to any particular cutoff.

Why a floor at all: in the real dataset, negative_space returns 0.000 for 9
of 10 entities (see project.md's "Current status" — it fires rarely by
design). A pure weighted average silently punishes an entity that trips one
detector hard, because the other two being at 0 drags the average down.
Concretely: Delta Rail Systems scores 0.800 on negative_space and 1.000 on
anomaly but 0.000 on execution_gap. Its weighted average alone would be
0.40*0 + 0.35*0.80 + 0.25*1.00 = 0.53 — a single detector at 1.000 is a
genuine catch a jury should see ranked at the top, not diluted toward the
middle by two quiet detectors.

Why a *soft* floor and not a hard threshold: an earlier version only applied
the floor when a detector exceeded 0.70, which produced exactly the kind of
binary-threshold cliff the median/MAD rework in negative_space.py and
execution_gap.py was meant to eliminate — two entities 0.016 apart in raw
score (Indus 0.727, Continental 0.684) landed 31 risk-score points apart
purely because one side of 0.70 and the other wasn't. The soft floor removes
that cliff entirely at the cost of also lifting some low, single-detector
scores partway — see the FLOOR_ATTENUATION tuning note in project usage;
re-check for baseline entities crossing into "medium" whenever this constant
changes.
"""

RISK_BAND_CRITICAL_THRESHOLD: float = 70.0
RISK_BAND_HIGH_THRESHOLD: float = 45.0
RISK_BAND_MEDIUM_THRESHOLD: float = 20.0
# Below RISK_BAND_MEDIUM_THRESHOLD is "low".

MAX_MERGED_EVIDENCE: int = 8
"""Cap on the total evidence items merged across all three detectors per entity."""

RiskBand = Literal["critical", "high", "medium", "low"]

# Fallback used only if an entity is somehow absent from one detector's
# results (shouldn't happen — all three iterate the same alerts table).
_EMPTY_DETECTOR_RESULT: dict = {"score": 0.0, "metrics": {}, "evidence": []}


def compute_risk_scores(db: Session) -> list[dict]:
    """Combine execution_gap, negative_space, and anomaly into one risk score per entity.

    Runs all three detectors, combines their scores with a weighted sum
    (see WEIGHT_* constants) subject to the MAX_DETECTOR_FLOOR rule (see
    SINGLE_DETECTOR_ALERT_THRESHOLD), and returns one row per entity sorted
    by risk_score descending. Each row's ``evidence`` merges up to
    MAX_MERGED_EVIDENCE items from the underlying detectors, tagged with
    ``source``, so a jury can trace every flag back to its origin.
    """
    execution_gap_results = compute_execution_gap(db)
    negative_space_results = compute_negative_space(db)
    anomaly_results = compute_anomaly(db)

    entity_names = (
        set(execution_gap_results) | set(negative_space_results) | set(anomaly_results)
    )

    rows = [
        _combine_entity(
            entity_name,
            execution_gap_results.get(entity_name, _EMPTY_DETECTOR_RESULT),
            negative_space_results.get(entity_name, _EMPTY_DETECTOR_RESULT),
            anomaly_results.get(entity_name, _EMPTY_DETECTOR_RESULT),
        )
        for entity_name in entity_names
    ]

    rows.sort(key=lambda row: row["risk_score"], reverse=True)
    return rows


def compute_risk_scores_from_csv(csv_path, model_artifact_path) -> list[dict]:
    """Combine execution_gap, negative_space, and anomaly from a CSV file into risk score rows."""
    from pathlib import Path
    from app.analytics.anomaly import extract_features_from_csv, predict_anomaly
    from app.analytics.execution_gap import compute_execution_gap_from_csv
    from app.analytics.negative_space import compute_negative_space_from_csv

    eg_dict = compute_execution_gap_from_csv(csv_path)
    ns_dict = compute_negative_space_from_csv(csv_path)
    feat_map = extract_features_from_csv(csv_path)

    # Predict anomaly using the joblib model artifact
    anomaly_obj = predict_anomaly(feat_map, model_artifact_path)
    an_dict = {
        name: {
            "score": res.score,
            "metrics": res.metrics,
            "evidence": res.evidence,
        }
        for name, res in anomaly_obj.items()
    }

    entity_names = set(eg_dict) | set(ns_dict) | set(an_dict)

    rows = [
        _combine_entity(
            entity_name,
            eg_dict.get(entity_name, _EMPTY_DETECTOR_RESULT),
            ns_dict.get(entity_name, _EMPTY_DETECTOR_RESULT),
            an_dict.get(entity_name, _EMPTY_DETECTOR_RESULT),
        )
        for entity_name in entity_names
    ]

    rows.sort(key=lambda row: row["risk_score"], reverse=True)
    return rows



def _combine_entity(
    entity_name: str,
    execution_gap: dict,
    negative_space: dict,
    anomaly: dict,
) -> dict:
    """Combine one entity's three detector outputs into a single risk_score row."""
    eg_score = execution_gap["score"]
    ns_score = negative_space["score"]
    an_score = anomaly["score"]

    contributions = {
        "execution_gap": WEIGHT_EXECUTION_GAP * eg_score,
        "negative_space": WEIGHT_NEGATIVE_SPACE * ns_score,
        "anomaly": WEIGHT_ANOMALY * an_score,
    }
    weighted_sum = sum(contributions.values())

    combined = _apply_max_detector_floor(
        weighted_sum, {"execution_gap": eg_score, "negative_space": ns_score, "anomaly": an_score}
    )
    combined = max(0.0, min(1.0, combined))
    risk_score = round(combined * 100, 1)

    # primary_driver reflects the weighted contribution, per the detector
    # contract — note this can differ from the detector that triggered the
    # MAX_DETECTOR_FLOOR, since that rule looks at raw scores, not weighted ones.
    primary_driver = max(contributions, key=lambda name: contributions[name])

    flags = _collect_flags(execution_gap, negative_space, anomaly)
    evidence = _merge_evidence(
        {
            "execution_gap": (eg_score, execution_gap["evidence"]),
            "negative_space": (ns_score, negative_space["evidence"]),
            "anomaly": (an_score, anomaly["evidence"]),
        }
    )

    return {
        "entity_name": entity_name,
        "risk_score": risk_score,
        "risk_band": _risk_band(risk_score),
        "execution_gap_score": eg_score,
        "negative_space_score": ns_score,
        "anomaly_score": an_score,
        "primary_driver": primary_driver,
        "flags": flags,
        "evidence": evidence,
    }


def _apply_max_detector_floor(weighted_sum: float, raw_scores: dict[str, float]) -> float:
    """Floor the weighted sum at highest_raw_detector_score * FLOOR_ATTENUATION.

    A continuous soft floor, not a threshold — see FLOOR_ATTENUATION's docstring.
    """
    highest_score = max(raw_scores.values())
    return max(weighted_sum, highest_score * FLOOR_ATTENUATION)


def _risk_band(risk_score: float) -> RiskBand:
    """Map a 0-100 risk_score to its named band."""
    if risk_score >= RISK_BAND_CRITICAL_THRESHOLD:
        return "critical"
    if risk_score >= RISK_BAND_HIGH_THRESHOLD:
        return "high"
    if risk_score >= RISK_BAND_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def _flag_from_evidence_detail(source: str, detail: str) -> str:
    """Extract a short rule/feature name flag from an evidence item's detail string.

    execution_gap formats detail as "<RULE> — <alert_id>"; negative_space as
    "<TYPE>: <description>"; anomaly has no named rule, so the deviant
    feature name itself (e.g. "avg_closure_seconds = 45 (...)") is used.
    """
    if source == "anomaly":
        return detail.split(" = ", 1)[0].strip().upper()
    separator = " — " if " — " in detail else ": "
    return detail.split(separator, 1)[0].strip()


def _collect_flags(execution_gap: dict, negative_space: dict, anomaly: dict) -> list[str]:
    """Short rule/feature names that fired across all three detectors for this entity."""
    sources = (
        ("execution_gap", execution_gap["evidence"]),
        ("negative_space", negative_space["evidence"]),
        ("anomaly", anomaly["evidence"]),
    )
    flags: list[str] = []
    seen: set[str] = set()
    for source, evidence in sources:
        for item in evidence:
            flag = _flag_from_evidence_detail(source, item["detail"])
            if flag not in seen:
                seen.add(flag)
                flags.append(flag)
    return flags


def _merge_evidence(tagged: dict[str, tuple[float, list[dict]]]) -> list[dict]:
    """Merge evidence across detectors, tagged with source, capped at MAX_MERGED_EVIDENCE.

    Detectors are visited highest-scoring first, so the strongest signal's
    evidence fills the cap before a weaker detector's evidence is considered.
    """
    ordered_sources = sorted(tagged.items(), key=lambda kv: kv[1][0], reverse=True)

    merged: list[dict] = []
    for source, (_score, evidence) in ordered_sources:
        for item in evidence:
            if len(merged) >= MAX_MERGED_EVIDENCE:
                return merged
            merged.append({"source": source, "detail": item["detail"], "reason": item["reason"]})
    return merged
