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
