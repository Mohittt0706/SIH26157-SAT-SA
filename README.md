# SAT-SA — Supervisory Analytics Tool for SOC Assessment

**SIH26157** | Sponsoring Org: NTRO | Theme: Blockchain & Cybersecurity

NCIIPC needs a way to tell which organizations are doing SOC (Security Operations
Center) work for real versus just for show, without relying on self-reported
questionnaires. SAT-SA ingests an organization's raw SOC alert/case export (CSV or
JSON) and runs three independent detectors — rule-based execution-gap checks, a
peer-baseline negative-space check, and an Isolation Forest anomaly model — to produce
one evidence-backed risk score per entity. It's built for supervisory bodies (NCIIPC,
sector regulators, internal audit teams) who need to prioritize which organizations to
audit first, from actual operational data rather than a self-assessment survey.

Full architecture and methodology: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Quick start (Docker — primary path)

```bash
git clone <repo-url>
cd SIH26157-SAT-SA
docker compose up --build
```

- Frontend: **http://localhost**
- Backend API: **http://localhost:8000** (proxied through the frontend at `/api/`)

That's it — upload `dataset/soc_alerts_synthetic_dataset.csv` (or your own file) from
the Analyze page and the dashboard populates. No other setup, no external services, no
internet access needed once the images are built.

## How it works

**1. Upload.** Submit a CSV or JSON export of an organization's SOC alert data from the
Analyze page. Ingestion replaces the current alert set and kicks off a fresh
assessment run, which is what the Audit trail records.

![Upload page](docs/screenshots/upload.png)
*Analyze page: file picker and upload status for a CSV/JSON alert export.*

**2. Assess.** All three detectors run against the uploaded data and combine into one
risk score per entity, shown ranked on the dashboard. Each row also carries a
risk band and a primary driver, so the highest-priority entities surface immediately.

![Supervisory overview dashboard](docs/screenshots/dashboard.png)
*Dashboard: entities ranked by risk score, with risk band and primary driver.*

**3. Drill down.** Click into any entity to see its three component scores broken out,
plus the concrete evidence behind them — cited `alert_id`s, peer-comparison strings,
and a peer benchmark chart. Nothing is flagged without a reason attached.

![Entity drill-down with evidence and peer benchmarking](docs/screenshots/drilldown.png)
*Drill-down: component scores, cited evidence, and peer benchmark comparison.*

**4. Audit.** Every upload is preserved as a historical run — timestamp, source file,
ingestion counts, the exact detector configuration in force, and the resulting scores —
so a supervisor can revisit or reproduce any past assessment.

![Audit trail of past assessment runs](docs/screenshots/audit.png)
*Audit page: list of past assessment runs with their configuration snapshots.*

## Manual setup (alternative)

**Backend** (Python 3.11+):
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
API is live at `http://localhost:8000` (docs at `http://localhost:8000/docs`).

**Frontend** (Node 20+), in a separate terminal:
```bash
cd frontend
npm install
npm run dev
```
App is live at `http://localhost:5173`, and already points at `http://localhost:8000/api`
by default (no `.env` needed for local dev).

---

## Data format

Upload a `.csv` or `.json` file. JSON must be either a top-level array of alert objects,
or `{"alerts": [...]}`. Every alert needs these 8 fields:

| Column | Description |
|---|---|
| `alert_id` | Unique per company — two companies may reuse the same ID |
| `entity_name` | The organization the alert belongs to |
| `severity` | `critical` / `high` / `medium` / `low` (case-insensitive) |
| `created_time` | When the alert fired, `YYYY-MM-DD HH:MM:SS` |
| `closed_time` | When it was closed, same format — blank/omitted if still open |
| `escalated` | `yes`/`no` (also accepts `true`/`false`, `1`/`0`) |
| `investigation_notes` | Free-text analyst notes — blank is valid and meaningful |
| `asset_type` | e.g. `Server`, `Database`, `Endpoint`, `Network Device` |

**CSV example:**
```csv
alert_id,entity_name,severity,created_time,closed_time,escalated,investigation_notes,asset_type
ALT00627,Jupiter Aviation Control,low,2026-01-01 19:48:00,2026-01-02 00:33:00,no,"Correlated with SIEM logs, escalated.",Database
```

**JSON example:**
```json
{
  "alerts": [
    {
      "alert_id": "ALT00627",
      "entity_name": "Jupiter Aviation Control",
      "severity": "low",
      "created_time": "2026-01-01 19:48:00",
      "closed_time": "2026-01-02 00:33:00",
      "escalated": "no",
      "investigation_notes": "Correlated with SIEM logs, escalated.",
      "asset_type": "Database"
    }
  ]
}
```

## API

Every response is JSON; the full request/response schema for each endpoint is at
**`/docs`** (Swagger UI) once the backend is running.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness check + current ingested alert count |
| `POST` | `/api/upload` | Upload a CSV/JSON file, replacing the current alert set |
| `GET` | `/api/risk-scores` | Every entity ranked by risk score (dashboard view) |
| `GET` | `/api/entities/{entity_name}` | Full drill-down for one entity — component scores, findings, evidence, peer metrics |
| `GET` | `/api/audit/runs` | List every past assessment run (audit trail) |
| `GET` | `/api/audit/runs/{run_id}` | Full audit record for one run — config snapshot + results at that point in time |

## Running the tests

```bash
cd backend
pip install -r requirements.txt   # if not already done
pytest tests/ -v
```
46 tests covering all three detectors, the risk-score combiner, and the external
dataset pipeline. `backend/pytest.ini` scopes discovery to `tests/` only.

## Repo layout

```
SIH26157-SAT-SA/
├── backend/app/
│   ├── main.py, database.py, models.py, schemas.py
│   ├── routers/          # ingestion.py (upload), analytics.py (risk-scores, entities, audit)
│   └── analytics/        # execution_gap.py, negative_space.py, anomaly.py, risk_score.py
├── backend/tests/        # pytest suite
├── frontend/src/         # React pages (Landing, Upload, Dashboard, DrillDown, Audit)
├── dataset/               # synthetic SOC alert dataset (639 alerts, 10 entities)
├── docs/ARCHITECTURE.md   # solution architecture, formulas, validation methodology
└── docker-compose.yml
```

## Results

The included synthetic dataset (`dataset/soc_alerts_synthetic_dataset.csv`) has 639
alerts across 10 entities, 4 of which have intentionally seeded supervisory-failure
patterns (2 execution-gap, 1 negative-space, 1 anomaly-spike) against 6 normal
baselines. **All 4 seeded entities land in the top 4 by risk score**, verified against a
held-out answer key (see [docs/ARCHITECTURE.md §6](docs/ARCHITECTURE.md)):

| Entity | Risk Score | Band |
|---|---|---|
| Delta Rail Systems | 85.0 | critical |
| Indus Financial Services | 61.8 | high |
| Continental Banking Corp | 58.2 | high |
| Fortis Defense Systems | 44.8 | medium |
| Ganga Oil & Gas | 25.4 | medium |
| *(remaining 5 entities)* | ≤ 18.8 | low |

## Offline

SAT-SA runs fully offline — no external API calls, no cloud services, no third-party
LLM dependency at runtime. Everything (ingestion, both rule-based detectors, and the
Isolation Forest model) runs locally against the SQLite file.

![Running with no network access](docs/screenshots/airgapped.png)
*Screenshot pending — should show the app running end-to-end (upload → dashboard) with
the host's network/Wi-Fi disabled or a browser network monitor showing zero external
requests, as evidence of the offline claim.*
