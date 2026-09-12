import { Database, Building2, History, FileCode } from "lucide-react";

export default function DatasetScale({
  totalAlerts = 0,
  entitiesCount = 0,
  auditRunsCount = null,
  latestRun = null,
  inputFormat = "CSV / JSON",
}) {
  return (
    <section className="benchmark-section" style={{ marginTop: "30px" }}>
      <div className="panel-header">
        <div>
          <div className="panel-label">OPERATIONAL TELEMETRY SCALE</div>
          <h2>Dataset / Analysis Scale</h2>
          <p style={{ margin: "4px 0 0", fontSize: "12px", color: "var(--muted)", maxWidth: "600px" }}>
            Real metrics detailing the operational scope, record volume, and ingestion integrity for the active assessment run.
          </p>
        </div>
        <span className="panel-meta">ACTIVE RUN SCOPE</span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: "1px",
          backgroundColor: "var(--line)",
          border: "1px solid var(--line)",
          marginTop: "16px",
        }}
      >
        {/* Metric 1: Alerts Analyzed */}
        <div
          style={{
            backgroundColor: "var(--surface)",
            padding: "20px 22px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "10px", color: "var(--muted)", letterSpacing: "0.1em", fontWeight: 700 }}>
              ALERTS ANALYZED
            </span>
            <Database size={15} color="var(--accent)" />
          </div>
          <strong style={{ fontSize: "28px", color: "var(--text)", lineHeight: 1 }}>
            {totalAlerts.toLocaleString()}
          </strong>
          <small style={{ fontSize: "11px", color: "var(--muted)" }}>
            Normalized operational alert records
          </small>
        </div>

        {/* Metric 2: Entities Assessed */}
        <div
          style={{
            backgroundColor: "var(--surface)",
            padding: "20px 22px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "10px", color: "var(--muted)", letterSpacing: "0.1em", fontWeight: 700 }}>
              ENTITIES ASSESSED
            </span>
            <Building2 size={15} color="var(--accent)" />
          </div>
          <strong style={{ fontSize: "28px", color: "var(--text)", lineHeight: 1 }}>
            {entitiesCount}
          </strong>
          <small style={{ fontSize: "11px", color: "var(--muted)" }}>
            Distinct peer organizations evaluated
          </small>
        </div>

        {/* Metric 3: Assessment Runs */}
        <div
          style={{
            backgroundColor: "var(--surface)",
            padding: "20px 22px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "10px", color: "var(--muted)", letterSpacing: "0.1em", fontWeight: 700 }}>
              ASSESSMENT RUNS
            </span>
            <History size={15} color="var(--accent)" />
          </div>
          <strong style={{ fontSize: "28px", color: "var(--text)", lineHeight: 1 }}>
            {auditRunsCount !== null ? auditRunsCount : "—"}
          </strong>
          <small style={{ fontSize: "11px", color: "var(--muted)" }}>
            Historical runs in persistent audit trail
          </small>
        </div>

        {/* Metric 4: Ingestion Format & Integrity */}
        <div
          style={{
            backgroundColor: "var(--surface)",
            padding: "20px 22px",
            display: "flex",
            flexDirection: "column",
            gap: "8px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: "10px", color: "var(--muted)", letterSpacing: "0.1em", fontWeight: 700 }}>
              INGESTION FORMAT
            </span>
            <FileCode size={15} color="var(--accent)" />
          </div>
          <strong style={{ fontSize: "24px", color: "var(--text)", lineHeight: 1 }}>
            {latestRun?.format ? latestRun.format.toUpperCase() : inputFormat}
          </strong>
          <small style={{ fontSize: "11px", color: "var(--muted)" }}>
            {latestRun
              ? `${latestRun.rows_inserted || 0} inserted / ${latestRun.rows_received || 0} received`
              : "Air-gapped offline ingestion"}
          </small>
        </div>
      </div>
    </section>
  );
}
