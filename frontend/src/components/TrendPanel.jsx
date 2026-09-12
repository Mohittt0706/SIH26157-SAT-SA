import { useState, useEffect } from "react";
import {
  TrendingDown,
  TrendingUp,
  Minus,
  Activity,
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
import { getEntityTrend } from "../lib/api";

const TRAJECTORY_BY_DIRECTION = {
  improving: {
    label: "Improving",
    color: "var(--green)",
    bg: "rgba(87, 213, 140, 0.12)",
    borderColor: "rgba(87, 213, 140, 0.3)",
    icon: TrendingDown,
  },
  deteriorating: {
    label: "Deteriorating",
    color: "var(--red)",
    bg: "rgba(239, 107, 114, 0.12)",
    borderColor: "rgba(239, 107, 114, 0.3)",
    icon: TrendingUp,
  },
  stable: {
    label: "Stable",
    color: "var(--accent)",
    bg: "rgba(86, 199, 255, 0.12)",
    borderColor: "rgba(86, 199, 255, 0.3)",
    icon: Minus,
  },
  volatile: {
    label: "Volatile",
    color: "var(--amber)",
    bg: "rgba(229, 173, 90, 0.12)",
    borderColor: "rgba(229, 173, 90, 0.3)",
    icon: Activity,
  },
};

/**
 * Builds the "since the first tracked run" description. `direction` now
 * comes from a least-squares slope over every run (see _compute_entity_trend
 * in app/routers/analytics.py), not from `change` — an entity can have a
 * near-zero first-to-last `change` while still reading "volatile" because it
 * swung widely in between (e.g. 85 -> 30.9 -> ... -> 85), which is exactly
 * what `volatility` (the series' own standard deviation) is for.
 */
function describeChange(direction, change, volatility) {
  if (direction === "volatile") {
    return `Risk score has swung by roughly ±${volatility} pts (σ) across tracked runs, with no clear net direction — net change since the first run is ${change >= 0 ? `+${change}` : change} pts.`;
  }
  if (change === null || change === undefined) return null;
  if (direction === "improving") {
    return `Risk score reduced by ${Math.abs(change)} pts since the first tracked run.`;
  }
  if (direction === "deteriorating") {
    return `Risk score increased by ${change} pts since the first tracked run.`;
  }
  return `Risk score remained stable (Δ ${change >= 0 ? `+${change}` : change} pts since the first tracked run).`;
}

export default function TrendPanel({ entityName }) {
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showComponents, setShowComponents] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function fetchEntityTrend() {
      if (!entityName) return;
      try {
        setLoading(true);
        setError(null);

        const detail = await getEntityTrend(entityName);
        if (isMounted) {
          setTrend(detail);
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

    fetchEntityTrend();

    return () => {
      isMounted = false;
    };
  }, [entityName]);

  const points = trend?.points || [];
  const history = points.map((p) => ({
    runId: p.run_id,
    rawTimestamp: p.timestamp,
    label: `Run #${p.run_id}`,
    date: p.timestamp
      ? new Date(p.timestamp).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : `Run #${p.run_id}`,
    risk_score: Number(p.risk_score || 0),
    risk_band: (p.risk_band || "LOW").toUpperCase(),
    // Raw 0.0-1.0 detector scores, exactly as the endpoint returns them —
    // not rescaled to the 0-100 risk_score axis.
    execution_gap: p.execution_gap ?? null,
    negative_space: p.negative_space ?? null,
    anomaly: p.anomaly ?? null,
  }));

  const direction = trend?.direction;
  const trajectory = direction ? TRAJECTORY_BY_DIRECTION[direction] : null;
  const changeDescription = trajectory ? describeChange(direction, trend.change, trend.volatility) : null;

  const hasEnoughHistory = direction && direction !== "insufficient_data" && history.length >= 2;

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
              {trajectory.label.toUpperCase()}
            </span>
            {direction === "volatile" && trend.volatility !== null && trend.volatility !== undefined && (
              <span style={{ fontSize: "10px", color: "var(--muted)" }}>
                (σ {trend.volatility})
              </span>
            )}
            {direction !== "volatile" && trend.change !== null && trend.change !== undefined && (
              <span style={{ fontSize: "10px", color: "var(--muted)" }}>
                ({trend.change > 0 ? `+${trend.change}` : trend.change})
              </span>
            )}
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

      {!loading && !error && !hasEnoughHistory && (
        <div className="empty-state" style={{ minHeight: "180px", padding: "40px 20px" }}>
          <Clock size={28} color="var(--muted)" />
          <h3 style={{ marginTop: "12px", color: "var(--text)" }}>
            Historical trend data is not available for this entity.
          </h3>
          <p style={{ maxWidth: "480px", color: "var(--muted)", fontSize: "12px", lineHeight: 1.6 }}>
            At least two assessment runs are required to compute a temporal trajectory for {entityName}. Future uploads will automatically build this entity&apos;s chronological trend.
          </p>
        </div>
      )}

      {!loading && !error && hasEnoughHistory && (
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
              {changeDescription}
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
                            <span>Execution Gap: {item.execution_gap?.toFixed(2) ?? "—"}</span>
                            <span>Negative Space: {item.negative_space?.toFixed(2) ?? "—"}</span>
                            <span>Anomaly: {item.anomaly?.toFixed(2) ?? "—"}</span>
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
