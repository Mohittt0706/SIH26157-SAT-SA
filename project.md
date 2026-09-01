# project.md — SAT-SA Project Context

## Project
**SIH26157 — Supervisory Analytics Tool for SOC Assessment (SAT-SA)**
Smart India Hackathon 2026 | Sponsoring Org: NTRO | Theme: Miscellaneous

NCIIPC (govt cybersecurity body) needs a dashboard that analyzes structured SOC
alert/case data (CSV/JSON) from multiple companies and automatically identifies
which organizations are doing security work only for show — i.e. performative
compliance rather than genuine security operations.

## Hard constraints
- **Fully offline / air-gapped.** No internet calls, no cloud APIs, no external
  LLM dependency. All processing is local. Do not add any library or code path
  that requires network access at runtime.
- **Explainability is mandatory.** Every flag raised must show *why* it fired,
  with the supporting evidence rows. A jury will inspect this. No black-box output.
- Desktop web app (not mobile).

## The two core detections
1. **Execution Gap** — work looks done but isn't genuine.
   Signals: critical alerts closed in seconds, no escalation on criticals,
   template/empty investigation notes.
2. **Negative Space** — what *should* be happening but isn't.
   Signals: suspicious silence vs peer alert-volume baseline, missing telemetry,
   asset types that never generate alerts.

Supporting: **Isolation Forest anomaly detection** on per-company feature vectors,
and **peer percentile comparison**. All combined into a weighted risk score per entity.

## Tech stack (locked — do not swap)
- Frontend: React 18 + Vite + React Router v6 + Tailwind + Recharts + Lucide React + Axios.
  UI-only — all analytics and ML computation stays in the FastAPI backend.
  Page flow: Landing → Upload → Dashboard → DrillDown → Supervisory Review.
- Backend: Python + FastAPI
- DB: SQLite (local file, offline-compatible)
- ML: scikit-learn Isolation Forest
  (chosen over deep learning: too little data, DL is a black box which fails the
  explainability requirement, and DL is too heavy for a 1-week timeline)
- Deployment: Docker Compose

## Repo layout
```
SIH26157-SAT-SA/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry, CORS, router registration
│   │   ├── database.py          # SQLite/SQLAlchemy setup
│   │   ├── models.py            # Alert table model
│   │   ├── schemas.py           # Pydantic response schemas
│   │   ├── routers/
│   │   │   ├── ingestion.py     # POST /api/upload — CSV -> DB
│   │   │   └── analytics.py     # GET /api/risk-scores, GET /api/entities/{name}
│   │   └── analytics/
│   │       ├── execution_gap.py # Rule-based detector
│   │       ├── negative_space.py# Z-score baseline comparison across peers
│   │       ├── anomaly.py       # Isolation Forest
│   │       └── risk_score.py    # Weighted combination -> final score per entity
│   ├── requirements.txt
│   ├── data/                    # SQLite db file lands here (gitignored)
│   └── tests/
├── frontend/
├── dataset/
├── docs/
├── project.md
└── CLAUDE.md
```
project.md sits at the repo root alongside CLAUDE.md.

## Current status
- `database.py`, `models.py`, `schemas.py`, `main.py` — **done**
- `ingestion.py` — `POST /api/upload` — **done and verified**
  (639 rows inserted, 0 skipped, 10 entities)
- `execution_gap.py` — **done**
- `negative_space.py` — **done**, uses median/MAD robust baseline
  ⚠️ except its `LOW_ALERT_VOLUME` rule, which still uses mean/stdev
  (`build_peer_baseline()`) — needs updating to match the median/MAD
  convention below.
- `anomaly.py` — **done**, Isolation Forest with MAD-based feature attribution
- `risk_score.py` — **done**, weighted combination with a soft floor (see
  "Scoring decisions" below)
- analytics router — **done** (`GET /api/risk-scores`, `GET /api/entities/{entity_name}`)
- frontend, Docker, docs — **not started**

## Data schema (alert CSV)
`alert_id, entity_name, severity, created_time, closed_time, escalated (yes/no),
investigation_notes, asset_type`

Synthetic dataset: 639 alerts across 10 fake companies. 4 companies have
intentionally baked-in suspicious patterns (2 execution-gap, 1 negative-space,
1 anomaly-spike); 6 are normal baseline.

`dataset/answer_key_INTERNAL_ONLY.csv` maps which company is which — internal
testing only, gitignored, never submitted.

### Dataset
`dataset/soc_alerts_synthetic_dataset.csv` is committed to the repo — 639
alerts, 10 entities. The answer key is internal only and gitignored (see above).

## Detector contract
All three detectors are meant to share one return shape so `risk_score.py`
and the analytics router can combine them uniformly:

```
compute_<name>(db: Session) -> dict[str, dict]
```

Each value: `{"score": float 0.0-1.0 (higher = worse), "metrics": dict,
"evidence": list[{"detail": str, "reason": str}]}`.

⚠️ **Not yet consistent in code** — `risk_score.py` will need to normalize
these before combining:
- `execution_gap.py` returns `score` but no `metrics` dict (the three rule
  rates are separate fields), and `evidence` is `dict[str, list[RuleEvidence]]`
  keyed by rule name rather than a flat list.
- `negative_space.py` returns `negative_space_score` (not `score`), plus
  `metrics` and `evidence: list[Finding]` (fields: `type`, `detail`, `reason`).
- `anomaly.py` returns `score`, `metrics`, and `evidence: list[dict]` with
  `detail`/`reason` keys — the closest match to the target contract above.

## Statistical conventions
- Peer baselines use the **median** and **MAD** (median absolute deviation)
  with a modified z-score, not mean and standard deviation. With only 10
  entities, a single outlier inflates a standard deviation enough to suppress
  real signals; median/MAD is robust to that.
  Currently only `anomaly.py`'s evidence generation follows this
  (`MAD_ZSCORE_SCALE = 0.6745`) — see the gap noted above for
  `negative_space.py`.
- Rule scores are graded ramps between named threshold constants, not binary
  thresholds — an entity should not look clean right up to a hard cutoff and
  then suddenly read as maximally guilty.

## Scoring decisions
- **Weights**: `execution_gap` 0.40, `negative_space` 0.35, `anomaly` 0.25
  (must sum to 1.0).
- **Soft floor**: `final = max(weighted_sum, highest_raw_score * 0.85)`, no
  hard threshold. An earlier hard-threshold version (floor only applied above
  0.70) produced a cliff — two entities 0.016 apart in raw score landed 31
  risk-score points apart depending on which side of 0.70 they fell. The
  continuous soft floor removes that cliff at the cost of also lifting some
  low, single-detector scores partway toward their raw value.
- **`FINDING_SUMMARY_THRESHOLD = 0.30`** gates which detectors appear in
  `findings_summary` (dashboard) and in the drill-down `findings` list. A
  detector must score at or above this to count as having "meaningfully
  fired" — merely non-zero isn't enough, since `anomaly.py` reports its
  top-3 deviant features unconditionally regardless of how anomalous an
  entity actually is.
- `risk_band` is an investigative priority ranking, not a verdict. An entity
  can sit at "medium" with an empty `findings` list — statistical deviation
  without a specific rule violation. Ganga Oil & Gas is that case in the
  current dataset: its only signal is an anomaly score (0.270) that clears
  the soft floor enough to land at "medium" but falls short of
  `FINDING_SUMMARY_THRESHOLD`, so no named finding backs it up. That's the
  tool correctly flagging borderline signal for human review, not a bug.
- **Final results on the real dataset**: Delta Rail Systems 85.0 critical,
  Indus Financial Services 61.8 high, Continental Banking Corp 58.2 high,
  Fortis Defense Systems 42.3 medium, Ganga Oil & Gas 22.9 medium, remaining
  five entities low. All four seeded entities (2 execution-gap, 1
  negative-space, 1 anomaly-spike) land in the top four.

## Team
| Member | Role |
|---|---|
| Mohit (Leader) | Backend core — ingestion, DB, risk-score API, coordination |
| Kriza | ML (Isolation Forest + detection logic refinement) + PPT |
| Shlok | Frontend — dashboard, upload page, drill-down page |
| Disha | Integration — frontend↔backend, testing, Docker |
| Bhakti | Documentation — architecture doc, README |
| Kunj | QA/Support — testing against answer key, research |

## Deliverables
Source code, README, architecture doc (max 2 pages), demo video (max 2 min),
PPT (max 5 slides).

## Differentiation angle
Existing solutions (SOC-CMM, Microsoft Security Self-Assessment, Thales SOC
Maturity Assessment) are all questionnaire-based self-assessments — subjective and
self-reported. SAT-SA is automated and evidence-based, analyzing actual
operational data, so there is no self-reporting bias.

## Working conventions
- Python: type hints on function signatures, docstrings on every detector.
- Every detector returns both a score AND an `evidence` list of the specific rows
  that triggered it — this feeds the drill-down page and the jury explanation.
- Keep detector thresholds in named constants at the top of each file, not inline
  magic numbers — they will need tuning.
- Do not commit the SQLite db file or the answer key.
- Branches: `main` = demo-ready only. `dev` = integration. Feature branches per member.