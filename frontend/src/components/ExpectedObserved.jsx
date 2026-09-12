import { Scale, Info } from "lucide-react";

/**
 * ExpectedObserved Component
 *
 * Visualizes structured "Expected vs Observed" operational baselines
 * (peer expectation vs actual entity telemetry for Negative Space analysis).
 *
 * Consumes the `expected_vs_observed` array from GET /api/entities/{name}
 * (see ExpectedVsObservedItem in schemas.py), one row per metric:
 * [
 *   {
 *     metric: string,
 *     metric_key: string,
 *     observed: number,
 *     expected: number,
 *     unit: string,
 *     deviation_z: number,
 *     direction: "below" | "above" | "aligned",
 *     interpretation: string,
 *   }
 * ]
 *
 * The API has no `status` or `difference` field — the badge is derived here
 * from `direction` plus the magnitude of `deviation_z`, and `deviation_z`
 * itself (not a precomputed "difference") is what's shown in that column.
 * `interpretation` is a ready-made plain-language sentence from the backend
 * and is surfaced directly under each metric — it's the most useful single
 * piece of information in the response for a supervisor scanning this table.
 *
 * If the current backend does NOT expose structured expected-vs-observed data,
 * it displays an honest, professional empty state without fabricating numbers.
 */

const DEVIANT_Z_THRESHOLD = 2.5;
const CRITICAL_Z_THRESHOLD = 5.0;

/**
 * Derive a status badge from `direction` and the magnitude of `deviation_z`.
 *
 * The API's `direction` already encodes "aligned" (|deviation_z| under the
 * backend's own EXPECTED_ALIGNED_Z_THRESHOLD) vs "below"/"above" — this only
 * adds a severity tier on top of "below"/"above", scaled the same way the
 * negative_space/anomaly detectors already grade deviation magnitude
 * elsewhere in this app, rather than inventing a new scale.
 */
function deriveStatus(direction, deviationZ) {
  if (direction !== "below" && direction !== "above") {
    return { label: "NORMAL", isDeviant: false };
  }
  const magnitude = Math.abs(deviationZ ?? 0);
  if (magnitude >= CRITICAL_Z_THRESHOLD) {
    return { label: "CRITICAL", isDeviant: true };
  }
  if (magnitude >= DEVIANT_Z_THRESHOLD) {
    return { label: "DEVIANT", isDeviant: true };
  }
  return { label: "ELEVATED", isDeviant: true };
}

function formatDirection(direction) {
  if (direction === "above") return "▲ above";
  if (direction === "below") return "▼ below";
  return "aligned";
}

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
          <p style={{ margin: "4px 0 0", fontSize: "12px", color: "var(--muted)", maxWidth: "600px" }}>
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
              fontSize: "12px",
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
              fontSize: "11px",
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
              fontSize: "12px",
              textAlign: "left",
              minWidth: "600px",
            }}
          >
            <thead>
              <tr
                style={{
                  borderBottom: "1px solid var(--line)",
                  color: "var(--muted)",
                  fontSize: "10px",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                <th style={{ padding: "14px 18px" }}>Metric</th>
                <th style={{ padding: "14px 18px" }}>Expected Baseline</th>
                <th style={{ padding: "14px 18px" }}>Observed Telemetry</th>
                <th style={{ padding: "14px 18px" }}>Deviation (z)</th>
                <th style={{ padding: "14px 18px" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row, idx) => {
                const { label: statusLabel, isDeviant } = deriveStatus(row.direction, row.deviation_z);
                const unitSuffix = row.unit ? ` ${row.unit}` : "";

                return (
                  <tr
                    key={idx}
                    style={{
                      borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      backgroundColor: isDeviant ? "rgba(239, 107, 114, 0.04)" : "transparent",
                    }}
                  >
                    <td style={{ padding: "14px 18px", color: "var(--text)" }}>
                      <div style={{ fontWeight: 600 }}>{row.metric}</div>
                      {row.interpretation && (
                        <div
                          style={{
                            marginTop: "4px",
                            color: "var(--muted)",
                            fontWeight: 400,
                            fontSize: "11px",
                            lineHeight: 1.5,
                            maxWidth: "420px",
                          }}
                        >
                          {row.interpretation}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: "14px 18px", color: "var(--muted)" }}>
                      {row.expected}
                      {unitSuffix}
                    </td>
                    <td style={{ padding: "14px 18px", color: "var(--text)" }}>
                      {row.observed}
                      {unitSuffix}
                    </td>
                    <td
                      style={{
                        padding: "14px 18px",
                        color: isDeviant ? "var(--red)" : "var(--green)",
                        fontWeight: 600,
                      }}
                    >
                      {typeof row.deviation_z === "number" ? row.deviation_z.toFixed(2) : row.deviation_z}
                      <span style={{ marginLeft: "6px", color: "var(--muted)", fontWeight: 400, fontSize: "11px" }}>
                        {formatDirection(row.direction)}
                      </span>
                    </td>
                    <td style={{ padding: "14px 18px" }}>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "2px 8px",
                          borderRadius: "2px",
                          fontSize: "9px",
                          fontWeight: 700,
                          letterSpacing: "0.08em",
                          backgroundColor: isDeviant ? "rgba(239, 107, 114, 0.15)" : "rgba(87, 213, 140, 0.12)",
                          color: isDeviant ? "var(--red)" : "var(--green)",
                          border: `1px solid ${isDeviant ? "rgba(239, 107, 114, 0.3)" : "rgba(87, 213, 140, 0.3)"}`,
                        }}
                      >
                        {statusLabel}
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
