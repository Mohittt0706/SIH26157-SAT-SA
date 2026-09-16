# SAT-SA — Architecture Document (SIH26157)

## 1. Problem & Approach
NCIIPC needs to identify which organizations perform SOC work only for show, from
structured alert/case exports, without questionnaires or self-reporting. SAT-SA ingests
CSV/JSON/SQLite SOC alert data from multiple entities, runs three independent detectors
per entity, and combines them into one auditable risk score — fully offline.

## 2. Solution Architecture
```
CSV/JSON/SQLite upload → FastAPI ingestion → SQLite (alerts table)
                                          │
                    ┌─────────────────────┼─────────────────────┐
              execution_gap.py      negative_space.py       anomaly.py
              (rule-based)          (peer baseline)          (Isolation Forest)
                    └─────────────────────┼─────────────────────┘
                                    risk_score.py (weighted + soft floor)
                                          │
        ┌────────────────┬───────────────┼───────────────┬──────────────────┐
  sample_priority.py  expected_observed.py  trend history   manual_review.py
  (alert ranking)     (peer benchmark)   (AssessmentRun)   (blind human review)
        └────────────────┴───────────────┼───────────────┴──────────────────┘
        React dashboard → drill-down → audit trail → client-side report export
```
Three-tier: React 18/Vite frontend (charts + client-side PDF/JSON/CSV export, no
computation) → FastAPI backend (all computation) → SQLite (local, offline). Detectors
share one contract — `compute_<name>(db) -> {entity: {score, metrics, evidence}}` — so
`risk_score.py` combines them without touching internals. A CSV-only path mirrors every
detector for the CLI/demo and independent validation, with no database required.

## 3. Functional Design
- **Execution Gap** (`execution_gap.py`) — did work *look* done but wasn't:
  `FAST_CLOSURE` (critical/high closed <`300s`), `NO_ESCALATION` (critical never
  escalated), `TEMPLATE_NOTES` (empty, `<20` chars, or verbatim-duplicated `≥5×` at a
  rate `≥1.0` modified z-scores above the peer median). Combined:
  `score = min(1, 0.4·fast_closure + 0.3·no_escalation + 0.3·template_notes)`.
- **Negative Space** (`negative_space.py`) — expected activity that's absent:
  `LOW_ALERT_VOLUME` (alert-count z-score, graded ramp from `-1.0` to saturation at
  `-5.0`), `MISSING_EXPECTED_SEVERITY` (a severity present for `≥2` peers, absent here).
  Combined: `score = 0.6·low_volume + 0.4·missing_severity`.
- **Anomaly** (`anomaly.py`) — Isolation Forest over a 6-feature vector per entity
  (`alert_count, avg_closure_seconds, escalation_rate, critical_ratio, avg_note_length,
  unique_asset_types`), `StandardScaler`-normalized, `decision_function` inverted and
  min-max rescaled to `[0,1]` per batch (1.0 = most anomalous in that run).
- Every rule score is a graded ramp, not a hard cutoff, and every detector returns
  `evidence` — concrete `alert_id`s or peer-comparison strings a jury can verify against
  the raw CSV. `risk_score.py` merges up to 8 items, highest-scoring detector first.

## 4. Peer-Baseline Methodology (median/MAD)
All peer comparisons use **median/MAD** with a modified z-score, not mean/stdev:
`modified_z = 0.6745 × (x − peer_median) / peer_MAD` (0.6745 = 75th percentile of
N(0,1)). With ~10-20 entities, one outlier inflates a standard deviation enough to mask
a real signal; median/MAD is robust to that outlier. Applied uniformly across anomaly
feature attribution, execution-gap's template-duplication check, negative-space's
`LOW_ALERT_VOLUME`, and expected-vs-observed (§5). A zero-MAD peer group falls back to a
±1.0 sign comparison rather than dividing by zero.

## 5. Risk Score Combination & Supervisory Features
```
weighted_sum = 0.40·execution_gap + 0.35·negative_space + 0.25·anomaly
floor        = max(execution_gap, negative_space, anomaly) × 0.85
risk_score   = round(clip(max(weighted_sum, floor), 0, 1) × 100, 1)
```
A pure weighted average dilutes an entity that trips one detector hard while the other
two sit near zero; the soft floor removes the resulting cliff without a hard threshold.
`risk_band` (critical ≥70, high ≥45, medium ≥20, low below) is an investigative
priority, not a verdict.

Four features sit on top of the combined score:
- **Alert sample prioritization** (`sample_priority.py`, req. #10) — a flat,
  cross-entity ranked list of *individual alerts* for a supervisor to sample, weighted
  `0.45·rule_citation_count + 0.35·entity_risk + 0.20·severity`. Honestly scoped: only
  `execution_gap`'s evidence cites concrete `alert_id`s (`FAST_CLOSURE`/`NO_ESCALATION`/
  `TEMPLATE_NOTES` hits); `negative_space` and `anomaly` findings are entity-level or
  feature-level by nature and cannot nominate an individual alert without misrepresenting
  what was actually found.
- **Temporal trend analysis** (`GET /api/trends`, req. #16) — least-squares regression
  of `risk_score` against run index across every `AssessmentRun` snapshot for an entity,
  classified `deteriorating`/`improving`/`volatile`/`stable` by slope (>±5.0 pts/run) and
  population-stdev volatility (>15.0 pts) — volatility catches a dip-and-recover series a
  first-vs-last comparison would misread as flat. Validated against four quarterly
  datasets (`dataset/periods/`) seeding one deteriorating, one improving (partial
  remediation), one Q1/Q2-only volume spike, and one oscillating/volatile entity across
  Q3'25–Q2'26; all four read the intended direction (see that folder's README for the
  full per-quarter answer key).
- **Expected vs. observed** (`expected_observed.py`, part of entity drill-down) — for
  every one of the six anomaly features, restates entity value vs. peer median (MAD
  deviation) as a plain-language sentence (e.g. "30.75 modified z-scores below peer
  median"), reusing anomaly.py's own peer-median/MAD helpers rather than a second
  implementation. A presentation layer only — it feeds no score.
- **Blind manual review** (`manual_review.py`, answers §8's independent-validation
  requirement) — a supervisor sees only raw evidence (`GET
  /manual-review/{entity}/evidence`: alert counts, closure times, escalation rate, notes
  — never a score, band, driver, or peer comparison) and submits their own verdict
  (`POST /manual-review`) *before* `GET .../comparison` reveals VEIL's output and an
  agreement check across concern/priority/recommendation. Reviews are append-only
  (history preserved, never overwritten); `GET /manual-review/metrics` aggregates
  agreement rates across every submitted review.
- **Report export** — PDF/JSON/CSV, generated entirely client-side
  (`frontend/src/lib/assessmentReport.js` + `pdfReportBuilder.js`) from data the
  dashboard/drill-down already fetched — no new backend endpoint, no extra network
  exposure. Full detail is assembled only for flagged (high/critical) entities to keep a
  multi-hundred-entity report readable; every missing field renders as an explicit
  "Not available" sentinel, never blank or fabricated.

## 6. Validation Methodology & Result
The primary dataset (`dataset/soc_alerts_extended.csv`, 4,667 alerts, 21 entities) has 7
entities with intentionally seeded suspicious patterns (2 execution-gap, 2
negative-space, 2 anomaly, 1 borderline-mild) and 14 normal baselines, mapped in a
gitignored, internal-only answer key never exposed to the detectors or dashboard.
`backend/validation_outputs/` independently: (a) checks dataset integrity (row/entity
counts, duplicate IDs, timestamps, valid severity/escalated values); (b) recomputes the
risk-score formula from `/api/entities/{name}` component scores and diffs it against
the API's `risk_score`; (c) re-runs Isolation Forest across multiple random seeds to
confirm ranking stability independent of `random_state`; (d) traces execution-gap
evidence `alert_id`s back to the raw CSV. **Result: all 7 seeded entities rank in the
top 7 of 21 by `risk_score`** — Konkan Maritime Ltd 85.0 (critical), Meridian Trust Bank
82.5 (critical), Saraswati Rail Network 69.4 (high), Kaveri Power Holdings 47.1 (high),
Arcadia Defence Systems 40.1 (medium), Deccan Health Network 32.0 (medium), Nilgiri
Water Authority 24.6 (medium) — every baseline entity scored ≤15.9. The original
639-alert/10-entity dataset remains available as a secondary demo (4/4 seeded entities
in the top 4, unchanged). Trend-direction validation (§5) is a separate, independent
check against the same detectors run across time.

## 7. ML Details (Section 5 requirements)
- **Model architecture**: `sklearn.ensemble.IsolationForest`, unsupervised, one 6-D
  feature vector per entity. No deep learning — too small a dataset to generalize, and
  DL would be a black box, failing the explainability requirement.
- **Hyperparameters**: `n_estimators=200`, `contamination=0.2`, `random_state=42`
  (fixed, deterministic). Selected from 5 compared configurations by top-N ranking
  stability across 5 random seeds — used in place of accuracy/precision/recall, not
  meaningful for an unlabeled cohort.
- **Hardware**: CPU-only; verified on Windows 11 Home, 8 GB RAM, 4 CPUs. A 21-entity ×
  6-feature fit trains in well under a second; no GPU needed.
- **Offline training/inference**: no persisted model artifact — every request refits
  `StandardScaler` + `IsolationForest` from scratch on the uploaded dataset, since a
  model saved from one dataset's scale would answer "unusual vs. a stale prior dataset."
- **Model update mechanism**: none needed — refit-on-every-upload replaces retraining.
  Hyperparameters are named constants, changed and re-validated manually.
- **Explainability controls**: every entity's evidence lists its top-3 most deviant
  features against peer median/MAD in plain language, verifiable without understanding
  tree isolation — the same mechanism §5's expected-vs-observed feature exposes for
  *every* metric, not just the top 3.
- **Auditability controls**: every score traces to concrete evidence — anomaly to named
  features, execution-gap to specific `alert_id`s, negative-space to observed-vs-peer
  counts. Every upload persists an `AssessmentRun` audit record (timestamp, source
  filename/format, ingestion counts, full detector-constant snapshot, resulting scores)
  via `GET /api/audit/runs`, exactly reproducible from its own record. 85 automated
  tests (`pytest backend/tests/ -v`) cover all three detectors, the risk-score combiner,
  trend direction, alert prioritization, the blind manual-review workflow, and
  CSV/JSON/SQLite ingestion.

## 8. Data & Infrastructure Requirements
- **Input** (req. #2): CSV, JSON (top-level array or `{"alerts": [...]}`), or a SQLite
  `.db`/`.sqlite` export — opened read-only, searched for a table named `alerts` or any
  table whose columns are a superset of the required 8 (`alert_id, entity_name,
  severity, created_time, closed_time, escalated, investigation_notes, asset_type`;
  composite key `(entity_name, alert_id)`). All three formats funnel through one
  validation/normalization pipeline before insertion. At least ~2 peer entities are
  needed for a peer-baseline rule to have a nonzero MAD/stdev.
- **Backend**: Python + FastAPI + SQLAlchemy, SQLite file storage, scikit-learn/numpy/
  pandas. No external services, no network calls at runtime (CORS scoped to
  localhost/127.0.0.1 only).
- **Frontend**: React 18 + Vite, static assets served by nginx.
- **Deployment**: Docker Compose — `backend` (FastAPI on :8000, named volume for SQLite
  persistence) and `frontend` (nginx on :80, proxying `/api/`). Fully self-contained;
  runs on an air-gapped machine with only Docker installed.

## 9. Differentiation
Existing tools (SOC-CMM, Microsoft Security Self-Assessment, Thales SOC Maturity
Assessment) are questionnaire-based self-assessments. SAT-SA is automated,
evidence-based, and cross-validated against independent blind human review.
