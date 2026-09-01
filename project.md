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
- Frontend: React (Vite) + Tailwind + Recharts
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
│   └── data/                    # SQLite db file lands here (gitignored)
├── frontend/
├── dataset/
├── docs/
└── project.md
```

## Data schema (alert CSV)
`alert_id, entity_name, severity, created_time, closed_time, escalated (yes/no),
investigation_notes, asset_type`

Synthetic dataset: 639 alerts across 10 fake companies. 4 companies have
intentionally baked-in suspicious patterns (2 execution-gap, 1 negative-space,
1 anomaly-spike); 6 are normal baseline.

`dataset/answer_key_INTERNAL_ONLY.csv` maps which company is which — internal
testing only, gitignored, never submitted.

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