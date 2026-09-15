"""Generate a four-quarter multi-period version of the SAT-SA extended dataset.

dataset/soc_alerts_extended.csv is a single snapshot (21 entities, Jan-Jun
2026), so every entity has exactly one AssessmentRun and the trend feature
has nothing to plot. This script generates four quarterly CSVs — same 21
entities, same 8-column ingestion schema, entity roster and per-field value
pools matching dataset/generate_extended.py — so uploading them in order
builds up a real multi-period history per entity.

Regenerated 2026-09 to replace an earlier version built against the retired
10-entity primary dataset (Delta Rail Systems / Indus Financial Services /
Continental Banking Corp), which no longer exist in the canonical roster.
Same mechanism as before: numpy Generator with a fixed seed, and the same
knobs the detectors read directly (fast_closure_rate / no_escalation_rate /
template_notes_rate for execution_gap.py, alert_count and severity weights
for negative_space.py, alert_count and closure/escalation/severity/asset
drift for anomaly.py) driven per entity per quarter so each seeded entity
traces a deliberate quarter-over-quarter trajectory. See
dataset/periods/README.md for the narrative version of exactly what was
planted where, and dataset/README_extended.md / dataset/generate_extended.py
for the single-snapshot values each trajectory converges toward.

Usage: python generate_periods.py
"""

from __future__ import annotations

import csv as csv_mod
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

OUT_DIR = Path(__file__).resolve().parent

GEN_SEED: int = 20260915
"""Fixed seed — every run of this script reproduces byte-identical CSVs."""

# ---------------------------------------------------------------------------
# Schema — the 8 columns app.routers.ingestion.REQUIRED_COLUMNS actually reads.
# ---------------------------------------------------------------------------

COLUMNS: list[str] = [
    "alert_id", "entity_name", "severity", "created_time", "closed_time",
    "escalated", "investigation_notes", "asset_type",
]

# ---------------------------------------------------------------------------
# Value pools and weights — mirrors dataset/generate_extended.py.
# ---------------------------------------------------------------------------

SEVERITIES: list[str] = ["Low", "Medium", "High", "Critical"]
NORMAL_SEVERITY_WEIGHTS: list[float] = [0.52, 0.28, 0.14, 0.06]
"""Baseline severity mix — matches generate_extended.py's NORMAL_SEV."""

ASSET_TYPES: list[str] = [
    "Server", "Endpoint", "Firewall", "Database", "Network Device",
    "Cloud Workload", "IoT Device", "Identity Provider",
]
ASSET_TYPE_WEIGHTS: list[float] = [1 / len(ASSET_TYPES)] * len(ASSET_TYPES)

ESCALATION_RATE_BY_SEVERITY: dict[str, float] = {
    "Critical": 0.638554,
    "High": 0.750000,
    "Low": 0.239496,
    "Medium": 0.207921,
}
"""Baseline P(escalated=Yes | severity) — applied whenever an entity/quarter
has no execution-gap or drift override active for that severity."""

LONG_NOTES: list[str] = [
    "Correlated with SIEM logs across 3 hosts, identified lateral movement attempt, escalated.",
    "Investigated source IP, confirmed malicious signature, blocked at firewall, root cause documented.",
    "Performed forensic triage on affected host, isolated system, initiated containment protocol.",
    "Cross-referenced with threat intel feed, identified C2 communication pattern, escalated to IR team.",
    "Reviewed EDR telemetry timeline; parent process traced to legitimate installer.",
    "Analysed PCAP sample; payload matched benign monitoring agent heartbeat.",
    "Contacted asset owner and confirmed scheduled maintenance window covered the activity.",
    "Ran memory capture on affected host; no injected process artefacts identified.",
]
SHORT_NOTES: list[str] = [
    "Reviewed and closed.",
    "No further action required.",
    "Closed as per standard procedure.",
    "False positive.",
]
ALL_NOTES: list[str] = LONG_NOTES + SHORT_NOTES
"""Baseline entities draw uniformly from all 12, keeping TEMPLATE_NOTES a
peer-relative signal rather than one that fires on everyone."""

FAST_CLOSURE_SEVERITIES: set[str] = {"critical", "high"}
"""Mirrors execution_gap.FAST_CLOSURE_SEVERITIES."""
NO_ESCALATION_OVERRIDE_SEVERITIES: set[str] = {"critical", "high"}
"""Severities whose escalation an execution-gap/drift profile can override."""

NORMAL_DURATION_MIN_MINUTES: int = 150
NORMAL_DURATION_MAX_MINUTES: int = 210
"""Closure duration for every alert with no fast-closure/drift override
active. Deliberately narrow (see the original version of this file / git
history for the full diagnosis) so a "normal" entity's own average closure
time doesn't wobble double digits purely from per-quarter sampling noise
against a modest peer count."""

FAST_DURATION_MIN_MINUTES: int = 1
FAST_DURATION_MAX_MINUTES: int = 4
"""1-4 minutes — matches Meridian Trust Bank's converged Q2 / single-snapshot
fast-closure range in generate_extended.py."""

# ---------------------------------------------------------------------------
# Entity roster — matches dataset/generate_extended.py's 21 entities exactly.
# ---------------------------------------------------------------------------

SEEDED_ENTITIES: list[str] = [
    "Saraswati Rail Network",
    "Meridian Trust Bank",
    "Kaveri Power Holdings",
    "Arcadia Defence Systems",
    "Konkan Maritime Ltd",
    "Nilgiri Water Authority",
    "Deccan Health Network",
]

BASELINE_ENTITIES: list[str] = [
    "Apex Power Grid Ltd",
    "Bharat Telecom Networks",
    "Cauvery Logistics Corp",
    "Eastern Grid Utility",
    "Godavari Chemicals",
    "Himalayan Healthcare Network",
    "Indus Financial Services",
    "Jupiter Aviation Control",
    "Krishna Port Authority",
    "Lakshmi Insurance Group",
    "Malabar Gas Pipelines",
    "Narmada Steel Works",
    "Orissa Mining Federation",
    "Pennar Cement Industries",
]

ENTITY_NAMES: list[str] = SEEDED_ENTITIES + BASELINE_ENTITIES

BASELINE_ALERT_COUNT: dict[str, int] = {
    "Apex Power Grid Ltd": 198,
    "Bharat Telecom Networks": 214,
    "Cauvery Logistics Corp": 187,
    "Eastern Grid Utility": 221,
    "Godavari Chemicals": 176,
    "Himalayan Healthcare Network": 209,
    "Indus Financial Services": 193,
    "Jupiter Aviation Control": 202,
    "Krishna Port Authority": 218,
    "Lakshmi Insurance Group": 181,
    "Malabar Gas Pipelines": 206,
    "Narmada Steel Works": 195,
    "Orissa Mining Federation": 212,
    "Pennar Cement Industries": 189,
}
"""Per-quarter target volume for the 14 stable entities (±BASELINE_NOISE_FRACTION
noise applied per quarter). Matches each entity's alert count in
generate_extended.py's single Jan-Jun 2026 snapshot."""

BASELINE_NOISE_FRACTION: float = 0.06
"""Multiplicative per-quarter volume noise for the 14 baseline entities —
alert_count is itself an anomaly feature, so this stays small enough that no
baseline entity's quarterly wobble competes with a seeded entity's signal."""

QUARTERS: list[tuple[str, str, datetime, datetime]] = [
    ("2025_q3", "period_2025_q3.csv", datetime(2025, 7, 1), datetime(2025, 9, 30, 23, 59, 59)),
    ("2025_q4", "period_2025_q4.csv", datetime(2025, 10, 1), datetime(2025, 12, 31, 23, 59, 59)),
    ("2026_q1", "period_2026_q1.csv", datetime(2026, 1, 1), datetime(2026, 3, 31, 23, 59, 59)),
    ("2026_q2", "period_2026_q2.csv", datetime(2026, 4, 1), datetime(2026, 6, 30, 23, 59, 59)),
]


@dataclass(frozen=True)
class EntityQuarterProfile:
    """The knobs that drive one entity's alert generation for one quarter.

    Every field left at its default falls back to the global baseline for
    that field. ``severity_weights`` overrides the [low, medium, high,
    critical] mix (e.g. to remove a severity entirely for negative-space's
    MISSING_EXPECTED_SEVERITY rule); ``assets`` restricts which asset types
    an entity's alerts are drawn from (for Konkan's asset-diversity drift);
    ``closure_range_minutes`` overrides the *baseline* (non-fast-closure)
    duration range (for Konkan's growing avg_closure_seconds); an
    ``escalation_rate_override`` maps individual severities to a flat
    escalation probability, independent of the execution-gap NO_ESCALATION
    override (used by Konkan to *raise*, not lower, escalation as part of
    its multi-feature drift).
    """

    alert_count: int
    fast_closure_rate: float | None = None
    no_escalation_rate: float | None = None
    template_notes_rate: float | None = None
    severity_weights: list[float] | None = None
    assets: list[str] | None = None
    closure_range_minutes: tuple[int, int] | None = None
    escalation_rate_override: dict[str, float] | None = None


# ---------------------------------------------------------------------------
# Planted per-entity, per-quarter profiles — see README.md for the narrative
# version of exactly what this table encodes.
# ---------------------------------------------------------------------------

SEEDED_PROFILES: dict[str, dict[str, EntityQuarterProfile]] = {
    # Deteriorating: near-normal in Q3, collapses into the negative-space
    # pattern (low volume + missing severities) by Q2 — matches
    # generate_extended.py's converged Saraswati profile (11 alerts,
    # low/medium only).
    "Saraswati Rail Network": {
        "2025_q3": EntityQuarterProfile(alert_count=180, severity_weights=[0.50, 0.29, 0.15, 0.06]),
        "2025_q4": EntityQuarterProfile(alert_count=90, severity_weights=[0.55, 0.30, 0.15, 0.00]),
        "2026_q1": EntityQuarterProfile(alert_count=35, severity_weights=[0.65, 0.35, 0.00, 0.00]),
        "2026_q2": EntityQuarterProfile(alert_count=11, severity_weights=[0.70, 0.30, 0.00, 0.00]),
    },
    # Execution-gap present from Q3, worsening every quarter, converging on
    # generate_extended.py's blatant Meridian profile by Q2 (94.7% fast
    # closure / 90.3% no-escalation / 100% template notes).
    #
    # alert_count is deliberately held near the 14-baseline band (~200-215)
    # every quarter, instead of climbing on its own — execution_gap.py's
    # score (40% of the blended risk_score, and NOT peer-relative) is the
    # only thing allowed to drive this entity's trend. A rising alert_count
    # would also feed anomaly.py's Isolation Forest, whose per-quarter score
    # is rescaled *relative to whichever other entities are most anomalous
    # that same quarter* (see Konkan Maritime Ltd's profile note below) — if
    # Meridian's own anomaly contribution spiked early (e.g. from an
    # elevated Q3 volume with comparatively little competition that quarter)
    # and then eased as Konkan/Saraswati's patterns escalate in later
    # quarters, the *blended* score could fall even while execution_gap
    # climbs. Keeping volume flat removes that confound; the escalating
    # fast-closure rate still pulls avg_closure_seconds down every quarter
    # too, so anomaly's own signal reinforces the climb instead of fighting
    # it.
    "Meridian Trust Bank": {
        "2025_q3": EntityQuarterProfile(
            alert_count=205, fast_closure_rate=0.15, no_escalation_rate=0.15, template_notes_rate=0.12
        ),
        "2025_q4": EntityQuarterProfile(
            alert_count=208, fast_closure_rate=0.45, no_escalation_rate=0.45, template_notes_rate=0.40
        ),
        "2026_q1": EntityQuarterProfile(
            alert_count=210, fast_closure_rate=0.75, no_escalation_rate=0.72, template_notes_rate=0.75
        ),
        "2026_q2": EntityQuarterProfile(
            alert_count=212, fast_closure_rate=0.97, no_escalation_rate=0.95, template_notes_rate=1.00
        ),
    },
    # Execution-gap in Q3/Q4 (peaking near generate_extended.py's subtle
    # Kaveri profile), then clearly improving in Q1/Q2 as if remediation
    # happened — the one entity that gets better.
    "Kaveri Power Holdings": {
        "2025_q3": EntityQuarterProfile(
            alert_count=230, fast_closure_rate=0.52, no_escalation_rate=0.62, template_notes_rate=0.36
        ),
        "2025_q4": EntityQuarterProfile(
            alert_count=240, fast_closure_rate=0.58, no_escalation_rate=0.68, template_notes_rate=0.39
        ),
        "2026_q1": EntityQuarterProfile(
            alert_count=245, fast_closure_rate=0.40, no_escalation_rate=0.45, template_notes_rate=0.30
        ),
        # Partial remediation, not disappearance — Kaveri should still read
        # as a mildly elevated, recently-improved entity in Q2, not as a
        # clean baseline. Rates left well above zero (vs. an earlier
        # near-total remediation to ~0.08-0.12, which put its blended score
        # below most baselines and read as the detector having stopped
        # looking rather than as a fix).
        "2026_q2": EntityQuarterProfile(
            alert_count=250, fast_closure_rate=0.42, no_escalation_rate=0.45, template_notes_rate=0.33
        ),
    },
    # Anomaly volume spike appearing only in Q1/Q2 — near-baseline volume
    # through Q4 (a hair above the 14 baselines' ~180-220/quarter band, like
    # execution_gap's Fortis-lesson: no other override needed), then a
    # sudden step-change that continues into Q2, converging on
    # generate_extended.py's 760-alert single-snapshot volume.
    "Arcadia Defence Systems": {
        "2025_q3": EntityQuarterProfile(alert_count=225),
        "2025_q4": EntityQuarterProfile(alert_count=235),
        "2026_q1": EntityQuarterProfile(alert_count=620),
        "2026_q2": EntityQuarterProfile(alert_count=760),
    },
    # Multi-feature drift building gradually across all four quarters:
    # closure time, escalation rate, critical ratio all climb together while
    # asset diversity narrows — no single rule catches it, converging on
    # generate_extended.py's Konkan profile (avg closure ~34,815s,
    # escalation ~0.59-0.81, critical ratio ~0.20-0.22, 3 asset types).
    "Konkan Maritime Ltd": {
        # Q3 is deliberately mild — close enough to baseline that it is not
        # yet the most anomalous entity that quarter (anomaly.py's Isolation
        # Forest output is rescaled *relative to peers*, so an entity that is
        # already the most-anomalous peer in Q3 saturates at 1.0 immediately
        # and cannot show gradual buildup — see README's "why Q3 starts mild"
        # note). Each subsequent quarter pushes closure time, escalation,
        # severity mix and asset diversity further from baseline.
        "2025_q3": EntityQuarterProfile(
            alert_count=190,
            severity_weights=[0.42, 0.30, 0.21, 0.07],
            assets=ASSET_TYPES,
            closure_range_minutes=(170, 270),
        ),
        "2025_q4": EntityQuarterProfile(
            alert_count=190,
            severity_weights=[0.38, 0.29, 0.22, 0.11],
            assets=["Server", "Identity Provider", "Cloud Workload", "Database", "Network Device", "Endpoint"],
            closure_range_minutes=(190, 300),
        ),
        "2026_q1": EntityQuarterProfile(
            alert_count=190,
            severity_weights=[0.30, 0.28, 0.26, 0.16],
            assets=["Server", "Identity Provider", "Cloud Workload", "Database"],
            closure_range_minutes=(280, 420),
            escalation_rate_override={"Critical": 0.72, "High": 0.60},
        ),
        "2026_q2": EntityQuarterProfile(
            alert_count=190,
            severity_weights=[0.22, 0.26, 0.30, 0.22],
            assets=["Server", "Identity Provider", "Cloud Workload"],
            closure_range_minutes=(433, 733),  # 26000-44000s
            escalation_rate_override={"Critical": 0.90, "High": 0.81},
        ),
    },
    # Stable missing-severity pattern throughout — flat but flagged, a
    # different signal from deteriorating: normal volume every quarter (so
    # LOW_ALERT_VOLUME never fires) but no high/critical severity at all in
    # any quarter, matching generate_extended.py's Nilgiri profile exactly.
    "Nilgiri Water Authority": {
        "2025_q3": EntityQuarterProfile(alert_count=170, severity_weights=[0.66, 0.34, 0.00, 0.00]),
        "2025_q4": EntityQuarterProfile(alert_count=178, severity_weights=[0.66, 0.34, 0.00, 0.00]),
        "2026_q1": EntityQuarterProfile(alert_count=172, severity_weights=[0.66, 0.34, 0.00, 0.00]),
        "2026_q2": EntityQuarterProfile(alert_count=175, severity_weights=[0.66, 0.34, 0.00, 0.00]),
    },
    # Oscillating — alternates between a mild quarter and a spike quarter so
    # it reads as volatile rather than trending in either direction. Spike
    # quarters land in the same range as generate_extended.py's Deccan
    # "deliberately ambiguous" snapshot (26.7% fast closure / 43% duplicated
    # notes); mild quarters sit close to baseline.
    "Deccan Health Network": {
        # Amplitude widened from an earlier mild<->spike swing (which stayed
        # under the trend classifier's volatility threshold and read as
        # "stable") so the oscillation is large enough to register as
        # genuinely volatile rather than merely quiet.
        "2025_q3": EntityQuarterProfile(
            alert_count=200, fast_closure_rate=0.04, no_escalation_rate=0.06, template_notes_rate=0.04
        ),
        "2025_q4": EntityQuarterProfile(
            alert_count=210, fast_closure_rate=0.55, no_escalation_rate=0.60, template_notes_rate=0.50
        ),
        "2026_q1": EntityQuarterProfile(
            alert_count=200, fast_closure_rate=0.05, no_escalation_rate=0.08, template_notes_rate=0.05
        ),
        "2026_q2": EntityQuarterProfile(
            alert_count=210, fast_closure_rate=0.52, no_escalation_rate=0.58, template_notes_rate=0.48
        ),
    },
}


def _normalized(weights: list[float]) -> np.ndarray:
    arr = np.array(weights, dtype=float)
    return arr / arr.sum()


def _noisy_count(base: int, rng: np.random.Generator) -> int:
    """Apply +/-BASELINE_NOISE_FRACTION multiplicative noise to a baseline count."""
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
    sev_weights = profile.severity_weights if profile.severity_weights is not None else NORMAL_SEVERITY_WEIGHTS
    severity = rng.choice(SEVERITIES, p=_normalized(sev_weights))
    asset_pool = profile.assets if profile.assets is not None else ASSET_TYPES
    asset_type = rng.choice(asset_pool)
    severity_lc = severity.lower()

    # --- closure duration ---
    fast_closure_rate = profile.fast_closure_rate
    is_fast_candidate = severity_lc in FAST_CLOSURE_SEVERITIES
    normal_range = profile.closure_range_minutes or (NORMAL_DURATION_MIN_MINUTES, NORMAL_DURATION_MAX_MINUTES)
    if is_fast_candidate and fast_closure_rate is not None and rng.random() < fast_closure_rate:
        duration_minutes = int(rng.integers(FAST_DURATION_MIN_MINUTES, FAST_DURATION_MAX_MINUTES + 1))
    else:
        duration_minutes = int(rng.integers(normal_range[0], normal_range[1] + 1))

    # --- escalation ---
    no_escalation_rate = profile.no_escalation_rate
    esc_override = profile.escalation_rate_override
    if severity_lc in NO_ESCALATION_OVERRIDE_SEVERITIES and no_escalation_rate is not None:
        escalated = rng.random() >= no_escalation_rate
    elif esc_override is not None and severity in esc_override:
        escalated = rng.random() < esc_override[severity]
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
        # independent and reproducible on its own). zlib.crc32 (not Python's
        # salted built-in hash()) so the derived seed is identical run to run.
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
