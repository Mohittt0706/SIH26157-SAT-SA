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
  getAuditRuns,
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

// ── CSV cell escaping (security hardening) ─────────────────────────────────

/** Leading characters spreadsheet apps (Excel, Google Sheets, LibreOffice)
 * interpret as "this cell is a formula" when a CSV is opened. */
const CSV_FORMULA_TRIGGER_CHARS = new Set(["=", "+", "-", "@", "\t", "\r"]);

/**
 * RFC 4180 quoting plus CSV/formula-injection hardening for one cell.
 *
 * entity_name (and, in the entity dossier export, investigation-note-derived
 * evidence strings) originate from an uploaded file — untrusted input by the
 * time it reaches here. A cell beginning with =, +, -, or @ is executed as a
 * formula by common spreadsheet apps on open, which is a real exfiltration/
 * code-execution vector for a CSV export (not merely a display-escaping
 * concern the way JSX/jsPDF's plain-text rendering already is elsewhere in
 * this file). Prefixing a single quote is the standard mitigation — every
 * major spreadsheet app treats a leading `'` as "force this cell to text"
 * and does not render the quote itself.
 */
function csvCell(val) {
  let s = String(val ?? "");
  if (s.length > 0 && CSV_FORMULA_TRIGGER_CHARS.has(s[0])) {
    s = `'${s}`;
  }
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
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
 * assembleEntityReportData(entityName, entityData, auditRuns)
 *
 * Assembles a dedicated single-entity report dossier.
 * Uses existing entityData from DrillDownPage state if available,
 * otherwise fetches it.
 *
 * @param {string} entityName
 * @param {Object} [entityData] - Pre-loaded state from DrillDownPage
 * @param {Array}  [auditRuns]  - Audit runs list if available
 * @returns {Object} reportData
 */
export async function assembleEntityReportData(entityName, entityData = null, auditRuns = null) {
  const now = new Date();
  const generatedAt = formatTimestamp(now);
  const stamp = fileStamp(now);

  // If auditRuns not provided, fetch them
  let runs = auditRuns;
  if (!runs || runs.length === 0) {
    try {
      runs = await getAuditRuns();
    } catch {
      runs = [];
    }
  }

  const latestRun = runs && runs.length > 0 ? runs[0] : null;
  const runId = latestRun?.id ?? "no-run";

  // Fetch run detail, trend, and entity details if missing
  const [runDetail, trend, fetchedDetail] = await Promise.all([
    latestRun
      ? getAuditRunDetail(latestRun.id).catch(() => null)
      : Promise.resolve(null),
    getEntityTrend(entityName).catch(() => null),
    !entityData
      ? getEntityDetails(entityName).catch(() => null)
      : Promise.resolve(entityData),
  ]);

  const detail = entityData || fetchedDetail;

  const entity = {
    entity_name: entityName,
    risk_score: detail?.risk_score,
    risk_band: detail?.risk_band,
    primary_driver: detail?.primary_driver,
  };

  const entityDetailSection = buildEntityDetail(entity, detail, trend);

  const payload = {
    report_schema_version: "1.0",
    _meta: {
      report_title: "SAT-SA Entity Assessment Report",
      product: "VEIL — Visibility and Evidence Intelligence Layer",
      mode: "entity",
      entity_name: entityName,
      generated_at_iso: generatedAt.iso,
      generated_at_display: generatedAt.display,
      run_id: String(runId),
      file_stamp: stamp,
    },
    entity_summary: {
      entity_name: safe(entityName),
      risk_score: detail?.risk_score !== undefined && detail?.risk_score !== null ? detail.risk_score : NA,
      risk_band: safe(detail?.risk_band),
      primary_driver: safe(detail?.primary_driver),
      component_scores: {
        execution_gap: detail?.component_scores?.execution_gap !== undefined ? detail.component_scores.execution_gap : NA,
        negative_space: detail?.component_scores?.negative_space !== undefined ? detail.component_scores.negative_space : NA,
        anomaly: detail?.component_scores?.anomaly !== undefined ? detail.component_scores.anomaly : NA,
      },
      peer_metrics: detail?.peer_metrics ?? null,
    },
    findings: entityDetailSection.findings,
    expected_vs_observed: entityDetailSection.expected_vs_observed,
    trend: entityDetailSection.trend,
    audit_metadata: buildAuditMetadata(runDetail),
    supervisory_review: {
      final_decision: NA,
      examiner_notes: NA,
      review_date: NA,
      reviewer_id: NA,
    },
    disclaimer:
      "This report is generated by VEIL (Visibility and Evidence Intelligence Layer) as part of the SAT-SA supervisory assessment workflow. " +
      "It is an evidence-compilation tool intended to support — not replace — human supervisory judgement. " +
      "Findings and risk scores are derived from statistical and anomaly-detection models applied to structured SOC operational telemetry. " +
      "They do not constitute a legal determination, regulatory verdict, or definitive finding of misconduct. " +
      "All supervisory decisions remain the sole responsibility of the designated examiner. " +
      "This document is intended for authorized supervisory use only and must be handled in accordance with applicable data-handling policies.",
  };

  const report_hash = await sha256Hex(JSON.stringify(payload));
  return { ...payload, report_hash };
}

/**
 * buildFileName(reportData, ext)
 * Returns: "SAT-SA_Assessment_Report_<runId>_<stamp>.<ext>"
 * or "SAT-SA_Entity_Report_<entityName>_<runId>_<stamp>.<ext>"
 */
export function buildFileName(reportData, ext) {
  const meta = reportData?._meta ?? {};
  const runId = (meta.run_id ?? "no-run").replace(/[^a-zA-Z0-9_-]/g, "_");
  const stamp = meta.file_stamp ?? "UNKNOWN";
  if (meta.mode === "entity" && meta.entity_name) {
    const safeEntity = meta.entity_name.replace(/[^a-zA-Z0-9_-]/g, "_");
    return `SAT-SA_Entity_Report_${safeEntity}_${runId}_${stamp}.${ext}`;
  }
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
 * Dispatches to downloadEntityCSV or exports the Supervisory Review Priority table.
 */
export function downloadCSV(reportData) {
  if (reportData?._meta?.mode === "entity") {
    return downloadEntityCSV(reportData);
  }

  const filename = buildFileName(reportData, "csv");
  const rows = reportData?.supervisory_priority ?? [];

  const header = ["Entity", "Risk Score", "Risk Band", "Alert Count", "Primary Driver"];
  const lines = [
    header.map(csvCell).join(","),
    ...rows.map((row) =>
      [
        row.entity_name,
        row.risk_score,
        row.risk_band,
        row.alert_count,
        row.primary_driver,
      ]
        .map(csvCell)
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

/**
 * downloadEntityCSV(reportData)
 * Exports a comprehensive CSV dossier for a single entity.
 */
export function downloadEntityCSV(reportData) {
  const filename = buildFileName(reportData, "csv");
  const summary = reportData?.entity_summary ?? {};
  const comp = summary.component_scores ?? {};
  const findings = reportData?.findings ?? [];
  const evo = reportData?.expected_vs_observed ?? [];
  const trend = reportData?.trend?.points ?? [];

  const lines = [];
  lines.push(["--- ENTITY ASSESSMENT SUMMARY ---"].join(","));
  lines.push(["Entity Name", "Risk Score", "Risk Band", "Primary Driver", "Execution Gap", "Negative Space", "Anomaly"].map(csvCell).join(","));
  lines.push([
    summary.entity_name,
    summary.risk_score,
    summary.risk_band,
    summary.primary_driver,
    comp.execution_gap,
    comp.negative_space,
    comp.anomaly,
  ].map(csvCell).join(","));

  lines.push("");
  lines.push(["--- EXPECTED VS OBSERVED ---"].join(","));
  lines.push(["Metric", "Observed", "Expected", "Unit", "Deviation Z", "Direction", "Interpretation"].map(csvCell).join(","));
  if (evo.length > 0) {
    evo.forEach((r) => {
      lines.push([r.metric, r.observed, r.expected, r.unit, r.deviation_z, r.direction, r.interpretation].map(csvCell).join(","));
    });
  } else {
    lines.push(["No expected vs observed anomalies flagged for this entity."]);
  }

  lines.push("");
  lines.push(["--- FINDINGS & EVIDENCE ---"].join(","));
  lines.push(["Rule", "Detector", "Description", "Evidence Count", "Evidence Detail", "Reason"].map(csvCell).join(","));
  if (findings.length > 0) {
    findings.forEach((f) => {
      if (f.evidence && f.evidence.length > 0) {
        f.evidence.forEach((ev) => {
          lines.push([f.rule, f.detector, f.description, f.evidence_count, ev.detail, ev.reason].map(csvCell).join(","));
        });
      } else {
        lines.push([f.rule, f.detector, f.description, f.evidence_count, "", ""].map(csvCell).join(","));
      }
    });
  } else {
    lines.push(["No findings recorded for this entity."]);
  }

  if (trend && trend.length > 0) {
    lines.push("");
    lines.push(["--- TEMPORAL TREND ---"].join(","));
    lines.push(["Run ID", "Timestamp", "Risk Score"].map(csvCell).join(","));
    trend.forEach((p) => {
      lines.push([p.run_id, p.timestamp, p.risk_score].map(csvCell).join(","));
    });
  }

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
