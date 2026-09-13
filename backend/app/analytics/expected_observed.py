"""Expected-vs-observed comparison — per-entity metrics against a peer baseline.

A presentation layer, not a detector. For every entity it restates the same
six features the anomaly detector already builds (see ``FEATURE_NAMES`` in
anomaly.py) as a plain-language comparison: what this entity does, what
comparable entities do, and how far apart those two numbers are.

Nothing here feeds a score. The peer median/MAD machinery is imported from
anomaly.py rather than reimplemented — ``_peer_median`` / ``_peer_mad`` there
are already metric-agnostic (they exclude one index from a value list), so
this module adds no third implementation of the same statistic.

Every comparison excludes the entity itself from its own baseline, matching
the convention in anomaly.py and negative_space.py.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.anomaly import (
    MAD_ZSCORE_SCALE,
    _peer_mad,
    _peer_median,
    extract_entity_features,
)
from app.models import Alert

# ---------------------------------------------------------------------------
# Tunable thresholds
# ---------------------------------------------------------------------------

EXPECTED_ALIGNED_Z_THRESHOLD: float = 1.0
"""Absolute modified z-score below which a metric is reported as "aligned".

Without a dead band every metric reads as a deviation, because a peer median
is almost never hit exactly — an entity a hair off the median would be
labelled "below", making a wholly normal profile look like six small
findings. Metrics inside this band are normal, and say so.
"""

# Metric units, used verbatim in the ``unit`` field.
UNIT_SECONDS: str = "seconds"
UNIT_RATIO: str = "ratio"
UNIT_COUNT: str = "count"
UNIT_CHARS: str = "chars"

# Direction labels.
DIRECTION_BELOW: str = "below"
DIRECTION_ABOVE: str = "above"
DIRECTION_ALIGNED: str = "aligned"

SECONDS_PER_HOUR: float = 3600.0

HOURS_READABILITY_CUTOFF: float = SECONDS_PER_HOUR
"""Second values at or above this are also phrased in hours in the sentence,
because "14400 seconds" does not land the way "4.0 hours" does."""

# ---------------------------------------------------------------------------
# Metric catalogue
# ---------------------------------------------------------------------------

METRIC_LABELS: dict[str, str] = {
    "avg_closure_seconds": "Average closure time",
    "escalation_rate": "Escalation rate",
    "critical_ratio": "Critical severity share",
    "avg_note_length": "Average investigation note length",
    "alert_count": "Alert volume",
    "unique_asset_types": "Distinct asset types covered",
}
"""Human label per metric key, in the order comparisons are returned."""

METRIC_UNITS: dict[str, str] = {
    "avg_closure_seconds": UNIT_SECONDS,
    "escalation_rate": UNIT_RATIO,
    "critical_ratio": UNIT_RATIO,
    "avg_note_length": UNIT_CHARS,
    "alert_count": UNIT_COUNT,
    "unique_asset_types": UNIT_COUNT,
}
"""Unit per metric key. Mirrors the keys of METRIC_LABELS exactly."""

METRIC_KEYS: list[str] = list(METRIC_LABELS)
"""Comparison order — deliberately leads with closure time, the metric a
reviewer reads first."""


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_seconds(value: float) -> str:
    """Render a second count for prose, adding an hours reading when large.

    Values below :data:`HOURS_READABILITY_CUTOFF` stay in seconds; above it
    the hours figure is what a reader actually reasons about.
    """
    if value >= HOURS_READABILITY_CUTOFF:
        return f"about {value / SECONDS_PER_HOUR:.1f} hours"
    return f"{value:.0f} seconds"


def _fmt_ratio(value: float) -> str:
    """Render a 0–1 ratio as a percentage, which reads more naturally in prose."""
    return f"{value * 100:.0f}%"


def _fmt_count(value: float) -> str:
    """Render a count, dropping the decimal point when the value is whole."""
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


def _fmt_chars(value: float) -> str:
    """Render an average character length."""
    return f"{value:.0f} characters"


def _fmt_value(metric_key: str, value: float) -> str:
    """Format *value* for prose according to *metric_key*'s unit."""
    unit = METRIC_UNITS[metric_key]
    if unit == UNIT_SECONDS:
        return _fmt_seconds(value)
    if unit == UNIT_RATIO:
        return _fmt_ratio(value)
    if unit == UNIT_CHARS:
        return _fmt_chars(value)
    return _fmt_count(value)


# ---------------------------------------------------------------------------
# Interpretation sentences
# ---------------------------------------------------------------------------

_SENTENCE_TEMPLATES: dict[str, str] = {
    "avg_closure_seconds": "Closes alerts in {observed} on average, where comparable SOCs take {expected}.",
    "escalation_rate": "Escalates {observed} of its alerts, where comparable SOCs escalate {expected}.",
    "critical_ratio": "Logs {observed} of its alerts as critical severity, where comparable SOCs log {expected}.",
    "avg_note_length": "Writes investigation notes averaging {observed}, where comparable SOCs write {expected}.",
    "alert_count": "Reported {observed} alerts, where comparable SOCs reported {expected}.",
    "unique_asset_types": "Raised alerts across {observed} distinct asset types, where comparable SOCs cover {expected}.",
}
"""One sentence per metric, each naming the observed value then the peer
value. Phrased so it stands alone without the surrounding numbers or any
statistical vocabulary — no z-scores, no "median", no "MAD"."""


def _build_interpretation(
    metric_key: str,
    observed: float,
    expected: float,
    direction: str,
) -> str:
    """Compose the plain-language sentence for one metric comparison.

    Always contains both numbers. Aligned metrics get a short clause saying so,
    rather than a bare pair of numbers the reader has to judge for themselves.
    """
    sentence = _SENTENCE_TEMPLATES[metric_key].format(
        observed=_fmt_value(metric_key, observed),
        expected=_fmt_value(metric_key, expected),
    )

    if direction == DIRECTION_ALIGNED:
        return f"{sentence} This is in line with its peers."
    return sentence


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _direction(deviation_z: float) -> str:
    """Classify a modified z-score as below, above, or aligned with peers."""
    if abs(deviation_z) < EXPECTED_ALIGNED_Z_THRESHOLD:
        return DIRECTION_ALIGNED
    return DIRECTION_ABOVE if deviation_z > 0 else DIRECTION_BELOW


def _modified_z(value: float, median: float, mad: float) -> float:
    """MAD-based modified z-score of *value*, with the shared zero-MAD fallback.

    When every peer holds the same value there is no spread to normalise by,
    so the result collapses to ±1.0 (or 0.0 on an exact match) — the same
    fallback anomaly.py and negative_space.py use.
    """
    if mad == 0.0:
        if value == median:
            return 0.0
        return 1.0 if value > median else -1.0
    return MAD_ZSCORE_SCALE * (value - median) / mad


def _compare_entity(
    entity_idx: int,
    feature_vectors: list[dict[str, float]],
) -> list[dict]:
    """Build every metric comparison for the entity at *entity_idx*.

    Parameters
    ----------
    entity_idx:
        Index of the entity under review within *feature_vectors*.
    feature_vectors:
        Feature dicts for all entities, in a stable order.

    Returns
    -------
    list[dict]
        One comparison dict per key in :data:`METRIC_KEYS`, in that order.
    """
    own = feature_vectors[entity_idx]
    comparisons: list[dict] = []

    for metric_key in METRIC_KEYS:
        all_values = [fv[metric_key] for fv in feature_vectors]

        observed = float(own[metric_key])
        expected = _peer_median(all_values, exclude_idx=entity_idx)
        mad = _peer_mad(all_values, exclude_idx=entity_idx)
        deviation_z = _modified_z(observed, expected, mad)
        direction = _direction(deviation_z)

        comparisons.append(
            {
                "metric": METRIC_LABELS[metric_key],
                "metric_key": metric_key,
                "observed": round(observed, 2),
                "expected": round(float(expected), 2),
                "unit": METRIC_UNITS[metric_key],
                "deviation_z": round(deviation_z, 2),
                "direction": direction,
                "interpretation": _build_interpretation(
                    metric_key, observed, float(expected), direction
                ),
            }
        )

    return comparisons


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_expected_vs_observed(db: Session) -> dict[str, list[dict]]:
    """Compare every entity's metrics against a peer baseline that excludes it.

    Parameters
    ----------
    db:
        An open SQLAlchemy session pointing at the alerts table.

    Returns
    -------
    dict[str, list[dict]]
        Mapping of entity name → list of comparison dicts, each with the keys
        ``metric``, ``metric_key``, ``observed``, ``expected``, ``unit``,
        ``deviation_z``, ``direction`` and ``interpretation``. Empty when the
        alerts table holds no entities.
    """
    alerts = db.execute(select(Alert)).scalars().all()

    by_entity: dict[str, list[Alert]] = defaultdict(list)
    for alert in alerts:
        by_entity[alert.entity_name].append(alert)

    entity_names = sorted(by_entity)
    if not entity_names:
        return {}

    feature_vectors = [extract_entity_features(by_entity[name]) for name in entity_names]

    return {
        name: _compare_entity(idx, feature_vectors)
        for idx, name in enumerate(entity_names)
    }
