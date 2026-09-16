import axios from "axios";

const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || "http://localhost:8000/api";

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 8000,
});

export async function getRiskScores() {
  const response = await client.get("/risk-scores");
  return response.data;
}

export async function getEntityDetails(entityName) {
  const response = await client.get(`/entities/${encodeURIComponent(entityName)}`);
  return response.data;
}

export async function uploadCSV(file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await client.post("/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function getAuditRuns() {
  const response = await client.get("/audit/runs");
  return response.data;
}

export async function getAuditRunDetail(runId) {
  const response = await client.get(`/audit/runs/${runId}`);
  return response.data;
}

export async function getEntityTrend(entityName) {
  const response = await client.get(`/trends/${encodeURIComponent(entityName)}`);
  return response.data;
}

export async function getPrioritySamples(limit) {
  const params = limit ? { limit } : {};
  const response = await client.get("/priority-samples", { params });
  return response.data;
}

/**
 * Entity picker for the manual-review workflow — GET /api/manual-review/entities.
 * Name + alert_count only, derived live from the currently loaded dataset.
 * Never carries a risk_score/risk_band/primary_driver — same blindness
 * guarantee as getBlindEvidence below, so this is safe to call before any
 * review has been formed.
 */
export async function getBlindEntities() {
  const response = await client.get("/manual-review/entities");
  return response.data;
}

/**
 * Blind evidence dossier for one entity — GET /api/manual-review/{entity}/evidence.
 * No fallback on failure: a failed blind fetch must surface as a real error
 * to the caller, not silently resolve to null (that null previously drove a
 * peer_metrics fallback built from VEIL's own drill-down response — exactly
 * the peer-relative data this endpoint exists to withhold).
 */
export async function getBlindEvidence(entityName) {
  const response = await client.get(`/manual-review/${encodeURIComponent(entityName)}/evidence`);
  return response.data;
}

/**
 * Submit a manual review — POST /api/manual-review. entity_name travels in
 * the body (there is no path segment on this route); payload must already
 * be shaped like the backend's ManualReviewCreate schema (flat top-level
 * fields, enum values in their backend form, no `answers` wrapper).
 */
export async function submitManualReview(payload) {
  const response = await client.post("/manual-review", payload);
  return response.data;
}

/**
 * Full review history for one entity, newest first — GET /api/manual-review/{entity}.
 * Always a list (possibly empty), never a single object.
 */
export async function getManualReviewHistory(entityName) {
  const response = await client.get(`/manual-review/${encodeURIComponent(entityName)}`);
  return response.data;
}

/**
 * Manual-vs-VEIL comparison for one entity's most recent review —
 * GET /api/manual-review/{entity}/comparison. Only meaningful after at
 * least one review has been submitted; the backend returns
 * `{available: false, ...}` otherwise rather than 404ing.
 */
export async function getManualReviewComparison(entityName) {
  const response = await client.get(`/manual-review/${encodeURIComponent(entityName)}/comparison`);
  return response.data;
}

/**
 * Aggregate manual-vs-VEIL agreement across every submitted review —
 * GET /api/manual-review/metrics.
 */
export async function getManualReviewMetrics() {
  const response = await client.get("/manual-review/metrics");
  return response.data;
}
