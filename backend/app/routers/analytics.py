"""GET /api/risk-scores and GET /api/entities/{entity_name} — the dashboard and
drill-down views over the three detectors' combined output.

Reuses each detector's already-computed ``metrics``/``evidence`` (see
project.md's detector contract) rather than re-deriving anything from the
alerts table directly.
"""

import statistics

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analytics.anomaly import compute_anomaly
from app.analytics.execution_gap import compute_execution_gap
from app.analytics.negative_space import compute_negative_space
from app.analytics.risk_score import compute_risk_scores
from app.database import get_db
from app.schemas import EntityDrillDown, RiskScoreSummary

router = APIRouter()

MAX_FINDING_EVIDENCE: int = 5
"""Cap on evidence items shown per finding on the drill-down page."""

PEER_METRIC_FIELDS: list[str] = [
    "avg_closure_seconds",
    "escalation_rate",
    "avg_note_length",
    "alert_count",
]
"""Feature names pulled from anomaly.py's per-entity metrics for peer comparison."""

DETECTOR_DISPLAY_NAMES: dict[str, str] = {
    "execution_gap": "Execution Gap",
    "negative_space": "Negative Space",
    "anomaly": "Anomaly",
}

FINDING_SUMMARY_THRESHOLD: float = 0.30
"""Minimum raw detector score (0.0-1.0) for that detector to count as having
"meaningfully fired" — gates both findings_summary on the dashboard and the
findings list on the drill-down page.

Without this gate, any detector score above exactly 0.0 was included, which
in practice meant nearly every entity showed the same badges: anomaly's
evidence is unconditional top-3-deviant-feature reporting (see anomaly.py),
so it rarely lands at exactly 0.0, and most entities pick up at least a
sliver of execution_gap score from a single short note. A badge on 9 of 10
rows carries no information — this threshold keeps findings_summary reserved
for scores that are actually elevated, not just non-zero.
"""

RULE_DESCRIPTIONS: dict[str, str] = {
    "FAST_CLOSURE": (
        "Critical or high severity alerts closed implausibly fast, under the "
        "investigation-time threshold."
    ),
    "NO_ESCALATION": "Critical severity alerts that were never escalated.",
    "TEMPLATE_NOTES": (
        "Investigation notes that are empty, too short, or copy-pasted at a rate "
        "meaningfully above the peer baseline."
    ),
    "LOW_ALERT_VOLUME": (
        "Total alert volume significantly below the peer baseline — a possible "
        "sign of missing telemetry."
    ),
    "MISSING_EXPECTED_SEVERITY": (
        "A severity category common across peer entities is entirely absent here."
    ),
    "ASSET_SILENCE": "Asset types that generate alerts for peers produce none here.",
    "ALERT_COUNT": "Total alert count deviates significantly from the peer median.",
    "AVG_CLOSURE_SECONDS": "Average alert closure time deviates significantly from the peer median.",
    "ESCALATION_RATE": "Escalation rate deviates significantly from the peer median.",
    "CRITICAL_RATIO": "Proportion of critical-severity alerts deviates significantly from the peer median.",
    "AVG_NOTE_LENGTH": "Average investigation note length deviates significantly from the peer median.",
    "UNIQUE_ASSET_TYPES": (
        "Number of distinct asset types alerted on deviates significantly from the peer median."
    ),
}
DEFAULT_RULE_DESCRIPTION: str = "Deviates significantly from the peer baseline."


@router.get("/risk-scores", response_model=list[RiskScoreSummary])
def get_risk_scores(db: Session = Depends(get_db)) -> list[dict]:
    """List every entity ranked by risk_score descending, for the dashboard."""
    rows = compute_risk_scores(db)
    if not rows:
        return []

    anomaly_results = compute_anomaly(db)

    return [
        {
            "entity_name": row["entity_name"],
            "risk_score": row["risk_score"],
            "risk_band": row["risk_band"],
            "alert_count": _alert_count(row["entity_name"], anomaly_results),
            "primary_driver": row["primary_driver"],
            "findings_summary": _findings_summary(row),
        }
        for row in rows
    ]


@router.get("/entities/{entity_name}", response_model=EntityDrillDown)
def get_entity_detail(entity_name: str, db: Session = Depends(get_db)) -> dict:
    """Drill-down detail for one entity: component scores, findings, and peer metrics.

    Matching is case-insensitive; FastAPI already URL-decodes the path
    parameter, so names containing spaces work whether passed raw or
    percent-encoded (e.g. "Indus%20Financial%20Services").
    """
    execution_gap_results = compute_execution_gap(db)
    negative_space_results = compute_negative_space(db)
    anomaly_results = compute_anomaly(db)

    canonical_name = _resolve_entity_name(entity_name, execution_gap_results)
    if canonical_name is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_name}' not found")

    risk_rows = compute_risk_scores(db)
    risk_row = next(row for row in risk_rows if row["entity_name"] == canonical_name)

    eg = execution_gap_results[canonical_name]
    ns = negative_space_results[canonical_name]
    an = anomaly_results[canonical_name]

    return {
        "entity_name": canonical_name,
        "risk_score": risk_row["risk_score"],
        "risk_band": risk_row["risk_band"],
        "alert_count": int(an["metrics"]["alert_count"]),
        "component_scores": {
            "execution_gap": eg["score"],
            "negative_space": ns["score"],
            "anomaly": an["score"],
        },
        "findings": _build_findings(eg, ns, an),
        "peer_metrics": _peer_metrics(canonical_name, anomaly_results),
    }


def _resolve_entity_name(requested: str, entity_results: dict[str, dict]) -> str | None:
    """Case-insensitive lookup of the canonical entity name, or None if not found."""
    normalized = requested.strip().lower()
    for name in entity_results:
        if name.lower() == normalized:
            return name
    return None


def _alert_count(entity_name: str, anomaly_results: dict[str, dict]) -> int:
    """Alert count for an entity, pulled from anomaly.py's metrics rather than recomputed."""
    metrics = anomaly_results.get(entity_name, {}).get("metrics", {})
    return int(metrics.get("alert_count", 0))


def _findings_summary(row: dict) -> list[str]:
    """Human-readable names of detectors that meaningfully fired for this entity.

    "Meaningfully fired" means the raw score is at or above
    FINDING_SUMMARY_THRESHOLD, not merely non-zero. Returns an empty list if
    nothing cleared the bar — the frontend renders that as "no significant
    findings" rather than an empty-but-present badge row.
    """
    return [
        display_name
        for key, display_name in DETECTOR_DISPLAY_NAMES.items()
        if row[f"{key}_score"] >= FINDING_SUMMARY_THRESHOLD
    ]


def _parse_rule(detector: str, detail: str) -> str:
    """Extract the short rule/feature name from an evidence item's detail string.

    execution_gap formats detail as "<RULE> — <alert_id>"; negative_space as
    "<TYPE>: <description>"; anomaly has no named rule, so the deviant feature
    name itself (e.g. "avg_closure_seconds = 45 (...)") is used instead.
    """
    if detector == "anomaly":
        return detail.split(" = ", 1)[0].strip().upper()
    separator = " — " if " — " in detail else ": "
    return detail.split(separator, 1)[0].strip()


def _build_findings(execution_gap: dict, negative_space: dict, anomaly: dict) -> list[dict]:
    """Group each detector's evidence by rule/feature into the drill-down findings list.

    Skips a detector entirely when its raw score is below
    FINDING_SUMMARY_THRESHOLD — the same gate applied to findings_summary on
    the dashboard, so a low-signal detector doesn't pad the evidence view
    with rules that didn't meaningfully fire.
    """
    findings: list[dict] = []
    for detector, result in (
        ("execution_gap", execution_gap),
        ("negative_space", negative_space),
        ("anomaly", anomaly),
    ):
        if result["score"] < FINDING_SUMMARY_THRESHOLD:
            continue

        grouped: dict[str, list[dict]] = {}
        for item in result["evidence"]:
            rule = _parse_rule(detector, item["detail"])
            grouped.setdefault(rule, []).append(item)

        for rule, items in grouped.items():
            findings.append(
                {
                    "rule": rule,
                    "detector": detector,
                    "description": RULE_DESCRIPTIONS.get(rule, DEFAULT_RULE_DESCRIPTION),
                    "evidence_count": len(items),
                    "evidence": [
                        {"detail": item["detail"], "reason": item["reason"]}
                        for item in items[:MAX_FINDING_EVIDENCE]
                    ],
                }
            )
    return findings


def _peer_metrics(entity_name: str, anomaly_results: dict[str, dict]) -> dict[str, dict]:
    """Peer median (excluding self) for each displayed metric, pulled from anomaly.py's metrics.

    Uses the plain median across peers, consistent with the median/MAD
    convention used throughout the detectors (see project.md's "Statistical
    conventions").
    """
    result: dict[str, dict] = {}
    for field in PEER_METRIC_FIELDS:
        entity_value = anomaly_results[entity_name]["metrics"][field]
        peer_values = [
            r["metrics"][field] for name, r in anomaly_results.items() if name != entity_name
        ]
        peer_median = statistics.median(peer_values) if peer_values else 0.0
        result[field] = {
            "entity": int(entity_value) if field == "alert_count" else entity_value,
            "peer_median": peer_median,
        }
    return result
