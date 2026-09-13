import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const client = axios.create({
  baseURL: API_BASE_URL,
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
 * Step 5: Blind evidence API adapter.
 * Attempts to call backend blind-evidence endpoint if supported.
 */
export async function getBlindEvidence(entityName) {
  try {
    const response = await client.get(`/blind-evidence/${encodeURIComponent(entityName)}`);
    return response.data;
  } catch (error) {
    // If backend endpoint is not implemented (404/501), return null so UI can handle cleanly
    if (error.response?.status === 404 || error.response?.status === 501) {
      return null;
    }
    throw error;
  }
}

/**
 * Step 5: Manual review persistence adapter.
 * Attempts to POST manual review assessment to backend if supported.
 */
export async function submitManualReview(entityName, reviewData) {
  try {
    const response = await client.post(`/manual-review/${encodeURIComponent(entityName)}`, reviewData);
    return response.data;
  } catch (error) {
    if (error.response?.status === 404 || error.response?.status === 501) {
      return null;
    }
    throw error;
  }
}

/**
 * Step 5: Retrieve saved manual review response.
 */
export async function getManualReview(entityName) {
  try {
    const response = await client.get(`/manual-review/${encodeURIComponent(entityName)}`);
    return response.data;
  } catch (error) {
    if (error.response?.status === 404 || error.response?.status === 501) {
      return null;
    }
    throw error;
  }
}
