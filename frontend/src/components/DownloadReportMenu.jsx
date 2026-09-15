/**
 * DownloadReportMenu.jsx
 *
 * Button + dropdown to export the Assessment Report as PDF or JSON.
 * Mounts in DashboardPage's header next to the .dataset-info block.
 *
 * Props:
 *   entities   {Array}  — from getRiskScores() (already loaded on Dashboard)
 *   auditRuns  {Array}  — from getAuditRuns()  (already loaded on Dashboard)
 *
 * Behaviour:
 *   - Hidden (returns null) when entities.length === 0 — no assessment data.
 *   - Dropdown opens on button click; closes on outside click or Escape key.
 *   - Clicking PDF or JSON triggers the respective generation pipeline.
 *   - During generation the trigger button shows a spinner and is disabled
 *     (prevents duplicate-click double-downloads).
 *   - On failure, an inline error message is displayed below the button;
 *     full error is also written to console.error.
 */

import { useEffect, useRef, useState } from "react";
import { ChevronDown, FileText, FileJson, FileSpreadsheet, Loader, CheckCircle } from "lucide-react";
import { assembleReportData, assembleEntityReportData, downloadJSON, downloadCSV } from "../lib/assessmentReport";
import { buildPDF } from "../lib/pdfReportBuilder";

export default function DownloadReportMenu({
  mode = "overview",
  entities,
  auditRuns,
  entityData,
  entityName,
}) {
  const [open, setOpen] = useState(false);
  const [generating, setGenerating] = useState(false); // "pdf" | "json" | "csv" | false
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null); // { time: "HH:MM" } | null
  const containerRef = useRef(null);
  const toastTimerRef = useRef(null);

  // ── Close on outside click ───────────────────────────────────────────────
  useEffect(() => {
    function handleOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    function handleEscape(e) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  // ── Clear toast timer on unmount ──────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    };
  }, []);

  // ── Guards: no data → render nothing ──────────────────────────────────────
  if (mode === "overview" && (!entities || entities.length === 0)) return null;
  if (mode === "entity" && !entityData && !entityName) return null;

  async function handleGenerate(format) {
    setOpen(false);
    setError(null);
    setToast(null);
    setGenerating(format);
    try {
      let reportData;
      if (mode === "entity") {
        reportData = await assembleEntityReportData(
          entityName || entityData?.entity_name,
          entityData,
          auditRuns
        );
      } else {
        reportData = await assembleReportData(entities, auditRuns || []);
      }

      if (format === "pdf") {
        buildPDF(reportData);
      } else if (format === "csv") {
        downloadCSV(reportData);
      } else {
        downloadJSON(reportData);
      }

      // Show toast with current time
      const now = new Date();
      const pad = (n) => String(n).padStart(2, "0");
      const time = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
      setToast({ time });
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
      toastTimerRef.current = setTimeout(() => setToast(null), 4000);
    } catch (err) {
      console.error("[DownloadReportMenu] Report generation failed:", err);
      setError("Report generation failed — please retry.");
    } finally {
      setGenerating(false);
    }
  }

  const isLoading = generating !== false;
  const buttonLabel = mode === "entity" ? "DOWNLOAD REPORT" : "DOWNLOAD ASSESSMENT";

  return (
    <div className="download-report-menu" ref={containerRef}>
      {/* Trigger button */}
      <button
        className="download-report-trigger"
        onClick={() => !isLoading && setOpen((prev) => !prev)}
        disabled={isLoading}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label={mode === "entity" ? "Download Entity Report" : "Download Assessment Report"}
      >
        {isLoading ? (
          <>
            <Loader size={13} className="download-report-spinner" aria-hidden="true" />
            <span>
              {generating === "pdf"
                ? "Generating PDF…"
                : generating === "csv"
                ? "Generating CSV…"
                : "Generating JSON…"}
            </span>
          </>
        ) : (
          <>
            <span>{buttonLabel}</span>
            <ChevronDown
              size={13}
              className={`download-report-chevron${open ? " open" : ""}`}
              aria-hidden="true"
            />
          </>
        )}
      </button>

      {/* Dropdown */}
      {open && !isLoading && (
        <div className="download-report-dropdown" role="menu">
          <button
            className="download-report-item"
            role="menuitem"
            onClick={() => handleGenerate("pdf")}
          >
            <FileText size={14} aria-hidden="true" />
            <span>Download PDF</span>
          </button>
          <button
            className="download-report-item"
            role="menuitem"
            onClick={() => handleGenerate("json")}
          >
            <FileJson size={14} aria-hidden="true" />
            <span>Download JSON</span>
          </button>
          <button
            className="download-report-item"
            role="menuitem"
            onClick={() => handleGenerate("csv")}
          >
            <FileSpreadsheet size={14} aria-hidden="true" />
            <span>Download CSV</span>
            <span className="download-report-item-hint">
              {mode === "entity" ? "dossier data" : "priority table"}
            </span>
          </button>
        </div>
      )}

      {/* Success toast */}
      {toast && (
        <div className="download-report-toast" role="status" aria-live="polite">
          <CheckCircle size={13} aria-hidden="true" />
          <span>Report generated at {toast.time}</span>
        </div>
      )}

      {/* Inline error */}
      {error && (
        <p className="download-report-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
