"""Execution Gap detector — rule-based signals that SOC work looks done but isn't.

Three rules, computed per entity:
  1. FAST_CLOSURE    — critical/high alerts closed implausibly fast.
  2. NO_ESCALATION   — critical alerts never escalated.
  3. TEMPLATE_NOTES  — investigation notes that are empty, too short, or copy-pasted.

Each rule contributes a rate (0.0-1.0) plus up to MAX_EVIDENCE_EXAMPLES concrete
alert_ids with a human-readable reason, so a jury member can look the alert up
in the raw CSV and see exactly why it was flagged.
"""

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


def compute_execution_gap(db: Session) -> dict[str, ExecutionGapResult]:
    """Compute Execution Gap results for every entity present in the alerts table."""
    alerts = db.execute(select(Alert)).scalars().all()

    by_entity: dict[str, list[Alert]] = {}
    for alert in alerts:
        by_entity.setdefault(alert.entity_name, []).append(alert)

    return {
        entity_name: _compute_for_entity(entity_name, entity_alerts)
        for entity_name, entity_alerts in by_entity.items()
    }


def _compute_for_entity(entity_name: str, alerts: list[Alert]) -> ExecutionGapResult:
    """Compute the three rules and the combined score for one entity's alerts."""
    total = len(alerts)

    fast_closure_rate, fast_closure_evidence = _fast_closure_rule(alerts)
    no_escalation_rate, no_escalation_evidence = _no_escalation_rule(alerts)
    template_notes_rate, template_notes_evidence = _template_notes_rule(alerts, total)

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


def _template_notes_rule(alerts: list[Alert], total: int) -> tuple[float, list[RuleEvidence]]:
    """Rate of alerts with empty, too-short, or verbatim-duplicated investigation notes."""
    note_counts = Counter(a.investigation_notes for a in alerts if a.investigation_notes)
    duplicated_notes = {note for note, count in note_counts.items() if count > 1}

    hit_count = 0
    evidence: list[RuleEvidence] = []
    for a in alerts:
        notes = a.investigation_notes
        if not notes:
            reason = "investigation_notes is empty"
        elif len(notes) < MIN_NOTE_LENGTH:
            reason = f"investigation_notes only {len(notes)} chars (< {MIN_NOTE_LENGTH} minimum)"
        elif notes in duplicated_notes:
            reason = (
                f"investigation_notes duplicated verbatim across "
                f"{note_counts[notes]} alerts for this entity"
            )
        else:
            continue

        hit_count += 1
        if len(evidence) < MAX_EVIDENCE_EXAMPLES:
            evidence.append(RuleEvidence(alert_id=a.alert_id, reason=reason))

    rate = hit_count / total if total else 0.0
    return rate, evidence
