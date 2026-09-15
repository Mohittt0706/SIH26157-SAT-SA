/**
 * pdfReportBuilder.js
 *
 * jsPDF layout and rendering for the SAT-SA Assessment Report.
 * Kept separate from assessmentReport.js so the data-assembly layer
 * stays readable and testable without a PDF dependency.
 *
 * Design decisions:
 * - Print-optimized: white background / dark text — the PDF is an official
 *   artifact meant to be printed or shared, even though the app is dark-themed.
 * - Accent color (#56c7ff) is used only on headings / decorative rules —
 *   never as a background fill (illegible on white paper).
 * - Tables use jspdf-autotable; each table triggers a page-break guard so a
 *   table never starts in the last 40 mm of a page.
 * - All text values that equal the NA sentinel are rendered as em-dash (—)
 *   for cleaner typography in the printed artifact.
 * - Page numbers in the footer on every page except the cover.
 */

import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import { buildFileName, NA } from "./assessmentReport";

// ── Design tokens (PDF, not CSS) ───────────────────────────────────────────
const ACCENT = [86, 199, 255];       // #56c7ff  — headings / rules
const BLACK  = [15, 17, 20];         // near-black body text
const GRAY   = [100, 110, 120];      // muted / secondary text
const DIVIDER= [220, 224, 229];      // table rules / dividers

// Band colours used only in the Priority table badge column
const BAND_COLORS = {
  critical: [239, 107, 114],  // --red
  high:     [229, 173,  90],  // --amber
  medium:   [229, 173,  90],  // --amber (same shade)
  low:      [ 87, 213, 140],  // --green
};

const PAGE_W = 210;  // A4 mm
const PAGE_H = 297;
const MARGIN_L = 18;
const MARGIN_R = 18;
const CONTENT_W = PAGE_W - MARGIN_L - MARGIN_R;
const FOOTER_Y = PAGE_H - 12;

// ── Helpers ────────────────────────────────────────────────────────────────

/** Replaces the NA sentinel with an em-dash for typography. */
function display(val) {
  if (val === NA || val === null || val === undefined) return "—";
  return String(val);
}

/** Truncates a string to maxLen chars, appending "…" if cut. */
function trunc(str, maxLen = 120) {
  const s = display(str);
  return s.length > maxLen ? s.slice(0, maxLen - 1) + "…" : s;
}

/** Returns the band color triplet or a default gray. */
function bandColor(band) {
  return BAND_COLORS[(band || "").toLowerCase()] ?? GRAY;
}

// ── Cursor state ───────────────────────────────────────────────────────────

/**
 * Lightweight cursor object threaded through rendering functions.
 * `y` tracks vertical position in mm from top.
 */
function makeCursor(initialY = MARGIN_L) {
  return { y: initialY };
}

/** Adds a page, resets the cursor to the top margin, draws the footer. */
function addPage(doc, cursor) {
  doc.addPage();
  cursor.y = 22;
  drawFooter(doc);
}

/** Ensures at least `needed` mm remain on the page; adds one if not. */
function ensureSpace(doc, cursor, needed) {
  if (cursor.y + needed > FOOTER_Y - 6) {
    addPage(doc, cursor);
  }
}

// ── Footer ─────────────────────────────────────────────────────────────────

function drawFooter(doc) {
  const pageNum = doc.internal.getNumberOfPages();
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...GRAY);
  doc.text("SAT-SA | VEIL Assessment Report", MARGIN_L, FOOTER_Y);
  doc.text(`${pageNum}`, PAGE_W - MARGIN_R, FOOTER_Y, { align: "right" });
  doc.setDrawColor(...DIVIDER);
  doc.setLineWidth(0.3);
  doc.line(MARGIN_L, FOOTER_Y - 3, PAGE_W - MARGIN_R, FOOTER_Y - 3);
}

// ── Typography helpers ─────────────────────────────────────────────────────

function setHeading1(doc) {
  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.setTextColor(...ACCENT);
}

function setHeading2(doc) {
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.setTextColor(...BLACK);
}

function setHeading3(doc) {
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.setTextColor(...BLACK);
}

function setBody(doc) {
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.setTextColor(...BLACK);
}

function setMuted(doc) {
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.setTextColor(...GRAY);
}

/**
 * Draws a section title bar — accent rule on the left, bold heading text.
 * Advances the cursor by the heading height + gap.
 */
function drawSectionTitle(doc, cursor, text, level = 1) {
  ensureSpace(doc, cursor, 16);
  if (level === 1) {
    setHeading1(doc);
    doc.setDrawColor(...ACCENT);
    doc.setLineWidth(0.8);
    doc.line(MARGIN_L, cursor.y + 1, MARGIN_L + 3, cursor.y + 1);
    doc.text(text, MARGIN_L + 6, cursor.y + 1.5);
    cursor.y += 9;
    doc.setDrawColor(...DIVIDER);
    doc.setLineWidth(0.2);
    doc.line(MARGIN_L, cursor.y, PAGE_W - MARGIN_R, cursor.y);
    cursor.y += 4;
  } else {
    setHeading2(doc);
    doc.text(text, MARGIN_L, cursor.y);
    cursor.y += 6;
  }
}

/**
 * Draws a label/value pair in two columns.
 * label is muted; value is body text. Wraps long values.
 */
function drawKV(doc, cursor, label, value, labelW = 52) {
  ensureSpace(doc, cursor, 8);
  setMuted(doc);
  doc.text(String(label).toUpperCase(), MARGIN_L, cursor.y);
  setBody(doc);
  const valueStr = display(value);
  const lines = doc.splitTextToSize(valueStr, CONTENT_W - labelW);
  doc.text(lines, MARGIN_L + labelW, cursor.y);
  cursor.y += Math.max(lines.length * 4.5, 5.5);
}

/**
 * Renders a paragraph of body text with automatic line wrapping.
 */
function drawParagraph(doc, cursor, text, maxWidth = CONTENT_W) {
  ensureSpace(doc, cursor, 10);
  setBody(doc);
  const lines = doc.splitTextToSize(display(text), maxWidth);
  doc.text(lines, MARGIN_L, cursor.y);
  cursor.y += lines.length * 4.8 + 3;
}

// ── autoTable wrapper ──────────────────────────────────────────────────────

/**
 * Renders a table via jspdf-autotable and advances the cursor to after it.
 *
 * @param {jsPDF}  doc
 * @param {Object} cursor
 * @param {Array}  head   — array of column-header strings
 * @param {Array}  body   — array of row arrays (strings)
 * @param {Array}  colWidths — relative column widths (fractions of CONTENT_W)
 */
function drawTable(doc, cursor, head, body, colWidths) {
  ensureSpace(doc, cursor, 30);

  const columnStyles = {};
  if (colWidths) {
    colWidths.forEach((frac, i) => {
      columnStyles[i] = { cellWidth: CONTENT_W * frac };
    });
  }

  autoTable(doc, {
    startY: cursor.y,
    margin: { left: MARGIN_L, right: MARGIN_R },
    head: [head],
    body,
    styles: {
      font: "helvetica",
      fontSize: 8,
      textColor: BLACK,
      cellPadding: { top: 3, right: 4, bottom: 3, left: 4 },
      overflow: "linebreak",
      lineColor: DIVIDER,
      lineWidth: 0.2,
    },
    headStyles: {
      fillColor: [240, 243, 247],
      textColor: GRAY,
      fontStyle: "bold",
      fontSize: 7.5,
    },
    alternateRowStyles: {
      fillColor: [250, 251, 252],
    },
    columnStyles,
    didDrawPage: () => {
      drawFooter(doc);
    },
  });

  cursor.y = doc.lastAutoTable.finalY + 6;
}

// ── Cover page ─────────────────────────────────────────────────────────────

function renderCoverPage(doc, meta) {
  // Background accent bar at top
  doc.setFillColor(...ACCENT);
  doc.rect(0, 0, PAGE_W, 4, "F");

  // Title block
  doc.setFont("helvetica", "bold");
  doc.setFontSize(28);
  doc.setTextColor(...BLACK);
  doc.text("SAT-SA", MARGIN_L, 60);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(14);
  doc.setTextColor(...GRAY);
  doc.text("Supervisory Assessment Report", MARGIN_L, 72);

  // Subtitle / product name
  doc.setFontSize(9);
  doc.setTextColor(...ACCENT);
  doc.text("VEIL — Visibility and Evidence Intelligence Layer", MARGIN_L, 82);

  // Horizontal rule
  doc.setDrawColor(...DIVIDER);
  doc.setLineWidth(0.4);
  doc.line(MARGIN_L, 90, PAGE_W - MARGIN_R, 90);

  // Metadata block
  const kvY = 100;
  const labelW = 52;
  const lineH = 9;

  const fields = [
    ["Generated",  display(meta.generated_at_display)],
    ["Assessment Run", display(meta.run_id)],
  ];

  doc.setFont("helvetica", "normal");
  fields.forEach(([label, value], i) => {
    const y = kvY + i * lineH;
    doc.setFontSize(8);
    doc.setTextColor(...GRAY);
    doc.text(label.toUpperCase(), MARGIN_L, y);
    doc.setFontSize(9);
    doc.setTextColor(...BLACK);
    doc.text(value, MARGIN_L + labelW, y);
  });

  // Classification notice at bottom of cover
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.setTextColor(...GRAY);
  doc.text(
    "FOR AUTHORIZED SUPERVISORY USE ONLY",
    PAGE_W / 2,
    PAGE_H - 25,
    { align: "center" }
  );
  doc.setFont("helvetica", "normal");
  doc.setFontSize(7.5);
  doc.text(
    "Handle in accordance with applicable data-handling policies.",
    PAGE_W / 2,
    PAGE_H - 19,
    { align: "center" }
  );
}

// ── Section 1 — Assessment Overview ───────────────────────────────────────

function renderOverview(doc, cursor, overview) {
  drawSectionTitle(doc, cursor, "1  Assessment Overview");

  const run = overview.latest_run;
  drawKV(doc, cursor, "Entities Analyzed", overview.entity_count);
  drawKV(doc, cursor, "Total Alerts", overview.total_alerts !== undefined ? overview.total_alerts.toLocaleString() : NA);

  if (run) {
    cursor.y += 2;
    drawKV(doc, cursor, "Assessment Run ID", run.id);
    drawKV(doc, cursor, "Run Timestamp", run.timestamp);
    drawKV(doc, cursor, "Source File", run.filename);
    drawKV(doc, cursor, "Rows Received", run.rows_received);
    drawKV(doc, cursor, "Rows Inserted", run.rows_inserted);
    drawKV(doc, cursor, "Rows Skipped", run.rows_skipped);
  } else {
    drawKV(doc, cursor, "Assessment Run", NA);
  }

  cursor.y += 4;
}

// ── Section 2 — Supervisory Review Priority ────────────────────────────────

function renderPriorityTable(doc, cursor, priorityRows) {
  drawSectionTitle(doc, cursor, "2  Supervisory Review Priority");

  if (!priorityRows || priorityRows.length === 0) {
    drawParagraph(doc, cursor, "No entities found in this assessment.");
    return;
  }

  const head = ["Entity", "Risk Score", "Band", "Alerts", "Primary Driver"];
  const colWidths = [0.30, 0.13, 0.13, 0.10, 0.34];

  const body = priorityRows.map((row) => [
    display(row.entity_name),
    row.risk_score !== NA ? String(Number(row.risk_score).toFixed(3)) : "—",
    display(row.risk_band).toUpperCase(),
    row.alert_count !== NA ? String(row.alert_count) : "—",
    display(row.primary_driver),
  ]);

  // Color-code band cells via willDrawCell
  autoTable(doc, {
    startY: cursor.y,
    margin: { left: MARGIN_L, right: MARGIN_R },
    head: [head],
    body,
    styles: {
      font: "helvetica",
      fontSize: 8,
      textColor: BLACK,
      cellPadding: { top: 3, right: 4, bottom: 3, left: 4 },
      overflow: "linebreak",
      lineColor: DIVIDER,
      lineWidth: 0.2,
    },
    headStyles: {
      fillColor: [240, 243, 247],
      textColor: GRAY,
      fontStyle: "bold",
      fontSize: 7.5,
    },
    alternateRowStyles: {
      fillColor: [250, 251, 252],
    },
    columnStyles: Object.fromEntries(
      colWidths.map((frac, i) => [i, { cellWidth: CONTENT_W * frac }])
    ),
    willDrawCell: (data) => {
      // Column 2 is the band column — tint the text to match the band color
      if (data.section === "body" && data.column.index === 2) {
        const band = (body[data.row.index]?.[2] || "").toLowerCase();
        const color = bandColor(band);
        doc.setTextColor(...color);
        doc.setFont("helvetica", "bold");
      }
    },
    didDrawCell: (data) => {
      // Reset text color after band cell
      if (data.section === "body" && data.column.index === 2) {
        doc.setTextColor(...BLACK);
        doc.setFont("helvetica", "normal");
      }
    },
    didDrawPage: () => drawFooter(doc),
  });

  cursor.y = doc.lastAutoTable.finalY + 6;
}

// ── Sections 3–5 — Per-entity detail ─────────────────────────────────────

function renderEntityDetail(doc, cursor, detail, index) {
  // Always start a new page for each flagged entity
  addPage(doc, cursor);

  // Entity header
  setHeading1(doc);
  doc.text(`Entity ${index + 1}`, MARGIN_L, cursor.y);
  cursor.y += 7;

  setHeading2(doc);
  doc.text(display(detail.entity_name), MARGIN_L, cursor.y);
  cursor.y += 5;

  setMuted(doc);
  doc.setFontSize(8);
  const bandStr = display(detail.risk_band).toUpperCase();
  const scoreStr = detail.risk_score !== NA
    ? `Risk Score: ${Number(detail.risk_score).toFixed(3)}`
    : "Risk Score: —";
  doc.text(`${scoreStr}   |   Band: ${bandStr}   |   Primary Driver: ${display(detail.primary_driver)}`, MARGIN_L, cursor.y);
  cursor.y += 5;

  doc.setDrawColor(...DIVIDER);
  doc.setLineWidth(0.3);
  doc.line(MARGIN_L, cursor.y, PAGE_W - MARGIN_R, cursor.y);
  cursor.y += 6;

  // ── Section 3: Why Flagged ─────────────────────────────────────────────
  drawSectionTitle(doc, cursor, "3  Why Flagged", 2);

  if (!detail.findings || detail.findings.length === 0) {
    drawParagraph(doc, cursor, "No findings recorded for this entity.");
  } else {
    detail.findings.forEach((finding, fi) => {
      ensureSpace(doc, cursor, 20);
      setHeading3(doc);
      doc.text(`Finding ${fi + 1}: ${trunc(finding.rule, 80)}`, MARGIN_L, cursor.y);
      cursor.y += 5;

      drawKV(doc, cursor, "Detector", finding.detector, 36);
      drawKV(doc, cursor, "Description", finding.description, 36);
      drawKV(doc, cursor, "Evidence Count", finding.evidence_count, 36);

      if (finding.evidence && finding.evidence.length > 0) {
        ensureSpace(doc, cursor, 20);
        setMuted(doc);
        doc.setFontSize(7.5);
        doc.text("EVIDENCE ITEMS", MARGIN_L, cursor.y);
        cursor.y += 4;

        const evHead = ["Detail", "Reason"];
        const evBody = finding.evidence.map((ev) => [
          trunc(ev.detail, 100),
          trunc(ev.reason, 80),
        ]);
        drawTable(doc, cursor, evHead, evBody, [0.58, 0.42]);
      }

      cursor.y += 3;
    });
  }

  // ── Section 4: Expected vs Observed ───────────────────────────────────
  if (detail.expected_vs_observed && detail.expected_vs_observed.length > 0) {
    ensureSpace(doc, cursor, 20);
    drawSectionTitle(doc, cursor, "4  Expected vs Observed", 2);

    const evoHead = ["Metric", "Observed", "Expected", "Unit", "Z-Score", "Direction", "Interpretation"];
    const evoWidths = [0.20, 0.10, 0.10, 0.08, 0.09, 0.10, 0.33];
    const evoBody = detail.expected_vs_observed.map((row) => [
      trunc(row.metric, 40),
      display(row.observed),
      display(row.expected),
      display(row.unit),
      row.deviation_z !== NA ? String(Number(row.deviation_z).toFixed(2)) : "—",
      display(row.direction),
      trunc(row.interpretation, 80),
    ]);
    drawTable(doc, cursor, evoHead, evoBody, evoWidths);
  }

  // ── Section 5: Trend ──────────────────────────────────────────────────
  if (detail.trend) {
    ensureSpace(doc, cursor, 20);
    drawSectionTitle(doc, cursor, "5  Trend / Temporal Analysis", 2);

    drawKV(doc, cursor, "Direction", detail.trend.direction, 36);
    drawKV(doc, cursor, "Volatility", detail.trend.volatility !== NA
      ? Number(detail.trend.volatility).toFixed(4)
      : NA, 36);

    if (detail.trend.points && detail.trend.points.length > 0) {
      const tHead = ["Run ID", "Timestamp", "Risk Score"];
      const tBody = detail.trend.points.map((p) => [
        display(p.run_id),
        display(p.timestamp),
        p.risk_score !== NA ? String(Number(p.risk_score).toFixed(3)) : "—",
      ]);
      drawTable(doc, cursor, tHead, tBody, [0.22, 0.50, 0.28]);
    }
  }
}

// ── Section 6 — Audit / Assessment Metadata ───────────────────────────────

function renderAuditMetadata(doc, cursor, meta) {
  ensureSpace(doc, cursor, 50);
  drawSectionTitle(doc, cursor, "6  Audit / Assessment Metadata");

  if (!meta) {
    drawParagraph(doc, cursor, "Audit metadata not available for this assessment.");
    return;
  }

  drawKV(doc, cursor, "Run ID",        meta.id);
  drawKV(doc, cursor, "Timestamp",     meta.timestamp);
  drawKV(doc, cursor, "Source File",   meta.filename);
  drawKV(doc, cursor, "Rows Received", meta.rows_received);
  drawKV(doc, cursor, "Rows Inserted", meta.rows_inserted);
  drawKV(doc, cursor, "Rows Skipped",  meta.rows_skipped);
  drawKV(doc, cursor, "Entity Count",  meta.entity_count);

  cursor.y += 3;

  // Detector config — render as a formatted block if it's an object
  setMuted(doc);
  doc.setFontSize(7.5);
  doc.text("DETECTOR CONFIGURATION SNAPSHOT", MARGIN_L, cursor.y);
  cursor.y += 4;

  const cfg = meta.detector_config;
  if (cfg === NA || cfg === null || cfg === undefined) {
    drawParagraph(doc, cursor, NA);
  } else {
    const cfgStr = typeof cfg === "object"
      ? JSON.stringify(cfg, null, 2)
      : String(cfg);
    ensureSpace(doc, cursor, 20);
    setBody(doc);
    doc.setFontSize(7.5);
    const lines = doc.splitTextToSize(cfgStr, CONTENT_W);
    // Guard: very long configs get truncated to keep the PDF manageable
    const maxLines = 60;
    const rendered = lines.length > maxLines
      ? [...lines.slice(0, maxLines), "… [truncated — see JSON export for full config]"]
      : lines;
    rendered.forEach((line) => {
      if (cursor.y > FOOTER_Y - 10) addPage(doc, cursor);
      doc.text(line, MARGIN_L, cursor.y);
      cursor.y += 4;
    });
    cursor.y += 3;
  }
}

// ── Section 7 — Supervisory Review Template ───────────────────────────────

function renderSupervisoryReviewTemplate(doc, cursor) {
  ensureSpace(doc, cursor, 60);
  drawSectionTitle(doc, cursor, "7  Supervisory Review");

  setMuted(doc);
  doc.setFontSize(8);
  doc.text(
    "Complete the fields below after conducting the supervisory review of this assessment.",
    MARGIN_L, cursor.y
  );
  cursor.y += 8;

  const fields = [
    "Final Supervisory Decision",
    "Supporting Rationale",
    "Examiner Name / ID",
    "Review Date",
    "Additional Notes",
  ];

  fields.forEach((label) => {
    ensureSpace(doc, cursor, 20);
    setMuted(doc);
    doc.setFontSize(7.5);
    doc.text(label.toUpperCase(), MARGIN_L, cursor.y);
    cursor.y += 3;

    // Blank ruled line(s)
    doc.setDrawColor(...DIVIDER);
    doc.setLineWidth(0.3);
    doc.line(MARGIN_L, cursor.y + 3, PAGE_W - MARGIN_R, cursor.y + 3);
    if (label === "Supporting Rationale" || label === "Additional Notes") {
      doc.line(MARGIN_L, cursor.y + 8, PAGE_W - MARGIN_R, cursor.y + 8);
      doc.line(MARGIN_L, cursor.y + 13, PAGE_W - MARGIN_R, cursor.y + 13);
      cursor.y += 18;
    } else {
      cursor.y += 8;
    }
  });

  cursor.y += 4;
}

// ── Section 8 — Disclaimer ─────────────────────────────────────────────────

function renderDisclaimer(doc, cursor, disclaimerText) {
  ensureSpace(doc, cursor, 40);
  drawSectionTitle(doc, cursor, "8  Disclaimer");
  setMuted(doc);
  doc.setFontSize(8);
  const lines = doc.splitTextToSize(disclaimerText, CONTENT_W);
  doc.text(lines, MARGIN_L, cursor.y);
  cursor.y += lines.length * 4.5 + 4;
}

// ── Main export ────────────────────────────────────────────────────────────

// ── Main exports ───────────────────────────────────────────────────────────

/**
 * buildEntityPDF(reportData)
 *
 * Renders a single entity's dossier report as a jsPDF document and triggers
 * a browser download.
 *
 * @param {Object} reportData — as returned by assembleEntityReportData()
 */
export function buildEntityPDF(reportData) {
  const doc = new jsPDF({ unit: "mm", format: "a4", orientation: "portrait" });

  const { _meta, entity_summary, findings, expected_vs_observed, trend, audit_metadata, disclaimer, report_hash } = reportData;

  // ── Cover page (page 1) ──────────────────────────────────────────────────
  doc.setFillColor(...ACCENT);
  doc.rect(0, 0, PAGE_W, 4, "F");

  doc.setFont("helvetica", "bold");
  doc.setFontSize(28);
  doc.setTextColor(...BLACK);
  doc.text("SAT-SA", MARGIN_L, 50);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(14);
  doc.setTextColor(...GRAY);
  doc.text("Supervisory Entity Assessment Dossier", MARGIN_L, 62);

  doc.setFontSize(9);
  doc.setTextColor(...ACCENT);
  doc.text("VEIL — Visibility and Evidence Intelligence Layer", MARGIN_L, 72);

  doc.setDrawColor(...DIVIDER);
  doc.setLineWidth(0.4);
  doc.line(MARGIN_L, 80, PAGE_W - MARGIN_R, 80);

  // Entity Highlight Card
  const cardY = 90;
  doc.setFillColor(248, 250, 252);
  doc.setDrawColor(...DIVIDER);
  doc.roundedRect(MARGIN_L, cardY, CONTENT_W, 36, 2, 2, "FD");

  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.setTextColor(...BLACK);
  doc.text(display(_meta?.entity_name), MARGIN_L + 8, cardY + 12);

  const band = (entity_summary?.risk_band || "").toLowerCase();
  const bandCol = bandColor(band);
  doc.setFontSize(10);
  doc.setTextColor(...bandCol);
  const scoreText = entity_summary?.risk_score !== NA
    ? `Risk Score: ${Number(entity_summary.risk_score).toFixed(1)} / 100 (${band.toUpperCase()})`
    : "Risk Score: —";
  doc.text(scoreText, MARGIN_L + 8, cardY + 20);

  doc.setFont("helvetica", "normal");
  doc.setFontSize(8.5);
  doc.setTextColor(...GRAY);
  doc.text(`Primary Driver: ${display(entity_summary?.primary_driver)}`, MARGIN_L + 8, cardY + 28);

  // Metadata block
  const kvY = 140;
  const labelW = 52;
  const lineH = 9;

  const fields = [
    ["Generated", display(_meta?.generated_at_display)],
    ["Assessment Run", display(_meta?.run_id)],
    ["Schema Version", display(reportData.report_schema_version || "1.0")],
    ["Report Hash", report_hash ? trunc(report_hash, 48) : "—"],
  ];

  fields.forEach(([label, value], i) => {
    const y = kvY + i * lineH;
    doc.setFontSize(8);
    doc.setTextColor(...GRAY);
    doc.text(label.toUpperCase(), MARGIN_L, y);
    doc.setFontSize(9);
    doc.setTextColor(...BLACK);
    doc.text(value, MARGIN_L + labelW, y);
  });

  // Classification notice at bottom
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.setTextColor(...GRAY);
  doc.text(
    "FOR AUTHORIZED SUPERVISORY USE ONLY",
    PAGE_W / 2,
    PAGE_H - 25,
    { align: "center" }
  );
  doc.setFont("helvetica", "normal");
  doc.setFontSize(7.5);
  doc.text(
    "Handle in accordance with applicable data-handling policies.",
    PAGE_W / 2,
    PAGE_H - 20,
    { align: "center" }
  );

  // ── Content pages ────────────────────────────────────────────────────────
  doc.addPage();
  drawFooter(doc);
  const cursor = makeCursor(22);

  // Section 1: Executive Summary & Component Breakdown
  drawSectionTitle(doc, cursor, "1  Executive Summary & Component Scores");

  const comp = entity_summary?.component_scores || {};
  const compHead = ["Component Detector", "Score", "Weight", "Description"];
  const compBody = [
    ["Execution Gap", comp.execution_gap !== NA ? String(Number(comp.execution_gap).toFixed(2)) : "—", "40%", "Triaged closure anomalies & investigation note duplication"],
    ["Negative Space", comp.negative_space !== NA ? String(Number(comp.negative_space).toFixed(2)) : "—", "35%", "Statistical gaps in reported severities or alert volumes"],
    ["Anomaly Drift", comp.anomaly !== NA ? String(Number(comp.anomaly).toFixed(2)) : "—", "25%", "Isolation Forest peer multi-feature drift"],
  ];
  drawTable(doc, cursor, compHead, compBody, [0.25, 0.12, 0.12, 0.51]);

  // Peer benchmark comparisons if available
  if (entity_summary?.peer_metrics) {
    ensureSpace(doc, cursor, 24);
    setHeading3(doc);
    doc.text("Peer Group Benchmark Comparisons", MARGIN_L, cursor.y);
    cursor.y += 5;

    const pm = entity_summary.peer_metrics;
    const pmHead = ["Metric", "Observed Value", "Peer Median", "Variance"];
    const pmBody = [];

    if (pm.avg_closure_seconds) {
      const entM = Math.round(pm.avg_closure_seconds.entity / 60);
      const peerM = Math.round(pm.avg_closure_seconds.peer_median / 60);
      pmBody.push(["Avg Closure Time", `${entM} min`, `${peerM} min`, `${entM - peerM >= 0 ? `+${entM - peerM}` : entM - peerM} min`]);
    }
    if (pm.escalation_rate) {
      const entR = Math.round(pm.escalation_rate.entity * 100);
      const peerR = Math.round(pm.escalation_rate.peer_median * 100);
      pmBody.push(["Escalation Rate", `${entR}%`, `${peerR}%`, `${entR - peerR >= 0 ? `+${entR - peerR}` : entR - peerR}%`]);
    }
    if (pm.avg_note_length) {
      const entN = Math.round(pm.avg_note_length.entity);
      const peerN = Math.round(pm.avg_note_length.peer_median);
      pmBody.push(["Avg Note Length", `${entN} chars`, `${peerN} chars`, `${entN - peerN >= 0 ? `+${entN - peerN}` : entN - peerN} chars`]);
    }
    if (pm.alert_count) {
      const entA = pm.alert_count.entity;
      const peerA = Math.round(pm.alert_count.peer_median);
      pmBody.push(["Alert Count", `${entA}`, `${peerA}`, `${entA - peerA >= 0 ? `+${entA - peerA}` : entA - peerA}`]);
    }

    if (pmBody.length > 0) {
      drawTable(doc, cursor, pmHead, pmBody, [0.35, 0.22, 0.22, 0.21]);
    }
  }

  // Section 2: Why Flagged (Findings & Evidence)
  ensureSpace(doc, cursor, 24);
  drawSectionTitle(doc, cursor, "2  Why Flagged (Evidence & Rule Triggers)");

  if (!findings || findings.length === 0) {
    drawParagraph(doc, cursor, "No suspicious rules or behavioral findings recorded for this entity.");
  } else {
    findings.forEach((finding, fi) => {
      ensureSpace(doc, cursor, 20);
      setHeading3(doc);
      doc.text(`Finding ${fi + 1}: ${trunc(finding.rule, 80)}`, MARGIN_L, cursor.y);
      cursor.y += 5;

      drawKV(doc, cursor, "Detector", finding.detector, 36);
      drawKV(doc, cursor, "Description", finding.description, 36);
      drawKV(doc, cursor, "Evidence Count", finding.evidence_count, 36);

      if (finding.evidence && finding.evidence.length > 0) {
        ensureSpace(doc, cursor, 20);
        setMuted(doc);
        doc.setFontSize(7.5);
        doc.text("EVIDENCE ITEMS", MARGIN_L, cursor.y);
        cursor.y += 4;

        const evHead = ["Detail", "Reason"];
        const evBody = finding.evidence.map((ev) => [
          trunc(ev.detail, 100),
          trunc(ev.reason, 80),
        ]);
        drawTable(doc, cursor, evHead, evBody, [0.58, 0.42]);
      }
      cursor.y += 3;
    });
  }

  // Section 3: Expected vs Observed
  if (expected_vs_observed && expected_vs_observed.length > 0) {
    ensureSpace(doc, cursor, 24);
    drawSectionTitle(doc, cursor, "3  Expected vs Observed Baseline Deviation");

    const evoHead = ["Metric", "Observed", "Expected", "Unit", "Z-Score", "Direction", "Interpretation"];
    const evoWidths = [0.20, 0.10, 0.10, 0.08, 0.09, 0.10, 0.33];
    const evoBody = expected_vs_observed.map((row) => [
      trunc(row.metric, 40),
      display(row.observed),
      display(row.expected),
      display(row.unit),
      row.deviation_z !== NA ? String(Number(row.deviation_z).toFixed(2)) : "—",
      display(row.direction),
      trunc(row.interpretation, 80),
    ]);
    drawTable(doc, cursor, evoHead, evoBody, evoWidths);
  }

  // Section 4: Temporal / Trend Analysis
  if (trend) {
    ensureSpace(doc, cursor, 24);
    drawSectionTitle(doc, cursor, "4  Temporal / Trend Trajectory");

    drawKV(doc, cursor, "Direction", trend.direction, 36);
    drawKV(doc, cursor, "Volatility", trend.volatility !== NA
      ? Number(trend.volatility).toFixed(4)
      : NA, 36);

    if (trend.points && trend.points.length > 0) {
      const tHead = ["Run ID", "Timestamp", "Risk Score"];
      const tBody = trend.points.map((p) => [
        display(p.run_id),
        display(p.timestamp),
        p.risk_score !== NA ? String(Number(p.risk_score).toFixed(3)) : "—",
      ]);
      drawTable(doc, cursor, tHead, tBody, [0.22, 0.50, 0.28]);
    }
  }

  // Section 5: Audit & Telemetry Context
  ensureSpace(doc, cursor, 24);
  renderAuditMetadata(doc, cursor, audit_metadata);

  // Section 6: Supervisory Review Template
  renderSupervisoryReviewTemplate(doc, cursor);

  // Section 7: Disclaimer
  renderDisclaimer(doc, cursor, disclaimer);

  // Trigger download
  const filename = buildFileName(reportData, "pdf");
  doc.save(filename);
}

/**
 * buildPDF(reportData)
 *
 * Renders the full assessment report as a jsPDF document and triggers
 * a browser download.
 *
 * @param {Object} reportData — as returned by assembleReportData()
 */
export function buildPDF(reportData) {
  if (reportData?._meta?.mode === "entity") {
    return buildEntityPDF(reportData);
  }

  const doc = new jsPDF({ unit: "mm", format: "a4", orientation: "portrait" });

  const { _meta, overview, supervisory_priority, entity_details, audit_metadata, disclaimer } = reportData;

  // ── Cover page (page 1) ──────────────────────────────────────────────────
  renderCoverPage(doc, _meta);

  // ── Content pages ────────────────────────────────────────────────────────
  doc.addPage();
  drawFooter(doc);
  const cursor = makeCursor(22);

  // Section 1
  renderOverview(doc, cursor, overview);

  // Section 2
  renderPriorityTable(doc, cursor, supervisory_priority);

  // Sections 3–5 — one page-break per flagged entity
  if (entity_details && entity_details.length > 0) {
    entity_details.forEach((detail, i) => {
      renderEntityDetail(doc, cursor, detail, i);
    });
  } else {
    ensureSpace(doc, cursor, 20);
    drawSectionTitle(doc, cursor, "3–5  Entity Findings / Trend");
    drawParagraph(
      doc, cursor,
      "No entities met the threshold for full supervisory review (high or critical risk band, or non-empty findings). All entities are represented in the Priority table above."
    );
  }

  // Section 6
  ensureSpace(doc, cursor, 20);
  renderAuditMetadata(doc, cursor, audit_metadata);

  // Section 7
  renderSupervisoryReviewTemplate(doc, cursor);

  // Section 8
  renderDisclaimer(doc, cursor, disclaimer);

  // ── Trigger download ─────────────────────────────────────────────────────
  const filename = buildFileName(reportData, "pdf");
  doc.save(filename);
}
