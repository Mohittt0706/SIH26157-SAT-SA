"""Pipeline performance benchmark — measures each stage at increasing scale.

Generates synthetic SOC alert data using the same schema and categorical
value distributions as ``dataset/soc_alerts_synthetic_dataset.csv`` (severity,
category, asset_type frequencies; the escalated-by-severity correlation; the
closure-duration range; the fixed pool of canned investigation notes), at
four sizes, and measures — separately, for each size — the time taken by:

  - ingestion   (CSV parse + normalize + DB insert, mirroring
                 app.routers.ingestion._process_dataframe's normalize/insert
                 path, without also re-running the detectors it triggers for
                 the AssessmentRun audit snapshot)
  - each detector individually (execution_gap, negative_space, anomaly)
  - risk_score aggregation alone (the _combine_entity/sort step — NOT
                 including a second run of the three detectors, since
                 compute_risk_scores() normally reruns them internally)
  - total end-to-end wall time (sum of the phases above, timed as one
                 continuous run so nothing is double-counted)
  - peak process RSS (whole-process memory via psutil, sampled every 20ms)

Each size is run three times against a fresh scratch SQLite database (never
backend/data/satsa.db); the reported figure is the median of the three runs.
If a size does not complete within RUN_TIMEOUT_SECONDS it is skipped and
reported as such — no number for that size is invented or extrapolated.

Usage: python benchmark.py [--sizes 639/10,5000/50,...] [--runs 3]
"""

from __future__ import annotations

import argparse
import csv as csv_mod
import gc
import io
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import Base  # noqa: E402
from app.models import Alert  # noqa: E402
from app.analytics.execution_gap import compute_execution_gap  # noqa: E402
from app.analytics.negative_space import compute_negative_space  # noqa: E402
from app.analytics.anomaly import compute_anomaly  # noqa: E402
from app.analytics.risk_score import _combine_entity, _EMPTY_DETECTOR_RESULT  # noqa: E402

# ---------------------------------------------------------------------------
# Benchmark configuration
# ---------------------------------------------------------------------------

DEFAULT_SIZES: list[tuple[int, int]] = [
    (639, 10),
    (5_000, 50),
    (25_000, 100),
    (100_000, 250),
]
"""(alert_count, entity_count) pairs, matching the sizes requested."""

RUNS_PER_SIZE: int = 3

RUN_TIMEOUT_SECONDS: float = 1800.0
"""Abort a single run (not the whole size) if any one phase exceeds this."""

MEMORY_SAMPLE_INTERVAL_SECONDS: float = 0.02

SCRATCH_DIR: Path = Path(__file__).resolve().parent / "data" / "benchmark_scratch"

OUT_DIR: Path = Path(__file__).resolve().parent.parent / "docs"
BENCHMARK_MD: Path = OUT_DIR / "BENCHMARK.md"
BENCHMARK_CSV: Path = OUT_DIR / "benchmark_raw.csv"

GEN_SEED: int = 20260101
"""Fixed seed so the same size always generates the same synthetic dataset
across the three repeated runs — repeats measure pipeline variance, not
data variance."""

# ---------------------------------------------------------------------------
# Synthetic data generation — same schema/value pools as the real CSV
# ---------------------------------------------------------------------------

SEVERITIES: list[str] = ["Low", "Medium", "High", "Critical"]
SEVERITY_WEIGHTS: list[float] = [0.372457, 0.316119, 0.181534, 0.129890]
"""Observed proportions in dataset/soc_alerts_synthetic_dataset.csv."""

CATEGORIES: list[str] = [
    "Phishing",
    "Unauthorized Access",
    "Data Exfiltration Attempt",
    "Malware",
    "Misconfiguration",
    "Insider Threat Indicator",
    "DDoS",
]
CATEGORY_WEIGHTS: list[float] = [
    0.156495, 0.150235, 0.147105, 0.143975, 0.140845, 0.134585, 0.126761,
]

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
"""Observed P(escalated=Yes | severity) in the real dataset."""

INVESTIGATION_NOTES: list[str] = [
    "Correlated with SIEM logs across 3 hosts, identified lateral movement attempt, escalated.",
    "Reviewed and closed.",
    "No further action required.",
    "Investigated source IP, confirmed malicious signature, blocked at firewall, root cause documented.",
    "Performed forensic triage on affected host, isolated system, initiated containment protocol.",
    "Closed as per standard procedure.",
    "False positive.",
    "Cross-referenced with threat intel feed, identified C2 communication pattern, escalated to IR team.",
]
"""The fixed 8-note pool the real dataset draws from verbatim."""

CLOSURE_DURATION_MIN_MINUTES: int = 1
CLOSURE_DURATION_MAX_MINUTES: int = 598
"""Observed min/max closure_duration_minutes in the real dataset."""

DATASET_START: datetime = datetime(2026, 1, 1, 19, 48, 0)
DATASET_SPAN_DAYS: int = 180
"""Real dataset spans 2026-01-01 to 2026-06-30 — roughly 180 days."""

_ENTITY_ADJECTIVES = [
    "Apex", "Bharat", "Continental", "Delta", "Eastern", "Fortis", "Ganga",
    "Himalayan", "Indus", "Jupiter", "Kestrel", "Lumen", "Meridian", "Nimbus",
    "Orion", "Pinnacle", "Quantum", "Redwood", "Summit", "Titan", "Union",
    "Vertex", "Westgate", "Xenon", "Yeager", "Zenith",
]
_ENTITY_NOUNS = [
    "Financial Services", "Power Grid", "Water Utility", "Rail Systems",
    "Defense Systems", "Oil & Gas", "Telecom Networks", "Healthcare Network",
    "Aviation Control", "Banking Corp", "Logistics", "Retail Group",
    "Manufacturing Co", "Insurance Group", "Energy Holdings",
]


def _make_entity_names(n: int, rng: np.random.Generator) -> list[str]:
    """Generate *n* distinct plausible SOC-customer entity names."""
    pairs = [(a, b) for a in _ENTITY_ADJECTIVES for b in _ENTITY_NOUNS]
    rng.shuffle(pairs)
    if n <= len(pairs):
        chosen = pairs[:n]
        return [f"{a} {b}" for a, b in chosen]
    # More entities than the adjective x noun product offers: extend with a
    # numeric suffix, still deterministic under the fixed seed.
    names = [f"{a} {b}" for a, b in pairs]
    idx = 0
    while len(names) < n:
        a, b = pairs[idx % len(pairs)]
        names.append(f"{a} {b} {idx // len(pairs) + 2}")
        idx += 1
    return names[:n]


def generate_synthetic_csv(alert_count: int, entity_count: int, seed: int = GEN_SEED) -> bytes:
    """Build a synthetic alert CSV (as bytes) with the real dataset's schema and value pools.

    Column set matches dataset/soc_alerts_synthetic_dataset.csv exactly:
    alert_id, entity_name, severity, category, asset_type, created_time,
    closed_time, closure_duration_minutes, escalated, status,
    investigation_notes.

    Entities are assigned per-alert by uniform random draw (not evenly
    bucketed) — the same organic-imbalance pattern the real dataset shows
    (Fortis Defense Systems: 166 alerts vs Delta Rail Systems: 3, out of 639).
    Every categorical field is drawn independently from the frequency
    weights observed in the real CSV; escalation is drawn conditional on
    severity using the real per-severity escalation rate.
    """
    rng = np.random.default_rng(seed)
    entity_names = _make_entity_names(entity_count, rng)

    def _normalized(weights: list[float]) -> np.ndarray:
        arr = np.array(weights, dtype=float)
        return arr / arr.sum()

    entities = rng.choice(entity_names, size=alert_count)
    severities = rng.choice(SEVERITIES, size=alert_count, p=_normalized(SEVERITY_WEIGHTS))
    categories = rng.choice(CATEGORIES, size=alert_count, p=_normalized(CATEGORY_WEIGHTS))
    asset_types = rng.choice(ASSET_TYPES, size=alert_count, p=_normalized(ASSET_TYPE_WEIGHTS))
    notes = rng.choice(INVESTIGATION_NOTES, size=alert_count)

    escalation_probs = np.array([ESCALATION_RATE_BY_SEVERITY[s] for s in severities])
    escalated_draw = rng.random(alert_count) < escalation_probs
    escalated = np.where(escalated_draw, "Yes", "No")

    offsets_minutes = rng.integers(0, DATASET_SPAN_DAYS * 24 * 60, size=alert_count)
    created_times = [DATASET_START + timedelta(minutes=int(m)) for m in offsets_minutes]

    durations = rng.integers(
        CLOSURE_DURATION_MIN_MINUTES, CLOSURE_DURATION_MAX_MINUTES + 1, size=alert_count
    )
    closed_times = [ct + timedelta(minutes=int(d)) for ct, d in zip(created_times, durations)]

    # alert_id restarts per entity, matching the real dataset's convention
    # (each company's own export numbers its own alerts from 1).
    per_entity_counter: dict[str, int] = {}
    alert_ids = []
    for ent in entities:
        per_entity_counter[ent] = per_entity_counter.get(ent, 0) + 1
        alert_ids.append(f"ALT{per_entity_counter[ent]:05d}")

    buf = io.StringIO()
    writer = csv_mod.writer(buf)
    writer.writerow(
        [
            "alert_id", "entity_name", "severity", "category", "asset_type",
            "created_time", "closed_time", "closure_duration_minutes",
            "escalated", "status", "investigation_notes",
        ]
    )
    fmt = "%Y-%m-%d %H:%M:%S"
    for i in range(alert_count):
        writer.writerow(
            [
                alert_ids[i],
                entities[i],
                severities[i],
                categories[i],
                asset_types[i],
                created_times[i].strftime(fmt),
                closed_times[i].strftime(fmt),
                int(durations[i]),
                escalated[i],
                "Closed",
                notes[i],
            ]
        )
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# Ingestion (mirrors app.routers.ingestion._process_dataframe's normalize +
# insert path, WITHOUT the AssessmentRun/detector-snapshot step — that would
# silently re-run all three detectors inside "ingestion time").
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS: list[str] = [
    "alert_id", "entity_name", "severity", "created_time", "closed_time",
    "escalated", "investigation_notes", "asset_type",
]
TRUE_VALUES = {"yes", "true", "1"}


def _parse_escalated(value: object) -> bool:
    if pd.isna(value):
        return False
    return str(value).strip().lower() in TRUE_VALUES


def _clean_notes(value: object):
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _clean_required_str(value: object):
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def ingest_csv_bytes(raw: bytes, db) -> int:
    """Parse, normalize, and insert *raw* CSV bytes into *db*. Returns row count.

    Logic mirrors app.routers.ingestion._process_dataframe's normalize/dedup/
    insert steps exactly (entity_name is already unique per-generated-row
    here, so no canonicalization collisions are expected, but the same
    per-column cleaning functions are reused for a faithful comparison).
    """
    df = pd.read_csv(io.BytesIO(raw))

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")

    df["alert_id"] = df["alert_id"].apply(_clean_required_str)
    df["entity_name"] = df["entity_name"].apply(_clean_required_str)
    df["severity"] = df["severity"].apply(lambda v: str(v).strip().lower() if pd.notna(v) else "")
    df["escalated"] = df["escalated"].apply(_parse_escalated)
    df["created_time"] = pd.to_datetime(df["created_time"], errors="coerce")
    df["closed_time"] = pd.to_datetime(df["closed_time"], errors="coerce")
    df["investigation_notes"] = df["investigation_notes"].apply(_clean_notes)
    df["asset_type"] = df["asset_type"].apply(lambda v: str(v).strip() if pd.notna(v) else "")

    invalid_mask = df["alert_id"].isna() | df["entity_name"].isna() | df["created_time"].isna()
    df_valid = df.loc[~invalid_mask].copy()

    duplicate_mask = df_valid.duplicated(subset=["entity_name", "alert_id"], keep="first")
    df_clean = df_valid.loc[~duplicate_mask].copy()

    alerts = [
        Alert(
            alert_id=row.alert_id,
            entity_name=row.entity_name,
            severity=row.severity,
            created_time=row.created_time.to_pydatetime(),
            closed_time=row.closed_time.to_pydatetime() if pd.notna(row.closed_time) else None,
            escalated=bool(row.escalated),
            investigation_notes=row.investigation_notes,
            asset_type=row.asset_type,
        )
        for row in df_clean.itertuples(index=False)
    ]

    db.query(Alert).delete()
    db.bulk_save_objects(alerts)
    db.commit()
    return len(alerts)


# ---------------------------------------------------------------------------
# Memory sampling
# ---------------------------------------------------------------------------

class _PeakRSSSampler:
    """Samples the current process's RSS on a background thread; tracks the max."""

    def __init__(self, interval_seconds: float = MEMORY_SAMPLE_INTERVAL_SECONDS) -> None:
        self._interval = interval_seconds
        self._process = psutil.Process()
        self._peak_bytes = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            rss = self._process.memory_info().rss
            if rss > self._peak_bytes:
                self._peak_bytes = rss
            self._stop_event.wait(self._interval)

    def __enter__(self) -> "_PeakRSSSampler":
        self._peak_bytes = self._process.memory_info().rss
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    @property
    def peak_bytes(self) -> int:
        return self._peak_bytes


# ---------------------------------------------------------------------------
# Single-run measurement
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    ingestion_s: float
    execution_gap_s: float
    negative_space_s: float
    anomaly_s: float
    risk_aggregation_s: float
    total_s: float
    peak_rss_bytes: int
    rows_inserted: int
    error: str | None = None


def _scratch_db_path(alert_count: int, entity_count: int, run_idx: int) -> Path:
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    return SCRATCH_DIR / f"bench_{alert_count}_{entity_count}_{run_idx}.db"


def run_once(csv_bytes: bytes, alert_count: int, entity_count: int, run_idx: int) -> RunResult:
    """Run ingestion -> detectors -> risk aggregation once against a fresh scratch DB."""
    db_path = _scratch_db_path(alert_count, entity_count, run_idx)
    if db_path.exists():
        db_path.unlink()

    engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    gc.collect()

    try:
        with _PeakRSSSampler() as sampler:
            t_start = time.perf_counter()

            t0 = time.perf_counter()
            rows_inserted = ingest_csv_bytes(csv_bytes, db)
            t1 = time.perf_counter()
            ingestion_s = t1 - t0

            t0 = time.perf_counter()
            eg_results = compute_execution_gap(db)
            t1 = time.perf_counter()
            execution_gap_s = t1 - t0

            t0 = time.perf_counter()
            ns_results = compute_negative_space(db)
            t1 = time.perf_counter()
            negative_space_s = t1 - t0

            t0 = time.perf_counter()
            an_results = compute_anomaly(db)
            t1 = time.perf_counter()
            anomaly_s = t1 - t0

            t0 = time.perf_counter()
            entity_names = set(eg_results) | set(ns_results) | set(an_results)
            rows = [
                _combine_entity(
                    name,
                    eg_results.get(name, _EMPTY_DETECTOR_RESULT),
                    ns_results.get(name, _EMPTY_DETECTOR_RESULT),
                    an_results.get(name, _EMPTY_DETECTOR_RESULT),
                )
                for name in entity_names
            ]
            rows.sort(key=lambda row: row["risk_score"], reverse=True)
            t1 = time.perf_counter()
            risk_aggregation_s = t1 - t0

            t_end = time.perf_counter()

        return RunResult(
            ingestion_s=ingestion_s,
            execution_gap_s=execution_gap_s,
            negative_space_s=negative_space_s,
            anomaly_s=anomaly_s,
            risk_aggregation_s=risk_aggregation_s,
            total_s=t_end - t_start,
            peak_rss_bytes=sampler.peak_bytes,
            rows_inserted=rows_inserted,
        )
    finally:
        db.close()
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

@dataclass
class SizeResult:
    alert_count: int
    entity_count: int
    runs: list[RunResult] = field(default_factory=list)
    skipped_reason: str | None = None


def run_size(alert_count: int, entity_count: int, runs: int) -> SizeResult:
    print(f"\n=== {alert_count:,} alerts / {entity_count} entities ===", flush=True)
    print("  generating synthetic dataset...", flush=True)
    t0 = time.perf_counter()
    csv_bytes = generate_synthetic_csv(alert_count, entity_count)
    print(f"  generated {len(csv_bytes) / 1e6:.1f} MB in {time.perf_counter() - t0:.1f}s", flush=True)

    result = SizeResult(alert_count=alert_count, entity_count=entity_count)

    for run_idx in range(runs):
        print(f"  run {run_idx + 1}/{runs}...", flush=True)
        t0 = time.perf_counter()
        try:
            r = run_once(csv_bytes, alert_count, entity_count, run_idx)
        except Exception as exc:  # noqa: BLE001 — report and move on
            elapsed = time.perf_counter() - t0
            print(f"    FAILED after {elapsed:.1f}s: {exc}", flush=True)
            result.skipped_reason = f"run {run_idx + 1} failed after {elapsed:.1f}s: {exc}"
            return result
        elapsed = time.perf_counter() - t0
        if elapsed > RUN_TIMEOUT_SECONDS:
            print(f"    exceeded {RUN_TIMEOUT_SECONDS:.0f}s budget ({elapsed:.1f}s) — stopping this size", flush=True)
            result.runs.append(r)
            result.skipped_reason = (
                f"run {run_idx + 1} took {elapsed:.1f}s, over the {RUN_TIMEOUT_SECONDS:.0f}s "
                f"per-run budget; no further runs attempted at this size"
            )
            return result
        print(
            f"    total={r.total_s:.2f}s "
            f"(ingest={r.ingestion_s:.2f}s, exec_gap={r.execution_gap_s:.2f}s, "
            f"neg_space={r.negative_space_s:.2f}s, anomaly={r.anomaly_s:.2f}s, "
            f"risk_agg={r.risk_aggregation_s:.3f}s) "
            f"peak_rss={r.peak_rss_bytes / 1e6:.1f}MB",
            flush=True,
        )
        result.runs.append(r)

    return result


def _median(values: list[float]) -> float:
    return statistics.median(values)


def summarize(results: list[SizeResult]) -> list[dict]:
    """Build one row per size: median of each measured field across completed runs."""
    rows = []
    for res in results:
        if not res.runs:
            rows.append(
                {
                    "alert_count": res.alert_count,
                    "entity_count": res.entity_count,
                    "runs_completed": 0,
                    "status": f"SKIPPED: {res.skipped_reason}",
                }
            )
            continue

        row = {
            "alert_count": res.alert_count,
            "entity_count": res.entity_count,
            "runs_completed": len(res.runs),
            "status": "ok" if res.skipped_reason is None else f"PARTIAL: {res.skipped_reason}",
            "ingestion_s_median": _median([r.ingestion_s for r in res.runs]),
            "execution_gap_s_median": _median([r.execution_gap_s for r in res.runs]),
            "negative_space_s_median": _median([r.negative_space_s for r in res.runs]),
            "anomaly_s_median": _median([r.anomaly_s for r in res.runs]),
            "risk_aggregation_s_median": _median([r.risk_aggregation_s for r in res.runs]),
            "total_s_median": _median([r.total_s for r in res.runs]),
            "peak_rss_mb_median": _median([r.peak_rss_bytes / 1e6 for r in res.runs]),
        }
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_raw_csv(results: list[SizeResult], path: Path) -> None:
    """One row per individual run (not just the median) for charting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv_mod.writer(fh)
        writer.writerow(
            [
                "alert_count", "entity_count", "run_index",
                "ingestion_s", "execution_gap_s", "negative_space_s",
                "anomaly_s", "risk_aggregation_s", "total_s", "peak_rss_mb",
                "rows_inserted",
            ]
        )
        for res in results:
            for idx, r in enumerate(res.runs):
                writer.writerow(
                    [
                        res.alert_count, res.entity_count, idx,
                        f"{r.ingestion_s:.6f}", f"{r.execution_gap_s:.6f}",
                        f"{r.negative_space_s:.6f}", f"{r.anomaly_s:.6f}",
                        f"{r.risk_aggregation_s:.6f}", f"{r.total_s:.6f}",
                        f"{r.peak_rss_bytes / 1e6:.3f}", r.rows_inserted,
                    ]
                )


def write_markdown(summary_rows: list[dict], path: Path, runs_requested: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Pipeline Performance Benchmark",
        "",
        (
            "Measured on this machine, using synthetic data generated with the same "
            "schema and per-field value distributions as "
            "`dataset/soc_alerts_synthetic_dataset.csv` (see `backend/benchmark.py` "
            "for the exact generation code). Each size ran "
            f"{runs_requested} times against a fresh scratch SQLite database "
            "(never `backend/data/satsa.db`); figures below are the **median** "
            "of the completed runs. All numbers are measured directly — none are "
            "extrapolated or estimated."
        ),
        "",
        (
            "`risk_score aggregation` is the `_combine_entity` + sort step alone — "
            "it does **not** include a second run of the three detectors, even "
            "though `compute_risk_scores()` normally reruns them internally. "
            "`total` is one continuous timed run covering ingestion through "
            "aggregation, so it is not simply the sum of the columns rounded "
            "differently, but it should be close to their sum."
        ),
        "",
        "| Alerts | Entities | Runs completed | Ingestion (s) | Execution Gap (s) | Negative Space (s) | Anomaly (s) | Risk Aggregation (s) | Total (s) | Peak RSS (MB) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for row in summary_rows:
        if row["runs_completed"] == 0:
            lines.append(
                f"| {row['alert_count']:,} | {row['entity_count']} | 0 | — | — | — | — | — | — | — | "
                f"**{row['status']}** |"
            )
            continue
        status_suffix = "" if row["status"] == "ok" else f" ⚠️ {row['status']}"
        lines.append(
            f"| {row['alert_count']:,} | {row['entity_count']} | {row['runs_completed']}/{runs_requested} | "
            f"{row['ingestion_s_median']:.3f} | {row['execution_gap_s_median']:.3f} | "
            f"{row['negative_space_s_median']:.3f} | {row['anomaly_s_median']:.3f} | "
            f"{row['risk_aggregation_s_median']:.4f} | {row['total_s_median']:.3f} | "
            f"{row['peak_rss_mb_median']:.1f}{status_suffix} |"
        )

    lines += [
        "",
        "## Notes",
        "",
        "- Peak RSS is whole-process resident memory sampled every "
        f"{MEMORY_SAMPLE_INTERVAL_SECONDS * 1000:.0f}ms via `psutil` during "
        "ingestion + all three detectors + aggregation for that run; it "
        "includes the Python interpreter and every loaded library, not just "
        "the data itself.",
        "- A ⚠️ row completed fewer than the requested number of runs, or one "
        "run exceeded the per-run time budget; its median is computed only "
        "from the runs that did complete, and the reason is given verbatim.",
        "- Raw per-run figures (not just the medians here) are in "
        "`docs/benchmark_raw.csv`.",
        "",
    ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_sizes(spec: str) -> list[tuple[int, int]]:
    sizes = []
    for part in spec.split(","):
        alerts_str, entities_str = part.split("/")
        sizes.append((int(alerts_str), int(entities_str)))
    return sizes


def main() -> None:
    parser = argparse.ArgumentParser(description="SAT-SA pipeline performance benchmark")
    parser.add_argument(
        "--sizes",
        type=str,
        default=None,
        help="Comma-separated alert_count/entity_count pairs, e.g. '639/10,5000/50'.",
    )
    parser.add_argument("--runs", type=int, default=RUNS_PER_SIZE, help="Runs per size (median reported).")
    args = parser.parse_args()

    sizes = _parse_sizes(args.sizes) if args.sizes else DEFAULT_SIZES

    results: list[SizeResult] = []
    for alert_count, entity_count in sizes:
        res = run_size(alert_count, entity_count, args.runs)
        results.append(res)
        if res.skipped_reason and not res.runs:
            print(f"  size skipped entirely: {res.skipped_reason}", flush=True)

    summary_rows = summarize(results)

    write_raw_csv(results, BENCHMARK_CSV)
    write_markdown(summary_rows, BENCHMARK_MD, runs_requested=args.runs)

    print(f"\nWrote {BENCHMARK_MD}")
    print(f"Wrote {BENCHMARK_CSV}")

    if SCRATCH_DIR.exists():
        try:
            SCRATCH_DIR.rmdir()
        except OSError:
            pass  # leftover files from a failed run — leave them for inspection


if __name__ == "__main__":
    main()
