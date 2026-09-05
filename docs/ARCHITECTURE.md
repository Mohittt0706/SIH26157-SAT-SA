# SAT-SA — Architecture Document (SIH26157)

## 1. Problem & Approach
NCIIPC needs to identify which organizations perform SOC work only for show (performative
compliance) from structured alert/case exports, without questionnaires or self-reporting.
SAT-SA ingests CSV/JSON SOC alert data from multiple entities, runs three independent
detectors per entity, and combines them into one auditable risk score — fully offline.

## 2. Solution Architecture
```
CSV/JSON upload → FastAPI ingestion → SQLite (alerts table)
                                          │
                    ┌─────────────────────┼─────────────────────┐
              execution_gap.py      negative_space.py       anomaly.py
              (rule-based)          (peer baseline)          (Isolation Forest)
                    └─────────────────────┼─────────────────────┘
                                    risk_score.py (weighted + soft floor)
                                          │
                         GET /api/risk-scores, /api/entities/{name}
                                          │
                    React dashboard → drill-down → supervisory review
```
Three-tier: React 18/Vite frontend (charts only) → FastAPI backend (all computation) →
SQLite (local, offline). Detectors share one contract — `compute_<name>(db) ->
{entity: {score, metrics, evidence}}` — so `risk_score.py` combines them without
touching internals. A CSV-only path mirrors every detector for the CLI/demo and
independent validation, with no database required.

## 3. Functional Design
- **Execution Gap** (`execution_gap.py`) — did work *look* done but wasn't:
  - `FAST_CLOSURE`: critical/high alerts closed under `FAST_CLOSURE_THRESHOLD_SECONDS=300`.
  - `NO_ESCALATION`: critical alerts never escalated.
  - `TEMPLATE_NOTES`: notes empty, `< MIN_NOTE_LENGTH=20` chars, or verbatim-duplicated
    (`MIN_DUPLICATE_MULTIPLICITY=5`) at a rate `≥ TEMPLATE_DUPLICATE_Z_THRESHOLD=1.0`
    modified z-scores above the peer median duplication rate.
  - Combined: `score = min(1, 0.4·fast_closure_rate + 0.3·no_escalation_rate + 0.3·template_notes_rate)`.
- **Negative Space** (`negative_space.py`) — expected activity that's absent:
  - `LOW_ALERT_VOLUME`: entity alert count z-score `≤ LOW_VOLUME_Z_THRESHOLD = -1.0` vs peers.
  - `MISSING_EXPECTED_SEVERITY`: a severity present for `≥ MIN_PEERS_WITH_SEVERITY=2` peers
    but absent for this entity.
  - Combined: `score = 0.6·low_volume_signal + 0.4·missing_severity_signal` (each signal
    is a 0/1 trigger or a fraction of missing expected severities).
- **Anomaly** (`anomaly.py`) — Isolation Forest over a 6-feature vector per entity
  (`alert_count, avg_closure_seconds, escalation_rate, critical_ratio, avg_note_length,
  unique_asset_types`), `StandardScaler`-normalized. `decision_function` output is
  inverted and min-max rescaled to `[0,1]` (1.0 = most anomalous in the batch).
- Every rule score is a graded ramp, not a hard cutoff — deliberately, so an entity does
  not read as clean up to a threshold and maximally guilty just past it.
- Every detector returns `evidence`: concrete `alert_id`s or peer-comparison strings a
  jury can verify against the raw CSV. `risk_score.py` merges up to
  `MAX_MERGED_EVIDENCE=8` items, tagged by source, highest-scoring detector first.

## 4. Peer-Baseline Methodology (median/MAD)
All peer comparisons use the **median** and **MAD** (median absolute deviation) with a
modified z-score, not mean/standard deviation:
```
modified_z = 0.6745 × (x − peer_median) / peer_MAD      (MAD_ZSCORE_SCALE = 0.6745,
                                                           the 75th percentile of N(0,1))
```
Rationale: with only ~10 entities, one outlier inflates a standard deviation enough to
mask a real signal; median and MAD are robust to that single outlier. Applied uniformly
across all three detectors — anomaly feature attribution, the execution-gap
template-duplication check, and `negative_space`'s `LOW_ALERT_VOLUME` rule. A zero-MAD
peer group (all peers identical) falls back to a ±1.0 sign comparison rather than
dividing by zero.

## 5. Risk Score Combination — Soft Floor
```
weighted_sum = 0.40·execution_gap + 0.35·negative_space + 0.25·anomaly
floor        = max(execution_gap, negative_space, anomaly) × FLOOR_ATTENUATION(0.85)
combined     = clip(max(weighted_sum, floor), 0, 1)
risk_score   = round(combined × 100, 1)
```
A pure weighted average silently dilutes an entity that trips one detector hard while the
other two sit near zero (e.g. Delta Rail: 0/0.80/1.00 → weighted average only 0.53). An
earlier version applied the floor only when a raw score exceeded 0.70, producing a cliff:
two entities 0.016 apart in raw score (0.727 vs 0.684) landed 31 risk-score points apart.
The continuous soft floor removes that cliff at the cost of also lifting some low,
single-detector scores partway toward their raw value. `risk_band` (critical ≥70,
high ≥45, medium ≥20, low below) is an investigative priority ranking, not a verdict —
an entity can sit at "medium" with no named finding (only a sub-threshold anomaly signal),
which is the tool correctly surfacing borderline signal for human review, not a false
positive. `FINDING_SUMMARY_THRESHOLD=0.30` gates which detectors count as having
"meaningfully fired" in the dashboard/drill-down, since anomaly reports its top-3 deviant
features unconditionally regardless of magnitude.

## 6. Validation Methodology & Result
The synthetic dataset (639 alerts, 10 entities) has 4 entities with intentionally seeded
suspicious patterns (2 execution-gap, 1 negative-space, 1 anomaly-spike) and 6 normal
baseline entities, mapped in a gitignored, internal-only answer key never exposed to the
detectors or dashboard. `validation/validator.py` independently: (a) checks dataset
integrity (row/entity counts, duplicate IDs, timestamps, valid severity/escalated
values); (b) recomputes the risk-score formula from `/api/entities/{name}` component
scores and diffs it against the API's `risk_score` (tolerance 0.11); (c) re-runs
Isolation Forest across 5 random seeds to confirm top-3 ranking stability independent of
`random_state`; (d) traces execution-gap evidence `alert_id`s back to the raw CSV.
**Result: all 4 seeded entities rank in the top 4 by risk_score** — Delta Rail Systems
85.0 (critical), Indus Financial Services 61.8 (high), Continental Banking Corp 58.2
(high), Fortis Defense Systems 44.8 (medium) — verified against the held-out answer key.
The remaining 6 entities scored low, except Ganga Oil & Gas (25.4), which lands at
"medium" on anomaly signal alone with no named finding — correctly flagging borderline
deviation for review rather than a rule violation.

## 7. ML Details (Section 5 requirements)
- **Model architecture**: `sklearn.ensemble.IsolationForest`, unsupervised, one 6-D
  feature vector per entity. No deep learning — the dataset is too small for DL to
  generalize and DL would be a black box, failing the explainability requirement.
- **Hyperparameters**: `n_estimators=200`, `contamination=0.2`, `random_state=42` (fixed,
  for deterministic demo output). Selected from 5 compared configurations by top-3
  ranking stability across 5 random seeds — used in place of accuracy/precision/recall,
  which are not meaningful for an unlabeled 10-entity cohort.
- **Hardware**: CPU-only; verified on Windows 11 Home, 8 GB system RAM (3.7 GB allocated
  to Docker), 4 CPUs — full containerised image build completes in 8.3s. A 10-entity ×
  6-feature fit trains in well under a second; no GPU needed.
- **Offline training/inference**: no persisted model artifact — every request refits
  `StandardScaler` + `IsolationForest` from scratch on the uploaded dataset
  (`_fit_and_score`), since a model saved from one dataset's scale would answer "unusual
  vs. a stale prior dataset," not "unusual within this upload."
- **Model update mechanism**: none needed — refit-on-every-upload replaces retraining.
  Hyperparameters are named constants in `anomaly.py`, changed and re-validated manually
  via the 5-seed stability check, not tuned online.
- **Explainability controls**: raw scores are never shown alone — every entity's evidence
  lists its top `MAX_EVIDENCE_ITEMS=3` most deviant features against the peer
  median/MAD in plain language (e.g. "Entity is 30.75 modified z-scores below the peer
  median for avg_closure_seconds"), verifiable without understanding tree isolation.
- **Auditability controls**: every score traces to concrete evidence — anomaly to named
  features with entity value/peer median/MAD; execution-gap to specific `alert_id`s;
  negative-space to observed-vs-peer-mean counts. `validator.py` independently re-derives
  the combined formula and cross-checks evidence `alert_id`s against the source CSV.
  Every upload additionally persists an `AssessmentRun` audit record — timestamp, source
  filename and format, ingestion counts (rows received/inserted/skipped, entity count), a
  full snapshot of every detector constant in force for that run (`detector_config`), and
  the resulting per-entity scores (`results_snapshot`) — retrievable via
  `GET /api/audit/runs` and `GET /api/audit/runs/{run_id}`. Because the config snapshot is
  taken alongside a fixed `random_state`, any historical run is exactly reproducible from
  its audit record alone.

## 8. Data & Infrastructure Requirements
- **Input**: CSV/JSON with `alert_id, entity_name, severity, created_time, closed_time,
  escalated, investigation_notes, asset_type` (composite key `(entity_name, alert_id)`,
  since each company's `alert_id` series is independent). At least ~2 peer entities are
  needed for a peer-baseline rule to have a nonzero MAD/stdev.
- **Backend**: Python + FastAPI + SQLAlchemy, SQLite file storage (`backend/data/`,
  gitignored), scikit-learn/numpy/pandas. No external services, no network calls at
  runtime (CORS scoped to localhost/127.0.0.1 only).
- **Frontend**: React 18 + Vite, built as static assets served by nginx.
- **Deployment**: Docker Compose, two services — `backend` (FastAPI on :8000, named
  volume `satsa_db` for SQLite persistence) and `frontend` (nginx on :80, proxying
  `/api/` to `backend` so the browser only talks to one origin). Fully self-contained;
  runs on an air-gapped machine with only Docker installed.

## 9. Differentiation
Existing tools (SOC-CMM, Microsoft Security Self-Assessment, Thales SOC Maturity
Assessment) are questionnaire-based self-assessments. SAT-SA is automated and
evidence-based over actual operational data, removing self-reporting bias.
