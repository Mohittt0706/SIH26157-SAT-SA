"""Execution Gap detector — rule-based signals that SOC work looks done but isn't.

Three rules, computed per entity:
  1. FAST_CLOSURE    — critical/high alerts closed implausibly fast.
  2. NO_ESCALATION   — critical alerts never escalated.
  3. TEMPLATE_NOTES  — investigation notes that are empty, too short, or copy-pasted
                        at a rate meaningfully above the peer baseline.

Each rule contributes a rate (0.0-1.0) plus up to MAX_EVIDENCE_EXAMPLES concrete
alert_ids with a human-readable reason, so a jury member can look the alert up
in the raw CSV and see exactly why it was flagged.
"""

import statistics
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert

# --- Tunable thresholds -----------------------------------------------------

FAST_CLOSURE_THRESHOLD_SECONDS: int = 300
MIN_NOTE_LENGTH: int = 20
MAX_EVIDENCE_EXAMPLES: int = 5

FAST_CLOSURE_SEVERITIES: set[str] = {"critical", "high"}
NO_ESCALATION_SEVERITIES: set[str] = {"critical"}

MIN_DUPLICATE_MULTIPLICITY: int = 5
"""A note must repeat verbatim at least this many times before it counts as
template evidence at all — a note repeated twice is normal, 15+ times is not."""

TEMPLATE_DUPLICATE_Z_THRESHOLD: float = 1.0
"""An entity's rate of highly-duplicated notes must be at least this many
modified z-scores above the peer median before duplication counts toward the
TEMPLATE_NOTES rule. Keeps the rule from firing on every entity just because
some copy-paste is normal SOC behaviour."""

MAD_ZSCORE_SCALE: float = 0.6745
"""Scale factor converting MAD to a std-equivalent z-score (75th percentile
of the standard normal). Mirrors the constant of the same name in anomaly.py."""

# Rule weights for the combined score; must sum to 1.0.
FAST_CLOSURE_WEIGHT: float = 0.4
NO_ESCALATION_WEIGHT: float = 0.3
TEMPLATE_NOTES_WEIGHT: float = 0.3


@dataclass
class RuleEvidence:
    """One concrete alert supporting a triggered rule."""

    alert_id: str
    reason: str


@dataclass
class ExecutionGapResult:
    """Execution Gap outcome for a single entity."""

    entity_name: str
    score: float
    fast_closure_rate: float
    no_escalation_rate: float
    template_notes_rate: float
    evidence: dict[str, list[RuleEvidence]] = field(default_factory=dict)


def compute_execution_gap(db: Session) -> dict[str, dict]:
    """Compute Execution Gap results for every entity present in the alerts table.

    Returns the shared detector contract shape documented in project.md:
    ``{"score": float, "metrics": dict, "evidence": list[{"detail": str, "reason": str}]}``.
    """
    alerts = db.execute(select(Alert)).scalars().all()

    by_entity: dict[str, list[Alert]] = {}
    for alert in alerts:
        by_entity.setdefault(alert.entity_name, []).append(alert)

    # TEMPLATE_NOTES needs every entity's duplication rate up front so each
    # entity can be compared against its peers.
    entity_duplicate_rates: dict[str, float] = {
        entity_name: _duplicate_rate(entity_alerts)
        for entity_name, entity_alerts in by_entity.items()
    }

    return {
        entity_name: _to_contract_dict(
            _compute_for_entity(entity_name, entity_alerts, entity_duplicate_rates)
        )
        for entity_name, entity_alerts in by_entity.items()
    }


def _to_contract_dict(result: ExecutionGapResult) -> dict:
    """Serialize an ExecutionGapResult into the shared detector contract shape."""
    evidence = [
        {"detail": f"{rule} — {item.alert_id}", "reason": item.reason}
        for rule, items in result.evidence.items()
        for item in items
    ]
    return {
        "score": result.score,
        "metrics": {
            "fast_closure_rate": result.fast_closure_rate,
            "no_escalation_rate": result.no_escalation_rate,
            "template_notes_rate": result.template_notes_rate,
        },
        "evidence": evidence,
    }


def _compute_for_entity(
    entity_name: str,
    alerts: list[Alert],
    entity_duplicate_rates: dict[str, float],
) -> ExecutionGapResult:
    """Compute the three rules and the combined score for one entity's alerts."""
    total = len(alerts)

    fast_closure_rate, fast_closure_evidence = _fast_closure_rule(alerts)
    no_escalation_rate, no_escalation_evidence = _no_escalation_rule(alerts)
    template_notes_rate, template_notes_evidence = _template_notes_rule(
        alerts, total, entity_name, entity_duplicate_rates
    )

    score = min(
        1.0,
        FAST_CLOSURE_WEIGHT * fast_closure_rate
        + NO_ESCALATION_WEIGHT * no_escalation_rate
        + TEMPLATE_NOTES_WEIGHT * template_notes_rate,
    )

    return ExecutionGapResult(
        entity_name=entity_name,
        score=score,
        fast_closure_rate=fast_closure_rate,
        no_escalation_rate=no_escalation_rate,
        template_notes_rate=template_notes_rate,
        evidence={
            "FAST_CLOSURE": fast_closure_evidence,
            "NO_ESCALATION": no_escalation_evidence,
            "TEMPLATE_NOTES": template_notes_evidence,
        },
    )


def _fast_closure_rule(alerts: list[Alert]) -> tuple[float, list[RuleEvidence]]:
    """Rate of critical/high alerts closed under FAST_CLOSURE_THRESHOLD_SECONDS."""
    candidates = [
        a for a in alerts if a.severity in FAST_CLOSURE_SEVERITIES and a.closed_time is not None
    ]
    hits = [
        a
        for a in candidates
        if a.closure_seconds is not None and a.closure_seconds < FAST_CLOSURE_THRESHOLD_SECONDS
    ]
    rate = len(hits) / len(candidates) if candidates else 0.0

    evidence = [
        RuleEvidence(
            alert_id=a.alert_id,
            reason=(
                f"{a.severity} severity alert closed in {a.closure_seconds:.0f}s "
                f"(< {FAST_CLOSURE_THRESHOLD_SECONDS}s threshold)"
            ),
        )
        for a in hits[:MAX_EVIDENCE_EXAMPLES]
    ]
    return rate, evidence


def _no_escalation_rule(alerts: list[Alert]) -> tuple[float, list[RuleEvidence]]:
    """Rate of critical alerts left un-escalated."""
    candidates = [a for a in alerts if a.severity in NO_ESCALATION_SEVERITIES]
    hits = [a for a in candidates if not a.escalated]
    rate = len(hits) / len(candidates) if candidates else 0.0

    evidence = [
        RuleEvidence(
            alert_id=a.alert_id,
            reason=f"{a.severity} severity alert was never escalated (escalated=False)",
        )
        for a in hits[:MAX_EVIDENCE_EXAMPLES]
    ]
    return rate, evidence


def _highly_duplicated_notes(alerts: list[Alert]) -> tuple[Counter[str], set[str]]:
    """Note-text counts and the subset repeated >= MIN_DUPLICATE_MULTIPLICITY times."""
    note_counts = Counter(a.investigation_notes for a in alerts if a.investigation_notes)
    highly_duplicated = {
        note for note, count in note_counts.items() if count >= MIN_DUPLICATE_MULTIPLICITY
    }
    return note_counts, highly_duplicated


def _duplicate_rate(alerts: list[Alert]) -> float:
    """Fraction of an entity's alerts whose note repeats >= MIN_DUPLICATE_MULTIPLICITY times."""
    total = len(alerts)
    if not total:
        return 0.0
    _, highly_duplicated = _highly_duplicated_notes(alerts)
    hits = sum(1 for a in alerts if a.investigation_notes in highly_duplicated)
    return hits / total


def _peer_median_mad(values_by_entity: dict[str, float], current_entity: str) -> tuple[float, float]:
    """Median and MAD of *values_by_entity* across peers, excluding current_entity.

    Same median/MAD-based peer-baseline convention used for feature attribution
    in anomaly.py (see MAD_ZSCORE_SCALE there), adapted to this module's
    name-keyed per-entity dicts — the same "exclude self, compare against the
    rest" shape as negative_space.py's build_peer_baseline, but robust to a
    single outlier the way mean/stdev is not.
    """
    peer_values = [v for name, v in values_by_entity.items() if name != current_entity]
    if not peer_values:
        return 0.0, 0.0

    median = statistics.median(peer_values)
    if len(peer_values) < 2:
        return median, 0.0

    mad = statistics.median(abs(v - median) for v in peer_values)
    return median, mad


def _modified_z_score(value: float, peer_median: float, peer_mad: float) -> float:
    """Modified z-score of *value* against a peer median/MAD, with a zero-MAD fallback."""
    if peer_mad == 0.0:
        if value == peer_median:
            return 0.0
        return 1.0 if value > peer_median else -1.0
    return MAD_ZSCORE_SCALE * (value - peer_median) / peer_mad


def _template_notes_rule(
    alerts: list[Alert],
    total: int,
    entity_name: str,
    entity_duplicate_rates: dict[str, float],
) -> tuple[float, list[RuleEvidence]]:
    """Rate of alerts with empty, too-short, or peer-anomalously-duplicated notes.

    Empty and too-short notes are absolute per-alert checks. Duplication is
    relative: an entity's rate of highly-duplicated notes only counts toward
    this rule when it sits meaningfully above the peer median (see
    TEMPLATE_DUPLICATE_Z_THRESHOLD) — otherwise routine copy-paste on a couple
    of notes would flag every entity and the rule would discriminate nothing.
    """
    note_counts, highly_duplicated = _highly_duplicated_notes(alerts)

    entity_rate = entity_duplicate_rates.get(entity_name, 0.0)
    peer_median, peer_mad = _peer_median_mad(entity_duplicate_rates, entity_name)
    duplicate_z_score = _modified_z_score(entity_rate, peer_median, peer_mad)
    duplication_flagged = duplicate_z_score >= TEMPLATE_DUPLICATE_Z_THRESHOLD

    hit_count = 0
    evidence: list[RuleEvidence] = []
    for a in alerts:
        notes = a.investigation_notes
        if not notes:
            reason = "investigation_notes is empty"
        elif len(notes) < MIN_NOTE_LENGTH:
            reason = f"investigation_notes only {len(notes)} chars (< {MIN_NOTE_LENGTH} minimum)"
        elif duplication_flagged and notes in highly_duplicated:
            reason = (
                f"investigation_notes duplicated verbatim across {note_counts[notes]} alerts "
                f"for this entity — entity's duplication rate ({entity_rate:.0%}) is "
                f"{duplicate_z_score:.2f} modified z-scores above the peer median "
                f"({peer_median:.0%})"
            )
        else:
            continue

        hit_count += 1
        if len(evidence) < MAX_EVIDENCE_EXAMPLES:
            evidence.append(RuleEvidence(alert_id=a.alert_id, reason=reason))

    rate = hit_count / total if total else 0.0
    return rate, evidence
