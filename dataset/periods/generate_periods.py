"""Generate a four-quarter multi-period version of the SAT-SA synthetic dataset.

The existing dataset (dataset/soc_alerts_synthetic_dataset.csv) is a single
snapshot, so every entity has exactly one AssessmentRun and the trend feature
has nothing to plot. This script generates four quarterly CSVs — same 10
entities, same 8-column ingestion schema — so uploading them in order builds
up a real multi-period history per entity.

Same generation approach as backend/benchmark.py: numpy Generator with a
fixed seed, categorical fields drawn from the real dataset's observed
per-field frequency weights (severity, asset_type), the same fixed
investigation-notes pool, and closure durations in the same observed range.
Unlike benchmark.py (which only cares about scale), this script also
reproduces the *shape* of the three real seeded patterns already baked into
the original dataset (see project.md and dataset/answer_key_INTERNAL_ONLY.csv
[gitignored]) — execution-gap's fast-closure/no-escalation/template-notes
rates, negative-space's collapsing alert volume, and anomaly's volume spike —
by directly controlling the same knobs the detectors read, per entity per
quarter. See dataset/periods/README.md for exactly what was planted where.

Usage: python generate_periods.py
"""

from __future__ import annotations

import csv as csv_mod
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

OUT_DIR = Path(__file__).resolve().parent

GEN_SEED: int = 20250701
"""Fixed seed — every run of this script reproduces byte-identical CSVs."""

# ---------------------------------------------------------------------------
# Schema — the 8 columns app.routers.ingestion.REQUIRED_COLUMNS actually reads
# (category/closure_duration_minutes/status from the original 11-column CSV
# are dropped; closure_duration_minutes is implied by closed_time - created_time).
# ---------------------------------------------------------------------------

COLUMNS: list[str] = [
    "alert_id", "entity_name", "severity", "created_time", "closed_time",
    "escalated", "investigation_notes", "asset_type",
]

# ---------------------------------------------------------------------------
# Value pools and weights — observed frequencies in
# dataset/soc_alerts_synthetic_dataset.csv (same values used in benchmark.py).
# ---------------------------------------------------------------------------

SEVERITIES: list[str] = ["Low", "Medium", "High", "Critical"]
SEVERITY_WEIGHTS: list[float] = [0.372457, 0.316119, 0.181534, 0.129890]

ASSET_TYPES: list[str] = [
    "Cloud Workload", "Database", "Endpoint", "IoT Device", "Network Device", "Server",
]
ASSET_TYPE_WEIGHTS: list[float] = [
    0.176839, 0.173709, 0.173709, 0.165884, 0.158059, 0.151800,
]

ESCALATION_RATE_BY_SEVERITY: dict[str, float] = {
    "Critical": 0.638554,
    "High": 0.750000,
    "Low": 0.239496,
    "Medium": 0.207921,
}
"""Baseline P(escalated=Yes | severity) — applied whenever an entity/quarter
has no execution-gap override active for that severity."""

# The real dataset's 8-note pool splits naturally into two groups by how the
# real seeded execution-gap entities (Indus Financial Services, Continental
# Banking Corp) used them: 4 detailed, non-template notes normal SOC work
# produces, and 4 short/generic notes that read as rubber-stamped closures.
LONG_NOTES: list[str] = [
    "Correlated with SIEM logs across 3 hosts, identified lateral movement attempt, escalated.",
    "Investigated source IP, confirmed malicious signature, blocked at firewall, root cause documented.",
    "Performed forensic triage on affected host, isolated system, initiated containment protocol.",
    "Cross-referenced with threat intel feed, identified C2 communication pattern, escalated to IR team.",
]
SHORT_NOTES: list[str] = [
    "Reviewed and closed.",
    "No further action required.",
    "Closed as per standard procedure.",
    "False positive.",
]
ALL_NOTES: list[str] = LONG_NOTES + SHORT_NOTES
"""Baseline entities draw uniformly from all 8, exactly like the real dataset
— every entity sharing the same 8-note pool is what keeps TEMPLATE_NOTES a
peer-relative signal rather than one that fires on everyone."""

FAST_CLOSURE_SEVERITIES: set[str] = {"critical", "high"}
"""Mirrors execution_gap.FAST_CLOSURE_SEVERITIES."""
NO_ESCALATION_OVERRIDE_SEVERITIES: set[str] = {"critical", "high"}
"""Severities whose escalation an execution-gap profile can override. Only
"critical" feeds execution_gap.py's NO_ESCALATION rule directly, but the real
seeded Continental Banking Corp row also drove High-severity escalation to
0% — reproduced here so the anomaly detector's escalation_rate feature and
the rule both move together, the way they did in the original dataset."""

NORMAL_DURATION_MIN_MINUTES: int = 150
NORMAL_DURATION_MAX_MINUTES: int = 210
"""Closure duration for every alert with no fast-closure override active —
i.e. every baseline-entity alert, Delta Rail's and Fortis's alerts in every
quarter, and the (1 - fast_closure_rate) fraction of Indus's/Continental's.

Deliberately much narrower than the real single-snapshot dataset's observed
1-598 minute range. That range is fine for a single static snapshot, but
under repeated quarter-over-quarter peer comparison (see
compute_anomaly_from_features -> _peer_median/_peer_mad in anomaly.py, run
fresh against only 9 peers each quarter) it lets a "normal" entity's own
average closure time wobble by double-digit percentages purely from
per-alert sampling noise, and with only 9 peers the resulting peer MAD
estimate is itself noisy enough that an entity's harmless wobble can read as
a multi-sigma deviation in one quarter and nothing in the next. Narrowing
this range shrinks that sampling noise so the six baseline entities' own
avg_closure_seconds stays genuinely close together and stable release over
release, which is what actually keeps them off the top of the isolation
forest's per-quarter relative ranking — see dataset/periods/README.md for
the diagnosis this constant was tuned against."""

FAST_DURATION_MIN_MINUTES: int = 1
FAST_DURATION_MAX_MINUTES: int = 4
"""1-4 minutes — the exact closure_duration_minutes range observed on the
real dataset's Indus Financial Services / Continental Banking Corp rows."""

ENTITY_NAMES: list[str] = [
    "Jupiter Aviation Control",
    "Eastern Water Utility",
    "Indus Financial Services",
    "Fortis Defense Systems",
    "Ganga Oil & Gas",
    "Bharat Telecom Networks",
    "Himalayan Healthcare Network",
    "Apex Power Grid Ltd",
    "Continental Banking Corp",
    "Delta Rail Systems",
]
"""Same 10 entities as dataset/soc_alerts_synthetic_dataset.csv."""

BASELINE_ALERT_COUNT: dict[str, int] = {
    "Jupiter Aviation Control": 90,
    "Eastern Water Utility": 95,
    "Ganga Oil & Gas": 90,
    "Bharat Telecom Networks": 85,
    "Himalayan Healthcare Network": 100,
    "Apex Power Grid Ltd": 95,
}
"""Per-quarter target volume for the six stable entities (±BASELINE_NOISE_FRACTION
noise applied per quarter — see _noisy_count). Roughly double the real
dataset's per-6-month totals for these same entities — a deliberate increase
(not just a schema match) so every rate-based feature (escalation_rate,
critical_ratio, avg_note_length, avg_closure_seconds) averages over more
alerts and each entity's own quarterly mean is less exposed to sampling
noise, on top of the tightened NORMAL_DURATION range above."""

BASELINE_NOISE_FRACTION: float = 0.06
"""Multiplicative per-quarter volume noise for the six stable entities.
Lowered from an earlier 0.15 — the same instability documented in
NORMAL_DURATION_MIN/MAX_MINUTES above applies here: alert_count is itself
one of the six anomaly features, so injecting the same size of noise this
detector is meant to distinguish from a real signal directly worked against
"stay genuinely close to peers"."""

QUARTERS: list[tuple[str, str, datetime, datetime]] = [
    ("2025_q3", "period_2025_q3.csv", datetime(2025, 7, 1), datetime(2025, 9, 30, 23, 59, 59)),
    ("2025_q4", "period_2025_q4.csv", datetime(2025, 10, 1), datetime(2025, 12, 31, 23, 59, 59)),
    ("2026_q1", "period_2026_q1.csv", datetime(2026, 1, 1), datetime(2026, 3, 31, 23, 59, 59)),
    ("2026_q2", "period_2026_q2.csv", datetime(2026, 4, 1), datetime(2026, 6, 30, 23, 59, 59)),
]


@dataclass(frozen=True)
class EntityQuarterProfile:
    """The knobs that drive one entity's alert generation for one quarter.

    fast_closure_rate / no_escalation_rate / template_notes_rate are all
    ``None`` for a quarter with no planted pattern — the entity falls back to
    the global baseline rates for every field that quarter.
    """

    alert_count: int
    fast_closure_rate: float | None = None
    no_escalation_rate: float | None = None
    template_notes_rate: float | None = None


# ---------------------------------------------------------------------------
# Planted per-entity, per-quarter profiles — see README.md for the narrative
# version of exactly what this table encodes.
# ---------------------------------------------------------------------------

SEEDED_PROFILES: dict[str, dict[str, EntityQuarterProfile]] = {
    "Delta Rail Systems": {
        # Negative-space: already mildly below the peer baseline in Q3 (about
        # 44% of the six stable entities' ~90/quarter band — enough to clear
        # a real, if modest, LOW_ALERT_VOLUME z-score, not "normal" in the
        # strict statistical sense), collapsing further every quarter after —
        # a deteriorating trend with no execution-gap or anomaly overrides at
        # any point; volume alone drives the signal.
        "2025_q3": EntityQuarterProfile(alert_count=40),
        "2025_q4": EntityQuarterProfile(alert_count=35),
        "2026_q1": EntityQuarterProfile(alert_count=15),
        "2026_q2": EntityQuarterProfile(alert_count=3),
    },
    "Indus Financial Services": {
        # Execution-gap present from Q3, worsening slightly each quarter —
        # by Q2 it reaches the same near-total rates the real single-snapshot
        # dataset shows for this entity.
        "2025_q3": EntityQuarterProfile(
            alert_count=60, fast_closure_rate=0.30, no_escalation_rate=0.30, template_notes_rate=0.25
        ),
        "2025_q4": EntityQuarterProfile(
            alert_count=62, fast_closure_rate=0.48, no_escalation_rate=0.48, template_notes_rate=0.42
        ),
        "2026_q1": EntityQuarterProfile(
            alert_count=64, fast_closure_rate=0.68, no_escalation_rate=0.68, template_notes_rate=0.62
        ),
        "2026_q2": EntityQuarterProfile(
            alert_count=66, fast_closure_rate=0.93, no_escalation_rate=0.93, template_notes_rate=0.90
        ),
    },
    "Continental Banking Corp": {
        # Execution-gap strongly present in Q3/Q4 (mirrors the real dataset's
        # single-snapshot Continental profile), then remediated: Q1 shows
        # partial improvement, Q2 is close to baseline. The one entity that
        # gets *better* — otherwise the trend feature only ever shows one
        # direction.
        "2025_q3": EntityQuarterProfile(
            alert_count=34, fast_closure_rate=0.90, no_escalation_rate=0.90, template_notes_rate=0.85
        ),
        "2025_q4": EntityQuarterProfile(
            alert_count=33, fast_closure_rate=0.85, no_escalation_rate=0.85, template_notes_rate=0.80
        ),
        "2026_q1": EntityQuarterProfile(
            alert_count=45, fast_closure_rate=0.35, no_escalation_rate=0.35, template_notes_rate=0.30
        ),
        "2026_q2": EntityQuarterProfile(
            alert_count=60, fast_closure_rate=0.05, no_escalation_rate=0.10, template_notes_rate=0.10
        ),
    },
    "Fortis Defense Systems": {
        # Anomaly-spike: near-baseline volume through Q4, then a sudden
        # step-change in Q1 that continues into Q2 — nothing gradual,
        # matching "appearing only in Q1/Q2". The Q1/Q2 spike is carried
        # entirely by alert_count, as originally intended; Q3/Q4 needed a
        # second, deliberately boring stabilizer alongside alert_count —
        # see below for why volume alone would not reliably hold there.
        #
        # Q3/Q4 (alert_count=100, no_escalation_rate=0.85): 100 is only a
        # hair above the six stable entities' own ~85-100/quarter band —
        # deliberately not the 150-200 range tried and discarded below.
        # anomaly.py's per-quarter score is an Isolation Forest output
        # rescaled *relative to whichever other entities are most anomalous
        # that same quarter* (see _convert_scores), and Q3/Q4 are exactly
        # the quarters where Continental Banking Corp's execution-gap
        # pattern is near its worst. Every volume tried in that 150-200
        # range produced a highly unstable anomaly score purely from how
        # much of the "most anomalous" ranking Continental happened to
        # leave available that specific quarter (e.g. one run: an=0.286 in
        # Q3 but an=0.417 in Q4 off an *identical* alert_count of 200,
        # because Continental's own rates eased slightly between the two
        # quarters) — occasionally landing Fortis's "boring" quarter above
        # its own Q1/Q2 "spike" quarter, reproducing the exact bug this fix
        # exists to remove, just at different numbers. A small, fixed
        # no_escalation_rate override (deterministic — it does not depend on
        # what any other entity does that quarter) gives Q3/Q4 a reliable
        # floor comfortably above the stable-entity ceiling without
        # depending on winning a volatile, competitive anomaly ranking; the
        # near-baseline alert_count keeps that quarter's own anomaly
        # contribution small and quiet, so the floor mostly comes from this
        # execution_gap contribution instead. This is a real, if modest,
        # signal (not literally zero), so "low and unremarkable" here means
        # "far below Delta's/Continental's/Indus's worst quarters and below
        # its own Q1/Q2", not "statistically identical to a clean entity".
        #
        # Q1/Q2 (alert_count=320/360): a ~3.2-3.6x jump off the ~100
        # baseline, sized to dominate the anomaly ranking regardless of what
        # Continental/Indus/Delta are doing that quarter — the actual
        # anomaly-spike signal, and the reason Q1/Q2 read clearly higher
        # than Q3/Q4 even though Q3/Q4 no longer scores anywhere near zero.
        "2025_q3": EntityQuarterProfile(alert_count=95, no_escalation_rate=0.85),
        "2025_q4": EntityQuarterProfile(alert_count=95, no_escalation_rate=0.85),
        "2026_q1": EntityQuarterProfile(alert_count=550),
        "2026_q2": EntityQuarterProfile(alert_count=650),
    },
}

STABLE_ENTITIES: list[str] = [name for name in ENTITY_NAMES if name not in SEEDED_PROFILES]
"""The six entities with no planted pattern in any quarter — pure baseline
with normal quarter-to-quarter noise."""


def _normalized(weights: list[float]) -> np.ndarray:
    arr = np.array(weights, dtype=float)
    return arr / arr.sum()


def _noisy_count(base: int, rng: np.random.Generator) -> int:
    """Apply ±BASELINE_NOISE_FRACTION multiplicative noise to a baseline count."""
    factor = rng.uniform(1.0 - BASELINE_NOISE_FRACTION, 1.0 + BASELINE_NOISE_FRACTION)
    return max(1, int(round(base * factor)))


def _profile_for(entity: str, quarter_key: str, rng: np.random.Generator) -> EntityQuarterProfile:
    """Resolve the profile driving *entity*'s generation in *quarter_key*."""
    if entity in SEEDED_PROFILES:
        return SEEDED_PROFILES[entity][quarter_key]
    return EntityQuarterProfile(alert_count=_noisy_count(BASELINE_ALERT_COUNT[entity], rng))


def _generate_alert(
    idx: int,
    entity: str,
    profile: EntityQuarterProfile,
    quarter_start: datetime,
    quarter_end: datetime,
    rng: np.random.Generator,
) -> dict[str, str]:
    """Build one alert row for *entity* under *profile*."""
    severity = rng.choice(SEVERITIES, p=_normalized(SEVERITY_WEIGHTS))
    asset_type = rng.choice(ASSET_TYPES, p=_normalized(ASSET_TYPE_WEIGHTS))
    severity_lc = severity.lower()

    # --- closure duration ---
    fast_closure_rate = profile.fast_closure_rate
    is_fast_candidate = severity_lc in FAST_CLOSURE_SEVERITIES
    if is_fast_candidate and fast_closure_rate is not None and rng.random() < fast_closure_rate:
        duration_minutes = int(rng.integers(FAST_DURATION_MIN_MINUTES, FAST_DURATION_MAX_MINUTES + 1))
    else:
        duration_minutes = int(rng.integers(NORMAL_DURATION_MIN_MINUTES, NORMAL_DURATION_MAX_MINUTES + 1))

    # --- escalation ---
    no_escalation_rate = profile.no_escalation_rate
    if severity_lc in NO_ESCALATION_OVERRIDE_SEVERITIES and no_escalation_rate is not None:
        escalated = rng.random() >= no_escalation_rate
    else:
        escalated = rng.random() < ESCALATION_RATE_BY_SEVERITY[severity]

    # --- investigation notes ---
    template_notes_rate = profile.template_notes_rate
    if template_notes_rate is not None and rng.random() < template_notes_rate:
        note = rng.choice(SHORT_NOTES)
    else:
        note = rng.choice(ALL_NOTES)

    # --- timestamps, inside this quarter's actual date range ---
    span_minutes = int((quarter_end - quarter_start).total_seconds() // 60)
    offset_minutes = int(rng.integers(0, span_minutes + 1))
    created_time = quarter_start + timedelta(minutes=offset_minutes)
    closed_time = created_time + timedelta(minutes=duration_minutes)
    if closed_time > quarter_end:
        closed_time = quarter_end  # keep both timestamps inside the quarter

    return {
        "alert_id": f"ALT{idx + 1:05d}",
        "entity_name": entity,
        "severity": severity,
        "created_time": created_time.strftime("%Y-%m-%d %H:%M:%S"),
        "closed_time": closed_time.strftime("%Y-%m-%d %H:%M:%S"),
        "escalated": "Yes" if escalated else "No",
        "investigation_notes": note,
        "asset_type": asset_type,
    }


def generate_quarter(quarter_key: str, quarter_start: datetime, quarter_end: datetime, seed: int) -> list[dict[str, str]]:
    """Generate every entity's rows for one quarter, in entity order."""
    rows: list[dict[str, str]] = []
    for entity in ENTITY_NAMES:
        # A separate, entity+quarter-derived RNG stream so adding/removing an
        # entity's pattern in one quarter never perturbs another entity's
        # random draws in the same quarter (each entity's stream is fully
        # independent and reproducible on its own).
        # zlib.crc32 (not Python's salted built-in hash()) so the derived
        # seed — and therefore every generated row — is identical run to run.
        entity_seed = seed ^ zlib.crc32(f"{entity}|{quarter_key}".encode("utf-8"))
        rng = np.random.default_rng(entity_seed)
        profile = _profile_for(entity, quarter_key, rng)
        for i in range(profile.alert_count):
            rows.append(_generate_alert(i, entity, profile, quarter_start, quarter_end, rng))
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv_mod.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for quarter_key, filename, start, end in QUARTERS:
        rows = generate_quarter(quarter_key, start, end, GEN_SEED)
        path = OUT_DIR / filename
        write_csv(rows, path)
        print(f"{filename}: {len(rows)} alerts across {len(ENTITY_NAMES)} entities")


if __name__ == "__main__":
    main()
