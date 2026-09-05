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
"""Modified z-score at or below which low-alert-volume starts to be flagged
(signal 0.0 at this point — see LOW_VOLUME_Z_SATURATION for the ramp)."""

LOW_VOLUME_Z_SATURATION: float = -5.0
"""Modified z-score at or below which the low-alert-volume signal saturates
at 1.0. Between LOW_VOLUME_Z_THRESHOLD and this point the signal is a linear
ramp, not a binary trigger — an entity far past the threshold (e.g. a
near-total silence at z=-5.49) should read as more severe than one that just
crossed it (z=-1.01); a flat 0/1 trigger discards that magnitude."""

MAD_ZSCORE_SCALE: float = 0.6745
"""Scale factor converting MAD to a std-equivalent z-score (75th percentile
of the standard normal). Mirrors the constant of the same name in anomaly.py
and execution_gap.py."""

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
    """Compute the median and MAD of alert counts for *peers*.

    The *current_entity* is excluded from the calculation so that an entity
    is never compared against itself. Same median/MAD-based peer-baseline
    convention used for feature attribution in anomaly.py (see
    MAD_ZSCORE_SCALE there) and mirrored by execution_gap.py's
    ``_peer_median_mad`` — robust to a single outlier the way mean/stdev is
    not. Concretely: Fortis Defense Systems' 166 alerts previously inflated
    the peer standard deviation enough to weaken Delta Rail's low-volume
    signal (z=-1.86 on mean/stdev); median/MAD is not pulled by that outlier.

    Parameters
    ----------
    entity_alert_counts:
        Mapping of entity name → total alert count for every entity.
    current_entity:
        The entity whose peer baseline is being computed.

    Returns
    -------
    tuple[float, float]
        (peer_median, peer_mad). MAD is returned as 0.0 when fewer than 2
        peers exist, to signal the zero-MAD fallback path downstream.
    """
    peer_values = [
        count
        for entity, count in entity_alert_counts.items()
        if entity != current_entity
    ]

    if not peer_values:
        return 0.0, 0.0

    peer_median = statistics.median(peer_values)

    if len(peer_values) < 2:
        return peer_median, 0.0

    peer_mad = statistics.median(abs(v - peer_median) for v in peer_values)
    return peer_median, peer_mad


def _modified_z_score(value: float, peer_median: float, peer_mad: float) -> float:
    """Modified z-score of *value* against a peer median/MAD, with a zero-MAD fallback.

    Mirrors the helper of the same purpose in execution_gap.py.
    """
    if peer_mad == 0.0:
        if value == peer_median:
            return 0.0
        return 1.0 if value > peer_median else -1.0
    return MAD_ZSCORE_SCALE * (value - peer_median) / peer_mad


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

def _low_volume_signal(z_score: float) -> float:
    """Graded ramp from LOW_VOLUME_Z_THRESHOLD (0.0) to LOW_VOLUME_Z_SATURATION (1.0).

    Replaces a binary trigger so magnitude carries information: an entity at
    z=-5.49 reads as more severe than one at z=-1.01, instead of both reading
    as the same flat 1.0. Above the threshold (less negative) the signal is 0.0.
    """
    if z_score > LOW_VOLUME_Z_THRESHOLD:
        return 0.0
    span = LOW_VOLUME_Z_THRESHOLD - LOW_VOLUME_Z_SATURATION
    fraction = (LOW_VOLUME_Z_THRESHOLD - z_score) / span
    return max(0.0, min(1.0, fraction))


def _rule_low_alert_volume(
    entity_alert_count: int,
    peer_median: float,
    peer_mad: float,
) -> tuple[float, float, Finding | None]:
    """Check whether the entity's alert count is significantly below its peers.

    Returns
    -------
    tuple[float, float, Finding | None]
        (signal, z_score, finding_or_None) — *signal* is the graded
        LOW_VOLUME ramp in [0.0, 1.0] from _low_volume_signal, not a boolean.
    """
    z_score = _modified_z_score(entity_alert_count, peer_median, peer_mad)
    signal = _low_volume_signal(z_score)

    if signal > 0.0:
        finding = Finding(
            type=RULE_LOW_ALERT_VOLUME,
            detail=(
                f"Observed {entity_alert_count} alerts versus peer median of "
                f"{peer_median:.1f} alerts."
            ),
            reason=(
                f"Alert activity is significantly below the peer baseline "
                f"(z={z_score:.2f})."
            ),
        )
    else:
        finding = None

    return signal, z_score, finding


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
    peer_median, peer_mad = build_peer_baseline(entity_alert_counts, entity_name)
    low_volume_signal, z_score, low_volume_finding = _rule_low_alert_volume(
        total_alerts, peer_median, peer_mad
    )

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
        "peer_median_alerts": round(peer_median, 1),
        "peer_mad_alerts": round(peer_mad, 1),
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

def compute_negative_space(db: Session) -> dict[str, dict]:
    """Compute Negative Space results for every entity present in the alerts table.

    Returns the shared detector contract shape documented in project.md:
    ``{"score": float, "metrics": dict, "evidence": list[{"detail": str, "reason": str}]}``.

    Parameters
    ----------
    db:
        An open SQLAlchemy session pointing at the alerts table.

    Returns
    -------
    dict[str, dict]
        Mapping of entity name → its contract-shaped result dict.
    """
    objects = _compute_negative_space_objects(db)
    return {entity_name: _to_contract_dict(result) for entity_name, result in objects.items()}


def compute_negative_space_from_csv(csv_path) -> dict[str, dict]:
    """Compute Negative Space results directly from a CSV file."""
    import csv as csv_mod
    from pathlib import Path

    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"CSV file not found at {p}")

    alerts_data: list[dict[str, str]] = []
    with open(p, newline="", encoding="utf-8") as fh:
        reader = csv_mod.DictReader(fh)
        for row in reader:
            alerts_data.append(row)

    by_entity: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in alerts_data:
        entity = row.get("entity_name", "").strip()
        if entity:
            by_entity[entity].append(row)

    entity_alert_counts: dict[str, int] = {
        name: len(rows) for name, rows in by_entity.items()
    }
    entity_severity_sets: dict[str, set[str]] = {
        name: {row["severity"].strip().lower() for row in rows if row.get("severity")}
        for name, rows in by_entity.items()
    }

    results: dict[str, NegativeSpaceResult] = {}
    for entity_name, entity_rows in by_entity.items():
        results[entity_name] = _compute_for_entity_csv(
            entity_name, entity_rows, entity_alert_counts, entity_severity_sets
        )

    return {entity_name: _to_contract_dict(res) for entity_name, res in results.items()}



def _to_contract_dict(result: NegativeSpaceResult) -> dict:
    """Serialize a NegativeSpaceResult into the shared detector contract shape."""
    return {
        "score": result.negative_space_score,
        "metrics": result.metrics,
        "evidence": [
            {"detail": f"{f.type}: {f.detail}", "reason": f.reason} for f in result.evidence
        ],
    }


def _compute_negative_space_objects(db: Session) -> dict[str, NegativeSpaceResult]:
    """Compute Negative Space results as internal dataclasses (used by compute_negative_space and the CLI)."""
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
        results = _compute_negative_space_objects(db)
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

    peer_median, peer_mad = build_peer_baseline(entity_alert_counts, entity_name)
    low_volume_signal, z_score, low_volume_finding = _rule_low_alert_volume(
        total_alerts, peer_median, peer_mad
    )

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
        "peer_median_alerts": round(peer_median, 1),
        "peer_mad_alerts": round(peer_mad, 1),
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
