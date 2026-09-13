import { Scale, Info } from "lucide-react";

/**
 * ExpectedObserved Component
 *
 * Visualizes structured "Expected vs Observed" operational baselines
 * (e.g., peer expectation vs actual entity telemetry for Negative Space analysis).
 *
 * Interface accepts an array of structured items:
 * [
 *   {
 *     metric: string,
 *     expected: string | number,
 *     observed: string | number,
 *     difference: string | number,
 *     status: "NORMAL" | "ELEVATED" | "DEVIANT" | "CRITICAL"
 *   }
 * ]
 *
 * If the current backend does NOT expose structured expected-vs-observed data,
 * it displays an honest, professional empty state without fabricating numbers.
 */
export default function ExpectedObserved({ data = null }) {
  // Check if structured expected_vs_observed items were provided by the backend
  const items = Array.isArray(data) ? data : data?.expected_vs_observed;
  const hasStructuredData = Array.isArray(items) && items.length > 0;

  return (
    <section className="ranking-panel" style={{ marginTop: "30px" }}>
      <div className="panel-header">
        <div>
          <div className="panel-label">NEGATIVE SPACE ANALYSIS</div>
          <h2>Expected vs Observed</h2>
          <p style={{ margin: "4px 0 0", fontSize: "14px", color: "var(--muted)", maxWidth: "600px" }}>
            Contrasts peer baseline operational expectations against observed entity metrics to detect absence of expected security activity.
          </p>
        </div>
        <span className="panel-meta">BASELINE TELEMETRY DEVIATION</span>
      </div>

      {!hasStructuredData ? (
        <div className="empty-state" style={{ minHeight: "180px", padding: "40px 24px" }}>
          <Scale size={28} color="var(--muted)" />
          <h3 style={{ marginTop: "12px", color: "var(--text)", fontSize: "14px" }}>
            Expected vs Observed metrics are not available in the current assessment response.
          </h3>
          <p
            style={{
              maxWidth: "520px",
              color: "var(--muted)",
              fontSize: "14px",
              lineHeight: 1.6,
              marginTop: "6px",
            }}
          >
            The backend API currently delivers peer median metrics and detector rule findings. UI is ready for structured expected/observed backend data when exposed by the analytics engine.
          </p>
          <div
            style={{
              marginTop: "16px",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 10px",
              borderRadius: "2px",
              background: "rgba(86, 199, 255, 0.08)",
              border: "1px solid rgba(86, 199, 255, 0.2)",
              color: "var(--accent)",
              fontSize: "12px",
              fontWeight: 600,
            }}
          >
            <Info size={13} />
            <span>UI schema ready for telemetry integration</span>
          </div>
        </div>
      ) : (
        <div style={{ overflowX: "auto", width: "100%" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "13px",
              textAlign: "left",
              minWidth: "600px",
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: "1px solid var(--line)",
                  color: "var(--muted)",
                  fontSize: "11px",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                <th style={{ padding: "14px 18px" }}>Metric</th>
                <th style={{ padding: "14px 18px" }}>Expected Baseline</th>
                <th style={{ padding: "14px 18px" }}>Observed Telemetry</th>
                <th style={{ padding: "14px 18px" }}>Deviation</th>
                <th style={{ padding: "14px 18px" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row, idx) => {
                const statusUpper = (row.status || "NORMAL").toUpperCase();
                const isDeviant = statusUpper === "DEVIANT" || statusUpper === "CRITICAL" || statusUpper === "ELEVATED";

                return (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      backgroundColor: isDeviant ? "rgba(239, 107, 114, 0.04)" : "transparent",
                    }}
                  >
                    <td style={{ padding: "14px 18px", color: "var(--text)", fontWeight: 600 }}>
                      {row.metric}
                    </td>
                    <td style={{ padding: "14px 18px", color: "var(--muted)" }}>
                      {row.expected}
                    </td>
                    <td style={{ padding: "14px 18px", color: "var(--text)" }}>
                      {row.observed}
                    </td>
                    <td
                      style={{
                        padding: "14px 18px",
                        color: isDeviant ? "var(--red)" : "var(--green)",
                        fontWeight: 600,
                      }}
                    >
                      {row.difference}
                    </td>
                    <td style={{ padding: "14px 18px" }}>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "2px 8px",
                          borderRadius: "2px",
                          fontSize: "11px",
                          fontWeight: 700,
                          letterSpacing: "0.08em",
                          backgroundColor: isDeviant ? "rgba(239, 107, 114, 0.15)" : "rgba(87, 213, 140, 0.12)",
                          color: isDeviant ? "var(--red)" : "var(--green)",
                          border: `1px solid ${isDeviant ? "rgba(239, 107, 114, 0.3)" : "rgba(87, 213, 140, 0.3)"}`,
                        }}
                      >
                        {statusUpper}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
