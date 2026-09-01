"""Negative Space detector — identifies expected security activity that is absent.

Compares each entity's alert profile against its peers to surface potential
supervisory signals where expected activity appears to be missing.

Three rules, computed per entity:
  1. LOW_ALERT_VOLUME        — total alert count significantly below peer baseline.
  2. MISSING_EXPECTED_SEVERITY — a severity category present across peers but absent here.
  3. ASSET_SILENCE           — (reserved) asset types with no alerts when peers have them.

The detector is transparent and rule-based. It does NOT conclude that an
organisation is insecure; it produces *potential negative-space signals*
that require human supervisory review.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert

# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------

LOW_VOLUME_Z_THRESHOLD: float = -1.0
"""Z-score at or below which low-alert-volume is flagged."""

MIN_PEERS_WITH_SEVERITY: int = 2
"""Minimum number of peer entities that must exhibit a severity before it
is considered 'expected' for the current entity."""

LOW_VOLUME_WEIGHT: float = 0.6
"""Weight of the low-volume signal in the combined negative-space score."""

MISSING_SEVERITY_WEIGHT: float = 0.4
"""Weight of the missing-severity signal in the combined negative-space score."""

# Rule types as string constants for evidence dictionaries.
RULE_LOW_ALERT_VOLUME: str = "LOW_ALERT_VOLUME"
RULE_MISSING_EXPECTED_SEVERITY: str = "MISSING_EXPECTED_SEVERITY"
RULE_ASSET_SILENCE: str = "ASSET_SILENCE"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    """A single evidence item supporting a triggered negative-space rule."""

    type: str
    detail: str
    reason: str


@dataclass
class NegativeSpaceResult:
    """Negative Space outcome for a single entity."""

    entity_name: str
    negative_space_score: float
    metrics: dict[str, float | int]
    evidence: list[Finding] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Peer baseline helper
# ---------------------------------------------------------------------------

def build_peer_baseline(
    entity_alert_counts: dict[str, int],
    current_entity: str,
) -> tuple[float, float]:
    """Compute mean and sample standard deviation of alert counts for *peers*.

    The *current_entity* is excluded from the calculation so that an entity
    is never compared against itself.

    Parameters
    ----------
    entity_alert_counts:
        Mapping of entity name → total alert count for every entity.
    current_entity:
        The entity whose peer baseline is being computed.

    Returns
    -------
    tuple[float, float]
        (peer_mean, peer_std) where *peer_std* uses the **sample** standard
        deviation (ddof=1).  If fewer than 2 peers exist the std is returned
        as 0.0 to avoid division-by-zero downstream.
    """
    peer_values = [
        count
        for entity, count in entity_alert_counts.items()
        if entity != current_entity
    ]

    if not peer_values:
        return 0.0, 0.0

    peer_mean = statistics.mean(peer_values)

    if len(peer_values) < 2:
        peer_std = 0.0
    else:
        peer_std = statistics.stdev(peer_values)

    return peer_mean, peer_std


# ---------------------------------------------------------------------------
# Missing severity helper
# ---------------------------------------------------------------------------

def detect_missing_severities(
    entity_severity_sets: dict[str, set[str]],
    current_entity: str,
) -> list[str]:
    """Identify severity categories expected by peers but absent from *current_entity*.

    A severity is considered *expected* if at least ``MIN_PEERS_WITH_SEVERITY``
    peer entities contain it.  Severity matching is case-insensitive — all
    input values are normalised to lowercase before comparison.

    Parameters
    ----------
    entity_severity_sets:
        Mapping of entity name → set of severity strings (any case).
    current_entity:
        The entity under evaluation.

    Returns
    -------
    list[str]
        Sorted list of expected severity categories (lowercase) missing from
        the entity.
    """
    # Normalise everything to lowercase for case-insensitive comparison.
    normalised: dict[str, set[str]] = {
        ent: {s.lower() for s in sevs}
        for ent, sevs in entity_severity_sets.items()
    }

    peer_entities = {
        ent: sevs
        for ent, sevs in normalised.items()
        if ent != current_entity
    }

    if not peer_entities:
        return []

    # Count how many peer entities have each severity.
    severity_peer_count: dict[str, int] = defaultdict(int)
    for _entity, sevs in peer_entities.items():
        for sev in sevs:
            severity_peer_count[sev] += 1

    # Expected severities = those appearing in >= MIN_PEERS_WITH_SEVERITY peers.
    expected_severities = {
        sev
        for sev, count in severity_peer_count.items()
        if count >= MIN_PEERS_WITH_SEVERITY
    }

    current_sevs = normalised.get(current_entity, set())

    missing = sorted(expected_severities - current_sevs)
    return missing


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------

def _rule_low_alert_volume(
    entity_alert_count: int,
    peer_mean: float,
    peer_std: float,
) -> tuple[bool, float, Finding | None]:
    """Check whether the entity's alert count is significantly below its peers.

    Returns
    -------
    tuple[bool, float, Finding | None]
        (triggered, z_score, finding_or_None)
    """
    if peer_std == 0.0:
        # All peers have the same count — no meaningful z-score.
        # Flag only if the entity is strictly below the peer mean.
        z_score = 0.0 if entity_alert_count == peer_mean else (
            -1.0 if entity_alert_count < peer_mean else 1.0
        )
    else:
        z_score = (entity_alert_count - peer_mean) / peer_std

    triggered = z_score <= LOW_VOLUME_Z_THRESHOLD

    if triggered:
        finding = Finding(
            type=RULE_LOW_ALERT_VOLUME,
            detail=(
                f"Observed {entity_alert_count} alerts versus peer mean of "
                f"{peer_mean:.1f} alerts."
            ),
            reason=(
                f"Alert activity is significantly below the peer baseline "
                f"(z={z_score:.2f})."
            ),
        )
    else:
        finding = None

    return triggered, z_score, finding


def _rule_missing_expected_severity(
    current_severities: set[str],
    missing_severities: list[str],
    total_expected: int,
) -> tuple[float, list[Finding]]:
    """Evaluate missing severity categories.

    Returns
    -------
    tuple[float, list[Finding]]
        (severity_signal, list_of_findings) where *severity_signal* ∈ [0.0, 1.0].
    """
    if total_expected == 0:
        return 0.0, []

    signal = len(missing_severities) / total_expected

    findings = [
        Finding(
            type=RULE_MISSING_EXPECTED_SEVERITY,
            detail=f"{sev.capitalize()} severity alerts are absent for this entity.",
            reason=(
                f"{sev.capitalize()} severity activity is present across peer "
                f"entities but absent for this entity."
            ),
        )
        for sev in missing_severities
    ]

    return signal, findings


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _compute_for_entity(
    entity_name: str,
    entity_alerts: list[Alert],
    entity_alert_counts: dict[str, int],
    entity_severity_sets: dict[str, set[str]],
) -> NegativeSpaceResult:
    """Compute all negative-space rules and the combined score for one entity."""

    total_alerts = len(entity_alerts)

    # --- Peer baseline (alert volume) ---
    peer_mean, peer_std = build_peer_baseline(entity_alert_counts, entity_name)
    low_volume_triggered, z_score, low_volume_finding = _rule_low_alert_volume(
        total_alerts, peer_mean, peer_std
    )
    low_volume_signal = 1.0 if low_volume_triggered else 0.0

    # --- Missing severities ---
    current_severities = entity_severity_sets.get(entity_name, set())
    missing = detect_missing_severities(entity_severity_sets, entity_name)

    # Compute total expected severities (those expected by peers).
    peer_entities_sevs = {
        ent: sevs
        for ent, sevs in entity_severity_sets.items()
        if ent != entity_name
    }
    severity_peer_count: dict[str, int] = defaultdict(int)
    for _ent, sevs in peer_entities_sevs.items():
        for s in sevs:
            severity_peer_count[s] += 1
    total_expected = sum(
        1 for s, c in severity_peer_count.items() if c >= MIN_PEERS_WITH_SEVERITY
    )

    missing_severity_signal, missing_sev_findings = _rule_missing_expected_severity(
        current_severities, missing, total_expected
    )

    # --- Asset silence (reserved — insufficient data to trigger) ---
    missing_asset_count = 0

    # --- Combined score ---
    raw_score = (
        LOW_VOLUME_WEIGHT * low_volume_signal
        + MISSING_SEVERITY_WEIGHT * missing_severity_signal
    )
    score = max(0.0, min(1.0, raw_score))

    # --- Assemble evidence ---
    evidence: list[Finding] = []
    if low_volume_finding is not None:
        evidence.append(low_volume_finding)
    evidence.extend(missing_sev_findings)

    metrics = {
        "total_alerts": total_alerts,
        "peer_mean_alerts": round(peer_mean, 1),
        "peer_std_alerts": round(peer_std, 1),
        "alert_volume_z_score": round(z_score, 2),
        "missing_asset_count": missing_asset_count,
        "missing_severity_count": len(missing),
    }

    return NegativeSpaceResult(
        entity_name=entity_name,
        negative_space_score=round(score, 3),
        metrics=metrics,
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Public API — integrates with SQLAlchemy (matches execution_gap.py pattern)
# ---------------------------------------------------------------------------

def compute_negative_space(db: Session) -> dict[str, NegativeSpaceResult]:
    """Compute Negative Space results for every entity present in the alerts table.

    Parameters
    ----------
    db:
        An open SQLAlchemy session pointing at the alerts table.

    Returns
    -------
    dict[str, NegativeSpaceResult]
        Mapping of entity name → its ``NegativeSpaceResult``.
    """
    alerts = db.execute(select(Alert)).scalars().all()

    # Group alerts by entity.
    by_entity: dict[str, list[Alert]] = defaultdict(list)
    for alert in alerts:
        by_entity[alert.entity_name].append(alert)

    # Pre-compute per-entity aggregates.
    entity_alert_counts: dict[str, int] = {
        name: len(al) for name, al in by_entity.items()
    }
    entity_severity_sets: dict[str, set[str]] = {
        name: {a.severity.lower() for a in al}
        for name, al in by_entity.items()
    }

    return {
        entity_name: _compute_for_entity(
            entity_name, entity_alerts, entity_alert_counts, entity_severity_sets
        )
        for entity_name, entity_alerts in by_entity.items()
    }


# ---------------------------------------------------------------------------
# CLI standalone runner (reads from SQLite DB or CSV)
# ---------------------------------------------------------------------------

def _run_cli() -> None:
    """Standalone CLI entry-point for development and demo."""
    import argparse
    import csv
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="SAT-SA Negative Space detector (CLI)")
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to SQLite DB file. If omitted, tries backend/data/satsa.db.",
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to an alert CSV file. If provided, data is read directly from CSV.",
    )
    args = parser.parse_args()

    # ---- Mode 1: Read from CSV directly (no DB required) ----
    if args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
            sys.exit(1)
        _run_from_csv(csv_path)
        return

    # ---- Mode 2: Read from SQLite DB ----
    db_path = Path(args.db) if args.db else Path(__file__).resolve().parent.parent.parent / "data" / "satsa.db"
    if not db_path.exists():
        print(
            f"Error: Database not found at {db_path}\n"
            "  Use --csv <path> to run from a CSV file, or upload data via the API first.",
            file=sys.stderr,
        )
        sys.exit(1)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        results = compute_negative_space(db)
    finally:
        db.close()

    _print_results(results)


def _run_from_csv(csv_path: Path) -> None:
    """Run the detector by reading alerts directly from a CSV file."""
    import csv as csv_mod

    alerts_data: list[dict[str, str]] = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv_mod.DictReader(fh)
        for row in reader:
            alerts_data.append(row)

    if not alerts_data:
        print("No alerts found in CSV.", file=sys.stderr)
        sys.exit(1)

    # Build the same aggregates the detector expects.
    by_entity: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in alerts_data:
        by_entity[row["entity_name"]].append(row)

    entity_alert_counts: dict[str, int] = {
        name: len(rows) for name, rows in by_entity.items()
    }
    entity_severity_sets: dict[str, set[str]] = {
        name: {row["severity"].strip().lower() for row in rows}
        for name, rows in by_entity.items()
    }

    results: dict[str, NegativeSpaceResult] = {}
    for entity_name, entity_rows in by_entity.items():
        # Build lightweight objects that mimic Alert attributes for the rules.
        results[entity_name] = _compute_for_entity_csv(
            entity_name, entity_rows, entity_alert_counts, entity_severity_sets
        )

    _print_results(results)


def _compute_for_entity_csv(
    entity_name: str,
    entity_rows: list[dict[str, str]],
    entity_alert_counts: dict[str, int],
    entity_severity_sets: dict[str, set[str]],
) -> NegativeSpaceResult:
    """Compute negative space for one entity from CSV row dicts (CLI mode)."""
    total_alerts = len(entity_rows)

    peer_mean, peer_std = build_peer_baseline(entity_alert_counts, entity_name)
    low_volume_triggered, z_score, low_volume_finding = _rule_low_alert_volume(
        total_alerts, peer_mean, peer_std
    )
    low_volume_signal = 1.0 if low_volume_triggered else 0.0

    missing = detect_missing_severities(entity_severity_sets, entity_name)

    peer_entities_sevs = {
        ent: sevs
        for ent, sevs in entity_severity_sets.items()
        if ent != entity_name
    }
    severity_peer_count: dict[str, int] = defaultdict(int)
    for _ent, sevs in peer_entities_sevs.items():
        for s in sevs:
            severity_peer_count[s] += 1
    total_expected = sum(
        1 for s, c in severity_peer_count.items() if c >= MIN_PEERS_WITH_SEVERITY
    )

    missing_severity_signal, missing_sev_findings = _rule_missing_expected_severity(
        entity_severity_sets.get(entity_name, set()), missing, total_expected
    )

    missing_asset_count = 0

    raw_score = (
        LOW_VOLUME_WEIGHT * low_volume_signal
        + MISSING_SEVERITY_WEIGHT * missing_severity_signal
    )
    score = max(0.0, min(1.0, raw_score))

    evidence: list[Finding] = []
    if low_volume_finding is not None:
        evidence.append(low_volume_finding)
    evidence.extend(missing_sev_findings)

    metrics = {
        "total_alerts": total_alerts,
        "peer_mean_alerts": round(peer_mean, 1),
        "peer_std_alerts": round(peer_std, 1),
        "alert_volume_z_score": round(z_score, 2),
        "missing_asset_count": missing_asset_count,
        "missing_severity_count": len(missing),
    }

    return NegativeSpaceResult(
        entity_name=entity_name,
        negative_space_score=round(score, 3),
        metrics=metrics,
        evidence=evidence,
    )


def _print_results(results: dict[str, NegativeSpaceResult]) -> None:
    """Pretty-print results to stdout for CLI / demo use."""
    print("\n===== SAT-SA NEGATIVE SPACE RESULTS =====\n")

    for entity_name in sorted(results):
        r = results[entity_name]
        print(f"[{entity_name}]")
        print(f"   Negative Space Score : {r.negative_space_score:.3f}")
        print(f"   Metrics              : {r.metrics}")
        if r.evidence:
            print("   Evidence:")
            for f in r.evidence:
                print(f"      -> {f.type}")
                print(f"         Observed: {f.detail}")
                print(f"         Reason:   {f.reason}")
        else:
            print("   Evidence:")
            print("      No significant negative-space signal detected.")
    print()


if __name__ == "__main__":
    _run_cli()
