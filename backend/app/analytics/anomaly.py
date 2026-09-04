"""Anomaly detector — Isolation Forest on per-entity feature vectors.

Builds one feature vector per entity from the alerts table, scales with
StandardScaler, and fits an IsolationForest.  The raw decision_function
output is rescaled to a 0.0–1.0 score (higher = more anomalous) so it
is directly comparable to the negative_space and execution_gap scores
that feed the weighted risk_score combiner.

Explainability: for every entity, features are compared against the peer
MEDIAN using MAD (median absolute deviation) to resist outlier inflation.
The top 2–3 most deviant features are surfaced as human-readable evidence
so a jury member can understand *why* an entity was flagged without knowing
how Isolation Forest works.

Fully offline — no network calls, no external models.
"""

from __future__ import annotations

import joblib
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert

# ---------------------------------------------------------------------------
# Tunable hyperparameters
# ---------------------------------------------------------------------------

IFOREST_RANDOM_STATE: int = 42
"""Deterministic seed so the demo produces identical output every run."""

IFOREST_CONTAMINATION: float = 0.2 
"""Expected fraction of anomalous entities in the training set."""

IFOREST_N_ESTIMATORS: int = 200
"""Number of trees in the forest."""

MAX_EVIDENCE_ITEMS: int = 3
"""Maximum number of deviant features surfaced in the evidence list."""

MAD_ZSCORE_SCALE: float = 0.6745
"""Scale factor converting MAD to a std-equivalent z-score.
0.6745 = 75th-percentile of the standard normal."""

# Feature names kept as a module-level list for consistent ordering.
FEATURE_NAMES: list[str] = [
    "alert_count",
    "avg_closure_seconds",
    "escalation_rate",
    "critical_ratio",
    "avg_note_length",
    "unique_asset_types",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AnomalyResult:
    """Anomaly outcome for a single entity."""

    entity_name: str
    score: float
    metrics: dict[str, float]
    evidence: list[dict[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

def _extract_features(alerts: list[Alert | _CsvAlert]) -> dict[str, float]:
    """Compute the six-feature vector for one entity's alerts.

    Returns a dict with keys matching ``FEATURE_NAMES``.
    """
    total = len(alerts)

    # 1. alert_count
    alert_count = float(total)

    # 2. avg_closure_seconds — exclude open alerts (closure_seconds is None)
    closure_vals = [
        a.closure_seconds for a in alerts
        if a.closure_seconds is not None
    ]
    avg_closure_seconds = statistics.mean(closure_vals) if closure_vals else 0.0

    # 3. escalation_rate
    escalated_count = sum(1 for a in alerts if a.escalated)
    escalation_rate = escalated_count / total if total else 0.0

    # 4. critical_ratio
    critical_count = sum(1 for a in alerts if a.severity and a.severity.lower() == "critical")
    critical_ratio = critical_count / total if total else 0.0

    # 5. avg_note_length — None notes count as length 0
    note_lengths = [
        len(a.investigation_notes) if a.investigation_notes else 0
        for a in alerts
    ]
    avg_note_length = statistics.mean(note_lengths) if note_lengths else 0.0

    # 6. unique_asset_types
    unique_asset_types = float(len({a.asset_type for a in alerts if a.asset_type and a.asset_type.strip()}))

    return {
        "alert_count": alert_count,
        "avg_closure_seconds": avg_closure_seconds,
        "escalation_rate": escalation_rate,
        "critical_ratio": critical_ratio,
        "avg_note_length": avg_note_length,
        "unique_asset_types": unique_asset_types,
    }


def extract_entity_features(alerts: list[Alert | _CsvAlert]) -> dict[str, float]:
    """Public API for extracting the six-feature vector for an entity's alerts."""
    return _extract_features(alerts)


def extract_features_from_csv(csv_path: str | Path) -> dict[str, dict[str, float]]:
    """Extract entity-level six-feature vectors directly from a CSV file."""
    import csv as csv_mod
    from pathlib import Path
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(f"CSV file not found: {p}")

    alerts_data: list[dict[str, str]] = []
    with open(p, newline="", encoding="utf-8") as fh:
        reader = csv_mod.DictReader(fh)
        for row in reader:
            alerts_data.append(row)

    by_entity: dict[str, list[_CsvAlert]] = defaultdict(list)
    for row in alerts_data:
        entity = row.get("entity_name", "").strip()
        if entity:
            by_entity[entity].append(_CsvAlert(row))

    return {
        entity: _extract_features(alerts)
        for entity, alerts in sorted(by_entity.items())
    }



# ---------------------------------------------------------------------------
# Peer baseline helpers (median + MAD)
# ---------------------------------------------------------------------------

def _peer_median(values: list[float], exclude_idx: int | None = None) -> float:
    """Median of *values*, optionally excluding one index."""
    peers = [v for i, v in enumerate(values) if i != exclude_idx]
    return statistics.median(peers) if peers else 0.0


def _peer_mad(values: list[float], exclude_idx: int | None = None) -> float:
    """MAD of *values*, optionally excluding one index.

    MAD = median(|x_i - median|).
    Returns 0.0 when fewer than 2 peers exist to avoid division-by-zero.
    """
    peers = [v for i, v in enumerate(values) if i != exclude_idx]
    if len(peers) < 2:
        return 0.0
    med = statistics.median(peers)
    abs_devs = [abs(v - med) for v in peers]
    return statistics.median(abs_devs)


# ---------------------------------------------------------------------------
# Score conversion
# ---------------------------------------------------------------------------

def _convert_scores(raw_scores: np.ndarray) -> np.ndarray:
    """Map IsolationForest decision_function outputs to 0.0–1.0.

    ``decision_function`` returns higher values for *normal* points and
    lower (more negative) values for anomalies.  We invert and min-max
    rescale so that the most anomalous entity gets 1.0 and the least
    anomalous gets 0.0.

    Returns an array of floats in [0.0, 1.0] with the same length as
    *raw_scores*.
    """
    # Invert: more negative → higher anomaly score.
    inverted = -raw_scores
    min_val = float(inverted.min())
    max_val = float(inverted.max())
    spread = max_val - min_val

    if spread == 0.0:
        return np.zeros_like(inverted, dtype=float)

    return (inverted - min_val) / spread


# ---------------------------------------------------------------------------
# Evidence generation
# ---------------------------------------------------------------------------

def _build_evidence(
    feature_vector: dict[str, float],
    entity_idx: int,
    all_feature_vectors: list[dict[str, float]],
    entity_names: list[str],
) -> list[dict[str, str]]:
    """Produce human-readable evidence for one entity.

    Compares every feature against the peer median using MAD-based
    modified z-scores and surfaces the top ``MAX_EVIDENCE_ITEMS``
    most deviant features with concrete numbers.
    """
    deviations: list[tuple[str, float, float, float, float]] = []

    for feat in FEATURE_NAMES:
        entity_val = feature_vector[feat]
        all_vals = [fv[feat] for fv in all_feature_vectors]
        med = _peer_median(all_vals, exclude_idx=entity_idx)
        mad = _peer_mad(all_vals, exclude_idx=entity_idx)

        if mad == 0.0:
            # All peers identical — no meaningful spread.
            z = 0.0 if entity_val == med else (1.0 if entity_val > med else -1.0)
        else:
            z = MAD_ZSCORE_SCALE * (entity_val - med) / mad

        deviations.append((feat, entity_val, med, mad, z))

    # Sort by absolute z-score descending — most deviant first.
    deviations.sort(key=lambda t: abs(t[4]), reverse=True)

    evidence: list[dict[str, str]] = []
    for feat, entity_val, med, mad, z in deviations[:MAX_EVIDENCE_ITEMS]:
        detail = (
            f"{feat} = {_fmt(entity_val)} "
            f"(peer median = {_fmt(med)}, MAD = {_fmt(mad)})"
        )
        direction = "above" if z > 0 else "below"
        reason = (
            f"Entity is {abs(z):.2f} modified z-scores {direction} the peer "
            f"median for {feat}."
        )
        evidence.append({"detail": detail, "reason": reason})

    return evidence


def _fmt(val: float) -> str:
    """Format a float for human-readable evidence output."""
    if val == int(val):
        return str(int(val))
    return f"{val:.1f}"


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _compute_anomaly_matrix(
    by_entity: dict[str, list[Alert]],
) -> dict[str, AnomalyResult]:
    """Fit IsolationForest on the entity×feature matrix and return results.

    This is the internal implementation shared by the DB and CLI paths.
    """
    entity_names = sorted(by_entity.keys())

    if not entity_names:
        return {}

    # Build feature matrix — one row per entity, columns in FEATURE_NAMES order.
    feature_vectors: list[dict[str, float]] = []
    for name in entity_names:
        feature_vectors.append(_extract_features(by_entity[name]))

    X = np.array([[fv[f] for f in FEATURE_NAMES] for fv in feature_vectors])

    # Scale features so that alert_count (hundreds) doesn't dominate
    # escalation_rate (0–1).
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Fit Isolation Forest.
    clf = IsolationForest(
        random_state=IFOREST_RANDOM_STATE,
        contamination=IFOREST_CONTAMINATION,
        n_estimators=IFOREST_N_ESTIMATORS,
    )
    raw_scores = clf.fit(X_scaled).decision_function(X_scaled)
    joblib.dump(
       {
           "model": clf,
           "scaler": scaler,
           "feature_names": FEATURE_NAMES,
       },
       "anomaly_model.joblib",
   )

    # Convert to 0.0–1.0 (higher = more anomalous).
    converted = _convert_scores(raw_scores)

    results: dict[str, AnomalyResult] = {}
    for i, name in enumerate(entity_names):
        score = float(converted[i])
        metrics = {feat: round(float(X[i][j]), 2) for j, feat in enumerate(FEATURE_NAMES)}
        evidence = _build_evidence(feature_vectors[i], i, feature_vectors, entity_names)

        results[name] = AnomalyResult(
            entity_name=name,
            score=round(score, 3),
            metrics=metrics,
            evidence=evidence,
        )

    return results


# ---------------------------------------------------------------------------
# Model Persistence & Inference APIs (Step 1.2)
# ---------------------------------------------------------------------------

def save_anomaly_model(
    scaler: StandardScaler,
    clf: IsolationForest,
    feature_vectors: list[dict[str, float]],
    entity_names: list[str],
    artifact_path: str | Path,
) -> str:
    """Persist fitted StandardScaler and IsolationForest ensemble to a joblib artifact."""
    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    model_dict = {
        "scaler": scaler,
        "clf": clf,
        "feature_names": FEATURE_NAMES,
        "training_feature_vectors": feature_vectors,
        "training_entities": entity_names,
        "hyperparameters": {
            "n_estimators": getattr(clf, "n_estimators", 200),
            "contamination": getattr(clf, "contamination", 0.2),
            "random_state": getattr(clf, "random_state", 42),
        },
    }
    joblib.dump(model_dict, path)
    return str(path.resolve())


def load_anomaly_model(artifact_path: str | Path) -> dict:
    """Load persisted anomaly model dictionary from a joblib artifact."""
    path = Path(artifact_path)
    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found at {path}")
    model_dict = joblib.load(path)
    if "scaler" not in model_dict or "clf" not in model_dict:
        raise ValueError(f"Invalid model artifact structure in {path}")
    return model_dict


def train_synthetic_model(
    synthetic_csv_path: str | Path,
    artifact_path: str | Path,
) -> dict[str, AnomalyResult]:
    """Train Isolation Forest on synthetic features and persist anomaly_model.joblib."""
    syn_features = extract_features_from_csv(synthetic_csv_path)
    entity_names = sorted(syn_features.keys())
    feature_vectors = [syn_features[name] for name in entity_names]

    X = np.array([[fv[f] for f in FEATURE_NAMES] for fv in feature_vectors])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    clf = IsolationForest(
        random_state=IFOREST_RANDOM_STATE,
        contamination=IFOREST_CONTAMINATION,
        n_estimators=IFOREST_N_ESTIMATORS,
    )
    raw_scores = clf.fit(X_scaled).decision_function(X_scaled)

    save_anomaly_model(scaler, clf, feature_vectors, entity_names, artifact_path)

    converted = _convert_scores(raw_scores)

    results: dict[str, AnomalyResult] = {}
    for i, name in enumerate(entity_names):
        score = float(converted[i])
        metrics = {feat: round(float(X[i][j]), 2) for j, feat in enumerate(FEATURE_NAMES)}
        evidence = _build_evidence(feature_vectors[i], i, feature_vectors, entity_names)

        results[name] = AnomalyResult(
            entity_name=name,
            score=round(score, 3),
            metrics=metrics,
            evidence=evidence,
        )

    return results


def predict_anomaly(
    features_by_entity: dict[str, dict[str, float]],
    artifact_path: str | Path,
) -> dict[str, AnomalyResult]:
    """Execute inference on entity feature vectors using a loaded joblib model artifact.

    Transforms input features using the PRE-FITTED scaler without retraining,
    calculates Isolation Forest decision_function scores, and computes MAD evidence.
    """
    model_dict = load_anomaly_model(artifact_path)
    scaler: StandardScaler = model_dict["scaler"]
    clf: IsolationForest = model_dict["clf"]
    expected_features: list[str] = model_dict.get("feature_names", FEATURE_NAMES)

    entity_names = sorted(features_by_entity.keys())
    if not entity_names:
        return {}

    feature_vectors: list[dict[str, float]] = []
    for name in entity_names:
        fv = features_by_entity[name]
        for feat in expected_features:
            if feat not in fv:
                raise KeyError(f"Feature '{feat}' missing for entity '{name}'")
            val = fv[feat]
            if not isinstance(val, (int, float)) or (isinstance(val, float) and np.isnan(val)):
                raise ValueError(f"Invalid/NaN feature value for '{name}.{feat}': {val}")
        feature_vectors.append(fv)

    X = np.array([[fv[f] for f in expected_features] for fv in feature_vectors])

    # Transform ONLY using fitted scaler — DO NOT FIT!
    X_scaled = scaler.transform(X)

    # Decision function from fitted Isolation Forest
    raw_scores = clf.decision_function(X_scaled)
    converted = _convert_scores(raw_scores)

    results: dict[str, AnomalyResult] = {}
    for i, name in enumerate(entity_names):
        score = float(converted[i])
        metrics = {feat: round(float(X[i][j]), 2) for j, feat in enumerate(expected_features)}
        evidence = _build_evidence(feature_vectors[i], i, feature_vectors, entity_names)

        results[name] = AnomalyResult(
            entity_name=name,
            score=round(score, 3),
            metrics=metrics,
            evidence=evidence,
        )

    return results


# ---------------------------------------------------------------------------
# Public API — integrates with SQLAlchemy (matches negative_space.py pattern)
# ---------------------------------------------------------------------------


def compute_anomaly(db: Session) -> dict[str, dict]:
    """Compute Isolation Forest anomaly scores for every entity.

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
    alerts = db.execute(select(Alert)).scalars().all()

    by_entity: dict[str, list[Alert]] = defaultdict(list)
    for alert in alerts:
        by_entity[alert.entity_name].append(alert)

    objects = _compute_anomaly_matrix(by_entity)
    return {entity_name: _to_contract_dict(result) for entity_name, result in objects.items()}


def _to_contract_dict(result: AnomalyResult) -> dict:
    """Serialize an AnomalyResult into the shared detector contract shape."""
    return {
        "score": result.score,
        "metrics": result.metrics,
        "evidence": result.evidence,
    }


# ---------------------------------------------------------------------------
# CLI standalone runner
# ---------------------------------------------------------------------------

def _run_cli() -> None:
    """Standalone CLI entry-point for development and demo."""
    import argparse
    import csv
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="SAT-SA Anomaly detector (CLI)")
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

    # ---- Mode 1: Read from CSV directly ----
    if args.csv:
        csv_path = Path(args.csv)
        if not csv_path.exists():
            print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
            sys.exit(1)
        _run_from_csv(csv_path)
        return

    # ---- Mode 2: Read from SQLite DB ----
    db_path = (
        Path(args.db)
        if args.db
        else Path(__file__).resolve().parent.parent.parent / "data" / "satsa.db"
    )
    if not db_path.exists():
        print(
            f"Error: Database not found at {db_path}\n"
            "  Use --csv <path> to run from a CSV file, or upload data via the API first.",
            file=sys.stderr,
        )
        sys.exit(1)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        alerts = db.execute(select(Alert)).scalars().all()
        by_entity: dict[str, list[Alert]] = defaultdict(list)
        for alert in alerts:
            by_entity[alert.entity_name].append(alert)
        results = _compute_anomaly_matrix(by_entity)
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

    # Group by entity — build lightweight Alert-like objects.
    by_entity: dict[str, list[_CsvAlert]] = defaultdict(list)
    for row in alerts_data:
        by_entity[row["entity_name"]].append(_CsvAlert(row))

    results = _compute_anomaly_matrix(by_entity)  # type: ignore[arg-type]
    _print_results(results)


class _CsvAlert:
    """Lightweight stand-in for an Alert ORM object, built from a CSV row."""

    def __init__(self, row: dict[str, str]) -> None:
        self.alert_id: str = row.get("alert_id", "").strip()
        self.entity_name: str = row.get("entity_name", "").strip()
        self.severity: str = row.get("severity", "").strip()
        self.escalated: bool = row.get("escalated", "").strip().lower() in ("yes", "true", "1")
        self.investigation_notes: str | None = row.get("investigation_notes") if row.get("investigation_notes") else None
        self.asset_type: str = row.get("asset_type", "").strip()

        # 1. Check direct closure_duration_minutes from CSV row
        dur_str = row.get("closure_duration_minutes", "").strip()
        self._csv_closure_seconds: float | None = None
        if dur_str:
            try:
                val = float(dur_str)
                if val >= 0:
                    self._csv_closure_seconds = val * 60.0
            except ValueError:
                pass

        # 2. Parse timestamps flexibly
        ct = row.get("created_time", "").strip()
        clt = row.get("closed_time", "").strip()
        self.created_time = _parse_dt(ct)
        self.closed_time = _parse_dt(clt)

    @property
    def closure_seconds(self) -> float | None:
        if self._csv_closure_seconds is not None:
            return self._csv_closure_seconds
        if self.created_time is None or self.closed_time is None:
            return None
        diff = (self.closed_time - self.created_time).total_seconds()
        return diff if diff >= 0 else None


def _parse_dt(dt_str: str):
    """Parse datetime string with format fallback."""
    from datetime import datetime
    if not dt_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            pass
    return None



def _print_results(results: dict[str, AnomalyResult]) -> None:
    """Pretty-print results to stdout for CLI / demo use."""
    print("\n===== SAT-SA ANOMALY DETECTION RESULTS =====\n")

    for entity_name in sorted(results):
        r = results[entity_name]
        print(f"[{entity_name}]")
        print(f"   Anomaly Score : {r.score:.3f}")
        print(f"   Metrics       : {r.metrics}")
        if r.evidence:
            print("   Evidence:")
            for item in r.evidence:
                print(f"      -> {item['detail']}")
                print(f"         {item['reason']}")
        else:
            print("   Evidence:")
            print("      No significant anomaly signal detected.")
    print()


if __name__ == "__main__":
    _run_cli()
