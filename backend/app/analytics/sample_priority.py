"""Sample Priority — ranks individual alerts for manual supervisory review.

Addresses problem-statement requirement #10: the existing detectors and
risk_score.py rank *entities*, telling a supervisor which company to look at
first, but not which specific alert within that company to open first. This
module produces a flat, cross-entity ranked list of individual alerts.

Read-only: it calls compute_execution_gap(db) and compute_risk_scores(db)
and reads Alert rows directly, but does not modify any detector, constant,
or score, and does not write to the database.

Eligibility — only alerts a detector actually cited as evidence:
Of the three detectors, only execution_gap.py's evidence cites specific
alert_ids at all: its contract-dict evidence details are formatted as
``"<RULE> — <alert_id>"`` (see execution_gap._to_contract_dict), one entry
per concrete alert behind a FAST_CLOSURE / NO_ESCALATION / TEMPLATE_NOTES
hit. negative_space.py's evidence is entity-level (LOW_ALERT_VOLUME,
MISSING_EXPECTED_SEVERITY findings describe the whole entity, not one
alert), and anomaly.py's evidence describes deviant *features*
(avg_closure_seconds, escalation_rate, ...), not alerts. Neither cites an
alert_id, so neither can nominate a candidate here — inventing a priority
for an alert no rule actually flagged would misrepresent what the detectors
found. This module's candidate pool is therefore exactly the alerts named in
execution_gap's evidence, deduplicated by (entity_name, alert_id) since
alert_id is only unique within one entity's export (see Alert in models.py).

Scoring: a fixed weighted sum of three named, independently-tunable signals
(see the WEIGHT_* and *_SCORE constants below) — how many distinct rules
cited the alert, how risky its entity is overall, and its own severity —
scaled to 0-100.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.execution_gap import compute_execution_gap
from app.analytics.risk_score import compute_risk_scores
from app.models import Alert

# ---------------------------------------------------------------------------
# Tunable weights and scores
# ---------------------------------------------------------------------------

RULE_COUNT_WEIGHT: float = 0.45
"""Weight of the "cited by more than one rule" signal in the combined score.
The largest of the three weights — an alert independently flagged by
multiple execution-gap rules (e.g. closed implausibly fast AND never
escalated) is corroborated evidence, the single strongest indicator that a
specific alert (not just its entity) deserves a human look."""

ENTITY_RISK_WEIGHT: float = 0.35
"""Weight of the entity's overall risk_score (0-100, rescaled to 0-1) in the
combined score — an alert from a high-risk entity is more likely to be part
of a genuine pattern than the same rule firing on an otherwise-clean entity."""

SEVERITY_WEIGHT: float = 0.20
"""Weight of the alert's own severity in the combined score. Smallest of the
three — severity alone (with no rule corroboration or entity-level risk)
is the weakest signal of the three, but a critical/high alert should still
rank above an otherwise-identical medium/low one."""
# RULE_COUNT_WEIGHT + ENTITY_RISK_WEIGHT + SEVERITY_WEIGHT must sum to 1.0.

MAX_TRIGGERED_RULES_FOR_SIGNAL: int = 3
"""Number of distinct execution_gap rules (FAST_CLOSURE, NO_ESCALATION,
TEMPLATE_NOTES) an alert can be cited by. Normalizes the rule-count signal to
0.0-1.0: an alert cited by all three rules maxes out the signal, one cited by
a single rule gets 1/3 of it, matching the graded-ramp convention used
elsewhere in this package rather than a flat "flagged at all" binary."""

SEVERITY_SCORE: dict[str, float] = {
    "critical": 1.00,
    "high": 0.75,
    "medium": 0.40,
    "low": 0.15,
}
"""Per-severity component of the combined score, 0.0-1.0. Deliberately not
linear (critical/high are close together and well above medium/low) so
"critical and high rank above medium and low" reads as a clear split, not a
smooth ramp that could put a borderline high alert below a low one."""

DEFAULT_SEVERITY_SCORE: float = 0.15
"""Severity component used for a blank/unrecognized severity value — the
same as "low", since an unlabeled alert should not outrank a labeled low one."""

RULE_SEPARATOR: str = " — "
"""Matches execution_gap._to_contract_dict's evidence detail format exactly
(``f"{rule} — {item.alert_id}"``) — this module does not reimplement that
detector, only parses its published contract-shaped output."""


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _parse_execution_gap_evidence(
    execution_gap_results: dict[str, dict],
) -> dict[tuple[str, str], list[str]]:
    """Extract (entity_name, alert_id) -> distinct triggered rule names.

    Parses execution_gap.py's published contract-dict evidence
    (``{"detail": "<RULE> — <alert_id>", "reason": str}``) rather than
    touching that detector's internals, per the read-only/no-detector-
    modification constraint. Preserves first-seen order per alert so
    ``triggered_rules`` reads in the order execution_gap discovered them.
    """
    triggered_rules: dict[tuple[str, str], list[str]] = defaultdict(list)

    for entity_name, result in execution_gap_results.items():
        for item in result.get("evidence", []):
            detail = item.get("detail", "")
            if RULE_SEPARATOR not in detail:
                continue  # not an alert-citing evidence item; nothing to key on
            rule, alert_id = detail.split(RULE_SEPARATOR, 1)
            rule = rule.strip()
            alert_id = alert_id.strip()
            key = (entity_name, alert_id)
            if rule not in triggered_rules[key]:
                triggered_rules[key].append(rule)

    return triggered_rules


def _severity_component(severity: str | None) -> float:
    """Map a stored severity string to its SEVERITY_SCORE component."""
    key = (severity or "").strip().lower()
    return SEVERITY_SCORE.get(key, DEFAULT_SEVERITY_SCORE)


def _build_reason(
    triggered_rules: list[str],
    severity: str | None,
    entity_name: str,
    entity_risk_score: float,
) -> str:
    """Compose the one-sentence, plain-language reason for this alert's priority."""
    severity_label = (severity or "unlabeled").strip().lower()
    if len(triggered_rules) == 1:
        rules_clause = f"the {triggered_rules[0]} rule"
    else:
        rules_clause = f"{len(triggered_rules)} rules ({', '.join(triggered_rules)})"

    return (
        f"Cited as evidence by {rules_clause}, on a {severity_label} severity "
        f"alert at {entity_name}, whose overall risk score is {entity_risk_score:.1f}."
    )


def compute_sample_priority(db: Session, limit: int = 25) -> list[dict]:
    """Rank individual alerts across all entities by manual-review priority.

    Builds the candidate pool from every alert execution_gap.py actually
    cited as evidence (see the module docstring for why negative_space.py and
    anomaly.py contribute none), scores each with a weighted combination of
    how many distinct rules cited it, its entity's overall risk_score, and
    its own severity, and returns the top *limit* by that score.

    Parameters
    ----------
    db:
        An open SQLAlchemy session pointing at the alerts table.
    limit:
        Maximum number of alerts to return (default 25).

    Returns
    -------
    list[dict]
        Up to *limit* dicts, sorted by ``priority_score`` descending (ties
        broken by entity_risk_score descending, then alert_id descending —
        the sort key is a single tuple with ``reverse=True``, which orders
        every element of the tuple descending, not just the first — for
        a deterministic order), each shaped:
        ``{"alert_id": str, "entity_name": str, "entity_risk_score": float,
        "severity": str, "created_time": datetime, "priority_score": float,
        "triggered_rules": list[str], "reason": str}``.
        Empty if no detector cited any alert as evidence.
    """
    alerts = db.execute(select(Alert)).scalars().all()
    alerts_by_key: dict[tuple[str, str], Alert] = {
        (alert.entity_name, alert.alert_id): alert for alert in alerts
    }

    execution_gap_results = compute_execution_gap(db)
    triggered_rules_by_key = _parse_execution_gap_evidence(execution_gap_results)

    risk_rows = compute_risk_scores(db)
    entity_risk_scores: dict[str, float] = {
        row["entity_name"]: row["risk_score"] for row in risk_rows
    }

    candidates: list[dict] = []
    for (entity_name, alert_id), rules in triggered_rules_by_key.items():
        alert = alerts_by_key.get((entity_name, alert_id))
        if alert is None:
            # Cited by a detector run moments ago but no longer in the table
            # (e.g. a concurrent re-upload) — skip rather than fabricate.
            continue

        entity_risk_score = entity_risk_scores.get(entity_name, 0.0)

        rule_count_signal = min(len(rules), MAX_TRIGGERED_RULES_FOR_SIGNAL) / MAX_TRIGGERED_RULES_FOR_SIGNAL
        entity_risk_signal = entity_risk_score / 100.0
        severity_signal = _severity_component(alert.severity)

        priority_raw = (
            RULE_COUNT_WEIGHT * rule_count_signal
            + ENTITY_RISK_WEIGHT * entity_risk_signal
            + SEVERITY_WEIGHT * severity_signal
        )
        priority_score = round(max(0.0, min(1.0, priority_raw)) * 100, 1)

        candidates.append(
            {
                "alert_id": alert.alert_id,
                "entity_name": entity_name,
                "entity_risk_score": entity_risk_score,
                "severity": alert.severity,
                "created_time": alert.created_time,
                "priority_score": priority_score,
                "triggered_rules": rules,
                "reason": _build_reason(rules, alert.severity, entity_name, entity_risk_score),
            }
        )

    candidates.sort(
        key=lambda c: (c["priority_score"], c["entity_risk_score"], c["alert_id"]),
        reverse=True,
    )
    return candidates[:limit]


# ---------------------------------------------------------------------------
# CLI standalone runner (reads from SQLite DB)
# ---------------------------------------------------------------------------

def _run_cli() -> None:
    """Standalone CLI entry-point for development and demo."""
    import argparse
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="SAT-SA Sample Priority ranker (CLI)")
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to SQLite DB file. If omitted, tries backend/data/satsa.db.",
    )
    parser.add_argument("--limit", type=int, default=25, help="Number of alerts to show.")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else Path(__file__).resolve().parent.parent.parent / "data" / "satsa.db"
    if not db_path.exists():
        print(
            f"Error: Database not found at {db_path}\n"
            "  Upload data via the API first, or pass --db <path>.",
            file=sys.stderr,
        )
        sys.exit(1)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        results = compute_sample_priority(db, limit=args.limit)
    finally:
        db.close()

    _print_results(results)


def _print_results(results: list[dict]) -> None:
    """Pretty-print results to stdout for CLI / demo use."""
    print("\n===== SAT-SA SAMPLE PRIORITY RESULTS =====\n")
    if not results:
        print("No alerts were cited as evidence by any detector.")
        return

    for rank, item in enumerate(results, start=1):
        created: datetime = item["created_time"]
        print(
            f"{rank:>2}. [{item['priority_score']:>5.1f}] {item['alert_id']} "
            f"({item['entity_name']}, {item['severity']}, {created:%Y-%m-%d %H:%M})"
        )
        print(f"     rules: {', '.join(item['triggered_rules'])}")
        print(f"     {item['reason']}")
    print()


if __name__ == "__main__":
    _run_cli()
