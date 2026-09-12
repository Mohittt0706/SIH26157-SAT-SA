import { useState, useEffect } from "react";
import {
  TrendingDown,
  TrendingUp,
  Minus,
  Clock,
  AlertCircle,
  Layers,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { getAuditRuns, getAuditRunDetail } from "../lib/api";

export default function TrendPanel({ entityName }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showComponents, setShowComponents] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function fetchEntityHistory() {
      if (!entityName) return;
      try {
        setLoading(true);
        setError(null);

        const runs = await getAuditRuns();
        if (!runs || runs.length < 2) {
          if (isMounted) {
            setHistory([]);
            setLoading(false);
          }
          return;
        }

        // Sort runs chronologically (oldest to newest)
        const chronologicalRuns = [...runs].sort((a, b) => a.id - b.id);

        // Fetch detail for each run to inspect results_snapshot
        const runDetails = await Promise.all(
          chronologicalRuns.map((r) =>
            getAuditRunDetail(r.id).catch(() => null)
          )
        );

        const entityPoints = [];
        const normTarget = entityName.trim().toLowerCase();

        runDetails.forEach((detail) => {
          if (!detail || !detail.results_snapshot) return;

          const snapshot = detail.results_snapshot.find(
            (s) => (s.entity_name || "").trim().toLowerCase() === normTarget
          );

          if (snapshot) {
            const dateObj = detail.timestamp ? new Date(detail.timestamp) : null;
            const formattedDate = dateObj
              ? dateObj.toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : `Run #${detail.id}`;

            entityPoints.push({
              runId: detail.id,
              rawTimestamp: detail.timestamp,
              label: `Run #${detail.id}`,
              date: formattedDate,
              risk_score: Number(snapshot.risk_score || 0),
              risk_band: (snapshot.risk_band || "LOW").toUpperCase(),
              execution_gap:
                snapshot.execution_gap_component_score !== null &&
                snapshot.execution_gap_component_score !== undefined
                  ? Number((snapshot.execution_gap_component_score * 100).toFixed(1))
                  : null,
              negative_space:
                snapshot.negative_space_component_score !== null &&
                snapshot.negative_space_component_score !== undefined
                  ? Number((snapshot.negative_space_component_score * 100).toFixed(1))
                  : null,
              anomaly:
                snapshot.anomaly_component_score !== null &&
                snapshot.anomaly_component_score !== undefined
                  ? Number((snapshot.anomaly_component_score * 100).toFixed(1))
                  : null,
            });
          }
        });

        if (isMounted) {
          setHistory(entityPoints);
        }
      } catch (err) {
        console.error("TrendPanel fetch error:", err);
        if (isMounted) {
          setError("Failed to load historical assessment runs.");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchEntityHistory();

    return () => {
      isMounted = false;
    };
  }, [entityName]);

  // Derive trend direction strictly when at least 2 data points exist
  let trajectory = null;
  if (history.length >= 2) {
    const latest = history[history.length - 1];
    const previous = history[history.length - 2];
    const delta = Number((latest.risk_score - previous.risk_score).toFixed(1));

    if (delta <= -1.0) {
      trajectory = {
        direction: "Improving",
        delta,
        description: `Risk score reduced by ${Math.abs(delta)} pts since prior run.`,
        color: "var(--green)",
        bg: "rgba(87, 213, 140, 0.12)",
        borderColor: "rgba(87, 213, 140, 0.3)",
        icon: TrendingDown,
      };
    } else if (delta >= 1.0) {
      trajectory = {
        direction: "Deteriorating",
        delta,
        description: `Risk score increased by ${delta} pts since prior run.`,
        color: "var(--red)",
        bg: "rgba(239, 107, 114, 0.12)",
        borderColor: "rgba(239, 107, 114, 0.3)",
        icon: TrendingUp,
      };
    } else {
      trajectory = {
        direction: "Stable",
        delta,
        description: `Risk score remained stable (Δ ${delta >= 0 ? `+${delta}` : delta} pts).`,
        color: "var(--accent)",
        bg: "rgba(86, 199, 255, 0.12)",
        borderColor: "rgba(86, 199, 255, 0.3)",
        icon: Minus,
      };
    }
  }

  return (
    <section className="ranking-panel" style={{ marginTop: "30px" }}>
      <div className="panel-header">
        <div>
          <div className="panel-label">TEMPORAL ANALYSIS</div>
          <h2>Temporal / Trend Analysis</h2>
          <p style={{ margin: "4px 0 0", fontSize: "12px", color: "var(--muted)", maxWidth: "600px" }}>
            Traces this entity&apos;s risk trajectory across persistent assessment runs. Requires at least two runs to determine directional progress.
          </p>
        </div>

        {trajectory && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 14px",
              borderRadius: "2px",
              backgroundColor: trajectory.bg,
              border: `1px solid ${trajectory.borderColor}`,
              color: trajectory.color,
            }}
          >
            <trajectory.icon size={15} />
            <span style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.08em" }}>
              {trajectory.direction.toUpperCase()}
            </span>
            <span style={{ fontSize: "10px", color: "var(--muted)" }}>
              ({trajectory.delta > 0 ? `+${trajectory.delta}` : trajectory.delta})
            </span>
          </div>
        )}
      </div>

      {loading && (
        <div style={{ padding: "40px 20px" }}>
          <div className="skeleton skeleton-card" style={{ height: "220px" }} />
        </div>
      )}

      {!loading && error && (
        <div className="error-state" style={{ minHeight: "160px", padding: "30px 20px" }}>
          <AlertCircle size={24} color="var(--amber)" />
          <h3 style={{ marginTop: "8px" }}>Historical Data Error</h3>
          <p style={{ fontSize: "12px" }}>{error}</p>
        </div>
      )}

      {!loading && !error && history.length < 2 && (
        <div className="empty-state" style={{ minHeight: "180px", padding: "40px 20px" }}>
          <Clock size={28} color="var(--muted)" />
          <h3 style={{ marginTop: "12px", color: "var(--text)" }}>
            Historical trend data is not available for this entity.
          </h3>
          <p style={{ maxWidth: "480px", color: "var(--muted)", fontSize: "12px", lineHeight: 1.6 }}>
            At least two assessment runs are required to compute a temporal trajectory. Currently, only {history.length} assessment snapshot is available for {entityName}. Future uploads will automatically build this entity&apos;s chronological trend.
          </p>
        </div>
      )}

      {!loading && !error && history.length >= 2 && (
        <div style={{ padding: "20px" }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "16px",
              flexWrap: "wrap",
              gap: "10px",
            }}
          >
            <div style={{ fontSize: "12px", color: "var(--muted)" }}>
              Tracking across <strong>{history.length}</strong> assessment runs ·{" "}
              {trajectory?.description}
            </div>

            <button
              onClick={() => setShowComponents(!showComponents)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                background: showComponents ? "rgba(86, 199, 255, 0.15)" : "rgba(255, 255, 255, 0.04)",
                border: `1px solid ${showComponents ? "var(--accent)" : "var(--line)"}`,
                color: showComponents ? "var(--accent)" : "var(--muted)",
                padding: "4px 10px",
                borderRadius: "2px",
                fontSize: "10px",
                fontWeight: 700,
                cursor: "pointer",
                letterSpacing: "0.06em",
              }}
            >
              <Layers size={12} />
              <span>{showComponents ? "HIDE COMPONENT LINES" : "SHOW COMPONENT BREAKDOWN"}</span>
            </button>
          </div>

          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={history}
                margin={{ top: 10, right: 20, left: -10, bottom: 5 }}
              >
                <CartesianGrid stroke="rgba(255,255,255,0.06)" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fill: "#8e96a0", fontSize: 10 }}
                  axisLine={{ stroke: "var(--line)" }}
                  tickLine={false}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: "#8e96a0", fontSize: 10 }}
                  axisLine={{ stroke: "var(--line)" }}
                  tickLine={false}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload || !payload.length) return null;
                    const item = payload[0].payload;
                    return (
                      <div
                        style={{
                          background: "var(--surface)",
                          border: "1px solid var(--line)",
                          padding: "10px 14px",
                          borderRadius: "2px",
                          fontSize: "11px",
                          boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
                        }}
                      >
                        <div style={{ fontWeight: 700, color: "var(--text)", marginBottom: "4px" }}>
                          {item.label} · {item.date}
                        </div>
                        <div style={{ color: "var(--accent)", marginBottom: "4px" }}>
                          Risk Score: <strong>{item.risk_score}</strong> ({item.risk_band})
                        </div>
                        {showComponents && (
                          <div
                            style={{
                              borderTop: "1px solid rgba(255,255,255,0.08)",
                              paddingTop: "6px",
                              display: "flex",
                              flexDirection: "column",
                              gap: "2px",
                              color: "var(--muted)",
                              fontSize: "10px",
                            }}
                          >
                            <span>Execution Gap: {item.execution_gap ?? "—"}</span>
                            <span>Negative Space: {item.negative_space ?? "—"}</span>
                            <span>Anomaly: {item.anomaly ?? "—"}</span>
                          </div>
                        )}
                      </div>
                    );
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="risk_score"
                  name="Risk Score"
                  stroke="#ef6b72"
                  strokeWidth={2.5}
                  dot={{ fill: "#ef6b72", r: 4 }}
                  activeDot={{ r: 6 }}
                />
                {showComponents && (
                  <>
                    <Line
                      type="monotone"
                      dataKey="execution_gap"
                      name="Execution Gap"
                      stroke="#e5ad5a"
                      strokeWidth={1.5}
                      strokeDasharray="4 4"
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="negative_space"
                      name="Negative Space"
                      stroke="#56c7ff"
                      strokeWidth={1.5}
                      strokeDasharray="4 4"
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="anomaly"
                      name="Anomaly"
                      stroke="#a78bfa"
                      strokeWidth={1.5}
                      strokeDasharray="4 4"
                      dot={false}
                    />
                  </>
                )}
                {showComponents && <Legend wrapperStyle={{ fontSize: "10px", paddingTop: "10px" }} />}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </section>
  );
}
