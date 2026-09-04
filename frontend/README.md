# VEIL — SAT-SA Frontend

The supervisory console for **SAT-SA** (Supervisory Analytics Tool for SOC
Assessment, SIH26157) — a dashboard for uploading SOC alert data and
reviewing the resulting risk scores, findings, and peer benchmarking for
each entity. UI only; all analytics and ML run in the FastAPI backend.

## Stack

React 18 · Vite · React Router · Tailwind CSS · Recharts · Axios

## Running locally

```bash
npm install
npm run dev
```

Serves at `http://localhost:5173`.

## Backend

The app expects the SAT-SA API running at `http://127.0.0.1:8000`
(see `src/lib/api.js`). Start it from `backend/` before using the
Upload or Dashboard pages — everything here is a thin client over
that API, offline and self-contained.
