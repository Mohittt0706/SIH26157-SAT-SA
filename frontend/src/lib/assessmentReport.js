/**
 * assessmentReport.js
 *
 * Data assembly and orchestration layer for Assessment Report export.
 * Fetches, shapes, and hands off a single structured report object to
 * both pdfReportBuilder.js (PDF) and the JSON download path.
 *
 * Design decisions:
 * - Full entity drill-down (getEntityDetails + getEntityTrend) is only fetched
 *   for flagged entities (high/critical risk band OR non-empty findings_summary).
 *   This caps sequential API calls at a manageable number and keeps the PDF
 *   readable — a report covering 250 entities in full detail would be unusable.
 * - Any field that is null/undefined renders as the sentinel string
 *   "Not available for this assessment." — never blank, never fabricated.
 * - getAuditRunDetail is called once for the latest run to capture the full
 *   detector_config snapshot for Section 6.
 */

import {
  getEntityDetails,
  getAuditRunDetail,
  getEntityTrend,
} from "./api";

// ── Sentinel used wherever a field is missing ──────────────────────────────
export const NA = "Not available for this assessment.";

// ── Risk band classification ───────────────────────────────────────────────
const FLAGGED_BANDS = new Set(["high", "critical"]);

/**
 * Returns true if an entity should receive a full drill-down section in the
 * report (i.e. it appears in the Supervisory Review Priority list).
 */
function isFlagged(entity) {
  if (!entity) return false;
  const band = (entity.risk_band || "").toLowerCase();
  if (FLAGGED_BANDS.has(band)) return true;
  if (Array.isArray(entity.findings_summary) && entity.findings_summary.length > 0)
    return true;
  return false;
}

// ── Safe accessor helpers ──────────────────────────────────────────────────

/** Returns val if it is a non-empty string/number, otherwise NA. */
function safe(val) {
  if (val === null || val === undefined) return NA;
  if (typeof val === "string" && val.trim() === "") return NA;
  return val;
}

/** Returns val if it is a non-empty array, otherwise an empty array. */
function safeArr(val) {
  return Array.isArray(val) && val.length > 0 ? val : [];
}

// ── Timestamp formatter ────────────────────────────────────────────────────

/**
 * Returns { iso: "YYYY-MM-DDTHH:mm:ssZ", display: "DD MMM YYYY, HH:mm UTC" }
 * for a Date object. Falls back to NA string on invalid input.
 */
function formatTimestamp(date) {
  try {
    if (!(date instanceof Date) || isNaN(date.getTime())) return { iso: NA, display: NA };
    const pad = (n) => String(n).padStart(2, "0");
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const iso = date.toISOString().replace(/\.\d{3}Z$/, "Z");
    const display = `${pad(date.getUTCDate())} ${months[date.getUTCMonth()]} ${date.getUTCFullYear()}, ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())} UTC`;
    return { iso, display };
  } catch {
    return { iso: NA, display: NA };
  }
}

// ── File-name stamp ────────────────────────────────────────────────────────

/**
 * Returns "YYYYMMDD-HHmm" string (UTC) for use in file names.
 */
function fileStamp(date) {
  try {
    const pad = (n) => String(n).padStart(2, "0");
    return (
      `${date.getUTCFullYear()}` +
      `${pad(date.getUTCMonth() + 1)}` +
      `${pad(date.getUTCDate())}` +
      `-${pad(date.getUTCHours())}` +
      `${pad(date.getUTCMinutes())}`
    );
  } catch {
    return "UNKNOWN";
  }
}

// ── Section builders ───────────────────────────────────────────────────────

/** Section 1 — Assessment Overview */
function buildOverview(entities, latestRun) {
  const totalAlerts = entities.reduce((s, e) => s + (e.alert_count || 0), 0);
  return {
    entity_count: entities.length,
    total_alerts: totalAlerts,
    latest_run: latestRun
      ? {
          id: safe(latestRun.id),
          timestamp: safe(latestRun.timestamp),
          filename: safe(latestRun.filename),
          rows_received: safe(latestRun.rows_received),
          rows_inserted: safe(latestRun.rows_inserted),
          rows_skipped: safe(latestRun.rows_skipped),
        }
      : null,
  };
}

/** Section 2 — Supervisory Review Priority (all entities, summary only) */
function buildPriorityTable(entities) {
  return entities.map((e) => ({
    entity_name: safe(e.entity_name),
    risk_score: e.risk_score !== undefined && e.risk_score !== null ? e.risk_score : NA,
    risk_band: safe(e.risk_band),
    alert_count: e.alert_count !== undefined && e.alert_count !== null ? e.alert_count : NA,
    primary_driver: safe(e.primary_driver),
  }));
}

/**
 * Sections 3–5 — Per-entity detail for flagged entities.
 * detail  = response from getEntityDetails(name)
 * trend   = response from getEntityTrend(name)
 */
function buildEntityDetail(entity, detail, trend) {
  // Section 3 — Why Flagged
  const findings = safeArr(detail?.findings).map((f) => ({
    rule: safe(f.rule),
    detector: safe(f.detector),
    description: safe(f.description),
    evidence_count: f.evidence_count !== undefined ? f.evidence_count : NA,
    evidence: safeArr(f.evidence).map((ev) => ({
      detail: safe(ev.detail),
      reason: safe(ev.reason),
    })),
  }));

  // Section 4 — Expected vs Observed
  const evo = safeArr(detail?.expected_vs_observed).map((row) => ({
    metric: safe(row.metric),
    observed: row.observed !== undefined ? row.observed : NA,
    expected: row.expected !== undefined ? row.expected : NA,
    unit: safe(row.unit),
    deviation_z: row.deviation_z !== undefined ? row.deviation_z : NA,
    direction: safe(row.direction),
    interpretation: safe(row.interpretation),
  }));

  // Section 5 — Trend / Temporal Analysis
  // Omit if trend indicates insufficient data
  const trendDirection = trend?.direction || "";
  const includeTrend = trendDirection !== "insufficient_data" && trend?.points?.length;
  const trendSection = includeTrend
    ? {
        direction: safe(trend.direction),
        volatility: trend.volatility !== undefined ? trend.volatility : NA,
        points: safeArr(trend.points).map((p) => ({
          run_id: safe(p.run_id),
          timestamp: safe(p.timestamp),
          risk_score: p.risk_score !== undefined ? p.risk_score : NA,
        })),
      }
    : null;

  return {
    entity_name: safe(entity.entity_name),
    risk_score: entity.risk_score !== undefined ? entity.risk_score : NA,
    risk_band: safe(entity.risk_band),
    primary_driver: safe(entity.primary_driver),
    findings,
    expected_vs_observed: evo,
    trend: trendSection,
  };
}

/** Section 6 — Audit / Assessment Metadata */
function buildAuditMetadata(runDetail) {
  if (!runDetail) return null;
  return {
    id: safe(runDetail.id),
    timestamp: safe(runDetail.timestamp),
    filename: safe(runDetail.filename),
    rows_received: safe(runDetail.rows_received),
    rows_inserted: safe(runDetail.rows_inserted),
    rows_skipped: safe(runDetail.rows_skipped),
    entity_count: safe(runDetail.entity_count),
    detector_config: runDetail.detector_config ?? NA,
  };
}

// ── SHA-256 hash ───────────────────────────────────────────────────────────

/**
 * Computes a SHA-256 hash of a string using the browser's native
 * crypto.subtle API (no external dependency). Returns the hex digest.
 * Falls back to "hash-unavailable" if the environment doesn't support it.
 */
async function sha256Hex(str) {
  try {
    const encoded = new TextEncoder().encode(str);
    const hashBuffer = await crypto.subtle.digest("SHA-256", encoded);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return "hash-unavailable";
  }
}

// ── Main export ────────────────────────────────────────────────────────────

/**
 * assembleReportData(entities, auditRuns)
 *
 * Orchestrates all fetches and assembles the canonical report data object.
 * Throws on any unrecoverable error (caller handles UI error state).
 *
 * @param {Array}  entities   — from getRiskScores() (already loaded on Dashboard)
 * @param {Array}  auditRuns  — from getAuditRuns() (already loaded on Dashboard)
 * @returns {Object} reportData — structured report ready for PDF or JSON export
 */
export async function assembleReportData(entities, auditRuns) {
  const now = new Date();
  const generatedAt = formatTimestamp(now);
  const stamp = fileStamp(now);

  const latestRun = auditRuns && auditRuns.length > 0 ? auditRuns[0] : null;
  const runId = latestRun?.id ?? "no-run";

  // Identify which entities warrant a full drill-down
  const flaggedEntities = entities.filter(isFlagged);

  // Fetch audit run detail and all flagged-entity details concurrently
  const [runDetail, ...entityResults] = await Promise.all([
    latestRun
      ? getAuditRunDetail(latestRun.id).catch(() => null)
      : Promise.resolve(null),
    ...flaggedEntities.map((entity) =>
      Promise.all([
        getEntityDetails(entity.entity_name).catch(() => ({})),
        getEntityTrend(entity.entity_name).catch(() => ({})),
      ])
    ),
  ]);

  // Build per-entity detail sections
  const entityDetails = flaggedEntities.map((entity, i) => {
    const [detail, trend] = entityResults[i];
    return buildEntityDetail(entity, detail, trend);
  });

  // Build the payload first (without the hash field) so we can hash it
  const payload = {
    // Schema version — increment when the report structure changes
    report_schema_version: "1.0",

    // Report metadata
    _meta: {
      report_title: "SAT-SA Supervisory Assessment Report",
      product: "VEIL — Visibility and Evidence Intelligence Layer",
      generated_at_iso: generatedAt.iso,
      generated_at_display: generatedAt.display,
      run_id: String(runId),
      file_stamp: stamp,
    },

    // Section 1
    overview: buildOverview(entities, latestRun),

    // Section 2
    supervisory_priority: buildPriorityTable(entities),

    // Sections 3–5 (flagged entities only)
    entity_details: entityDetails,

    // Section 6
    audit_metadata: buildAuditMetadata(runDetail),

    // Section 7 — static template
    supervisory_review: {
      final_decision: NA,
      examiner_notes: NA,
      review_date: NA,
      reviewer_id: NA,
    },

    // Section 8 — disclaimer
    disclaimer:
      "This report is generated by VEIL (Visibility and Evidence Intelligence Layer) as part of the SAT-SA supervisory assessment workflow. " +
      "It is an evidence-compilation tool intended to support — not replace — human supervisory judgement. " +
      "Findings and risk scores are derived from statistical and anomaly-detection models applied to structured SOC operational telemetry. " +
      "They do not constitute a legal determination, regulatory verdict, or definitive finding of misconduct. " +
      "All supervisory decisions remain the sole responsibility of the designated examiner. " +
      "This document is intended for authorized supervisory use only and must be handled in accordance with applicable data-handling policies.",
  };

  // Compute SHA-256 over the canonical JSON representation of the payload.
  // The hash field itself is excluded from the input so the value is stable
  // and a receiver can re-compute it by stringifying the object without report_hash.
  const report_hash = await sha256Hex(JSON.stringify(payload));

  const reportData = { ...payload, report_hash };

  return reportData;
}

/**
 * buildFileName(reportData, ext)
 * Returns: "SAT-SA_Assessment_Report_<runId>_<YYYYMMDD-HHmm>.<ext>"
 */
export function buildFileName(reportData, ext) {
  const meta = reportData?._meta ?? {};
  const runId = (meta.run_id ?? "no-run").replace(/[^a-zA-Z0-9_-]/g, "_");
  const stamp = meta.file_stamp ?? "UNKNOWN";
  return `SAT-SA_Assessment_Report_${runId}_${stamp}.${ext}`;
}

/**
 * downloadJSON(reportData)
 * Triggers a browser download of the report as pretty-printed JSON.
 */
export function downloadJSON(reportData) {
  const filename = buildFileName(reportData, "json");
  const blob = new Blob([JSON.stringify(reportData, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  // Clean up after a tick so the download has time to start
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}

/**
 * downloadCSV(reportData)
 * Exports the Supervisory Review Priority table as a CSV file.
 * Columns: Entity, Risk Score, Risk Band, Alert Count, Primary Driver.
 * No external dependency — plain string join.
 */
export function downloadCSV(reportData) {
  const filename = buildFileName(reportData, "csv");
  const rows = reportData?.supervisory_priority ?? [];

  const escape = (val) => {
    const s = String(val ?? "");
    // RFC 4180: wrap in quotes if value contains comma, quote, or newline
    if (s.includes(",") || s.includes('"') || s.includes("\n")) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };

  const header = ["Entity", "Risk Score", "Risk Band", "Alert Count", "Primary Driver"];
  const lines = [
    header.map(escape).join(","),
    ...rows.map((row) =>
      [
        row.entity_name,
        row.risk_score,
        row.risk_band,
        row.alert_count,
        row.primary_driver,
      ]
        .map(escape)
        .join(",")
    ),
  ];

  const csv = lines.join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 100);
}
