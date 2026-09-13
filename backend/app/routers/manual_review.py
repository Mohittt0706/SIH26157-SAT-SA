"""Blind manual review workflow — validates VEIL against independent human judgement.

The whole point of this workflow is that a supervisor forms their own
verdict from raw evidence *before* ever seeing what VEIL concluded. Two
endpoints therefore sit on opposite sides of a hard line:

  - GET /manual-review/{entity_name}/evidence is the blind dossier. It must
    never return risk_score, risk_band, primary_driver, component scores,
    any detector or rule name, detector-produced findings/evidence, a
    priority_score, or any peer-relative comparison — every one of those is
    a VEIL conclusion, and leaking any of them into this endpoint would let
    the reviewer's "independent" judgement be quietly anchored on VEIL's
    own answer, defeating the comparison this workflow exists to produce.
  - GET /manual-review/{entity_name}/comparison is the *only* place in this
    module that reads VEIL's output (via compute_risk_scores), and only
    after at least one review already exists — comparison, by definition,
    comes after the blind judgement was formed and recorded, never before.

This module never writes to the alerts table, never calls a detector's
compute_* function except compute_risk_scores (read-only, and only from the
comparison/metrics endpoints), and never touches sample_priority.py. The
ManualReview table is fully separate from the analytics path — nothing here
changes a single risk_score, risk_band, or detector output.
"""

from __future__ import annotations

import statistics

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.risk_score import compute_risk_scores
from app.database import get_db
from app.models import Alert, ManualReview
from app.schemas import (
    EntityBlindEvidence,
    ManualReviewComparison,
    ManualReviewCreate,
    ManualReviewMetrics,
    ManualReviewOut,
)

router = APIRouter()

NOT_RECORDED_KEY: str = "unknown"
"""Bucket label for a severity/asset_type distribution entry when the stored
value is blank — should not occur in practice given ingestion's validation,
but the aggregate must not silently drop the alert either."""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _resolve_entity_name_from_alerts(requested: str, db: Session) -> str | None:
    """Case-insensitive lookup of an entity's canonical name from the alerts table.

    Deliberately does not call any detector — the blind evidence endpoint
    must not run compute_execution_gap/compute_anomaly/etc. just to resolve
    a name, since that would put detector output one accidental field-leak
    away from a "blind" response.
    """
    normalized = requested.strip().lower()
    names = db.execute(select(Alert.entity_name).distinct()).scalars().all()
    for name in names:
        if name.strip().lower() == normalized:
            return name
    return None


def _reviews_for_entity(entity_name: str, db: Session) -> list[ManualReview]:
    """All ManualReview rows for *entity_name*, case-insensitive, newest first."""
    normalized = entity_name.strip().lower()
    reviews = db.execute(select(ManualReview)).scalars().all()
    matched = [r for r in reviews if r.entity_name.strip().lower() == normalized]
    matched.sort(key=lambda r: r.created_at, reverse=True)
    return matched


def _veil_signal(risk_band: str) -> bool:
    """Single VEIL-derived boolean used for both `_concern` and `_prioritized`.

    Per project.md, risk_band already *is* "an investigative priority
    ranking" — anything above "low" is VEIL saying this entity is worth a
    human look. Both comparison dimensions ("is there a concern" and "should
    this be prioritized") are read off that same existing signal rather than
    inventing two new, independent VEIL conclusions; this reads risk_band, it
    does not recompute or reinterpret it.
    """
    return risk_band != "low"


# ---------------------------------------------------------------------------
# 5.2 — the blind dossier
# ---------------------------------------------------------------------------

@router.get("/manual-review/{entity_name}/evidence", response_model=EntityBlindEvidence)
def get_blind_evidence(entity_name: str, db: Session = Depends(get_db)) -> dict:
    """Raw operational evidence for one entity — no VEIL conclusion included.

    See the module docstring for the exact list of fields this must never
    return. Every aggregate here is computed from this entity's own alerts
    only; there is no peer comparison of any kind.
    """
    canonical = _resolve_entity_name_from_alerts(entity_name, db)
    if canonical is None:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_name}' not found")

    alerts = (
        db.execute(
            select(Alert)
            .where(Alert.entity_name == canonical)
            .order_by(Alert.created_time.asc())
        )
        .scalars()
        .all()
    )

    alert_rows = [
        {
            "alert_id": a.alert_id,
            "severity": a.severity,
            "asset_type": a.asset_type,
            "created_time": a.created_time,
            "closed_time": a.closed_time,
            "closure_duration_seconds": a.closure_seconds,
            "escalated": a.escalated,
            "investigation_notes": a.investigation_notes,
        }
        for a in alerts
    ]

    total = len(alerts)
    closed = [a for a in alerts if a.closed_time is not None]
    closure_values = [a.closure_seconds for a in closed if a.closure_seconds is not None]
    avg_closure = statistics.mean(closure_values) if closure_values else None
    escalated_count = sum(1 for a in alerts if a.escalated)
    escalated_rate = escalated_count / total if total else 0.0
    note_lengths = [len(a.investigation_notes) if a.investigation_notes else 0 for a in alerts]
    avg_note_length = statistics.mean(note_lengths) if note_lengths else 0.0

    severity_distribution: dict[str, int] = {}
    asset_type_distribution: dict[str, int] = {}
    for a in alerts:
        sev_key = a.severity or NOT_RECORDED_KEY
        severity_distribution[sev_key] = severity_distribution.get(sev_key, 0) + 1
        asset_key = a.asset_type or NOT_RECORDED_KEY
        asset_type_distribution[asset_key] = asset_type_distribution.get(asset_key, 0) + 1

    return {
        "entity_name": canonical,
        "alerts": alert_rows,
        "aggregates": {
            "total_alerts": total,
            "open_alerts": total - len(closed),
            "closed_alerts": len(closed),
            "avg_closure_seconds": avg_closure,
            "escalated_count": escalated_count,
            "escalated_rate": escalated_rate,
            "avg_investigation_note_length": avg_note_length,
            "severity_distribution": severity_distribution,
            "asset_type_distribution": asset_type_distribution,
        },
    }


# ---------------------------------------------------------------------------
# 5.3 — submit
# ---------------------------------------------------------------------------

@router.post("/manual-review", response_model=ManualReviewOut, status_code=201)
def submit_manual_review(payload: ManualReviewCreate, db: Session = Depends(get_db)) -> ManualReview:
    """Persist a new manual review. Always appends — never updates a prior row.

    Enum fields (concern_type, manual_priority) are validated by Pydantic
    before this function ever runs: an invalid value is rejected with a 422
    automatically, since ManualReviewCreate types them as the strict
    ConcernType/ManualPriority enums rather than plain strings.

    Does not require the entity to currently exist in the alerts table —
    the manual_reviews table is intentionally decoupled from whatever
    dataset happens to be loaded (see the ManualReview model docstring), so
    a review submitted for an entity from an earlier upload still persists
    correctly even after a later upload replaces the alerts table.
    """
    review = ManualReview(
        entity_name=payload.entity_name.strip(),
        reviewer_id=payload.reviewer_id,
        supervisory_concern=payload.supervisory_concern,
        concern_type=payload.concern_type,
        manual_priority=payload.manual_priority,
        manual_review_recommended=payload.manual_review_recommended,
        evidence_sufficient=payload.evidence_sufficient,
        rationale=payload.rationale,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


# ---------------------------------------------------------------------------
# 5.6 — aggregate metrics (registered before the {entity_name} routes below
# so "/manual-review/metrics" is not swallowed by "/manual-review/{entity_name}")
# ---------------------------------------------------------------------------

@router.get("/manual-review/metrics", response_model=ManualReviewMetrics)
def get_manual_review_metrics(db: Session = Depends(get_db)) -> dict:
    """Aggregate manual-vs-VEIL agreement across every submitted review.

    Counts every review row, not one-per-entity — a re-reviewed entity
    contributes one data point per submission. A review whose entity is no
    longer present in the current dataset's VEIL results is excluded from
    every rate (counted in total_reviews, not in comparable_reviews or any
    agreement count) rather than guessed at. Rates are null, not 0.0, when
    there is nothing to measure them from.
    """
    reviews = db.execute(select(ManualReview)).scalars().all()
    total_reviews = len(reviews)

    if total_reviews == 0:
        return {
            "total_reviews": 0,
            "comparable_reviews": 0,
            "concern_agreement_count": 0,
            "concern_agreement_rate": None,
            "priority_agreement_count": 0,
            "priority_agreement_rate": None,
            "recommendation_agreement_count": 0,
            "recommendation_agreement_rate": None,
            "overall_agreement_count": 0,
            "overall_agreement_rate": None,
        }

    risk_rows = compute_risk_scores(db)
    risk_by_name = {row["entity_name"].strip().lower(): row for row in risk_rows}

    comparable = 0
    concern_agree = 0
    priority_agree = 0
    recommendation_agree = 0
    overall_agree = 0

    for review in reviews:
        risk_row = risk_by_name.get(review.entity_name.strip().lower())
        if risk_row is None:
            continue
        comparable += 1

        veil_signal = _veil_signal(risk_row["risk_band"])
        c_agree = review.supervisory_concern == veil_signal
        p_agree = review.manual_priority.value == risk_row["risk_band"]
        r_agree = review.manual_review_recommended == veil_signal

        concern_agree += int(c_agree)
        priority_agree += int(p_agree)
        recommendation_agree += int(r_agree)
        overall_agree += int(c_agree and p_agree and r_agree)

    def _rate(count: int) -> float | None:
        return round(count / comparable, 4) if comparable else None

    return {
        "total_reviews": total_reviews,
        "comparable_reviews": comparable,
        "concern_agreement_count": concern_agree,
        "concern_agreement_rate": _rate(concern_agree),
        "priority_agreement_count": priority_agree,
        "priority_agreement_rate": _rate(priority_agree),
        "recommendation_agreement_count": recommendation_agree,
        "recommendation_agreement_rate": _rate(recommendation_agree),
        "overall_agreement_count": overall_agree,
        "overall_agreement_rate": _rate(overall_agree),
    }


# ---------------------------------------------------------------------------
# 5.5 — comparison (only meaningful once a review exists)
# ---------------------------------------------------------------------------

@router.get("/manual-review/{entity_name}/comparison", response_model=ManualReviewComparison)
def get_manual_review_comparison(entity_name: str, db: Session = Depends(get_db)) -> dict:
    """Manual verdict vs VEIL's conclusion for one entity's most recent review.

    Returns an explicit `available: false` empty state — never VEIL's raw
    results — when no review has been submitted yet, or when a review
    exists but this entity isn't in the currently loaded dataset.
    """
    matched = _reviews_for_entity(entity_name, db)
    if not matched:
        return {
            "available": False,
            "entity_name": entity_name.strip(),
            "reason": "No manual review has been submitted for this entity yet.",
        }

    latest = matched[0]

    risk_rows = compute_risk_scores(db)
    normalized = entity_name.strip().lower()
    risk_row = next(
        (row for row in risk_rows if row["entity_name"].strip().lower() == normalized), None
    )
    if risk_row is None:
        return {
            "available": False,
            "entity_name": latest.entity_name,
            "reason": (
                "This entity is not present in the currently loaded dataset, "
                "so there is no VEIL result to compare the existing review against."
            ),
        }

    veil_risk_band = risk_row["risk_band"]
    veil_signal = _veil_signal(veil_risk_band)

    concern_agrees = latest.supervisory_concern == veil_signal
    priority_agrees = latest.manual_priority.value == veil_risk_band
    recommendation_agrees = latest.manual_review_recommended == veil_signal

    return {
        "available": True,
        "entity_name": risk_row["entity_name"],
        "reason": None,
        "review_id": latest.id,
        "review_created_at": latest.created_at,
        "manual_concern": latest.supervisory_concern,
        "veil_concern": veil_signal,
        "concern_agrees": concern_agrees,
        "manual_priority": latest.manual_priority,
        "veil_risk_band": veil_risk_band,
        "priority_agrees": priority_agrees,
        "manual_review_recommended": latest.manual_review_recommended,
        "veil_prioritized": veil_signal,
        "recommendation_agrees": recommendation_agrees,
        "overall_agreement": concern_agrees and priority_agrees and recommendation_agrees,
    }


# ---------------------------------------------------------------------------
# 5.4 — history (registered last: the most generic "/manual-review/{entity_name}"
# shape, so it must not shadow /metrics, /evidence, or /comparison above)
# ---------------------------------------------------------------------------

@router.get("/manual-review/{entity_name}", response_model=list[ManualReviewOut])
def list_manual_reviews(entity_name: str, db: Session = Depends(get_db)) -> list[ManualReview]:
    """All manual reviews for one entity, newest first. Empty list if none."""
    return _reviews_for_entity(entity_name, db)
