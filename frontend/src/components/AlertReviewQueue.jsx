import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, AlertTriangle, RefreshCw, ListOrdered, ShieldAlert } from "lucide-react";
import { getPrioritySamples } from "../lib/api";

function formatRuleName(rule) {
  if (!rule) return "";
  return rule.replace(/_/g, " ");
}

export default function AlertReviewQueue() {
  const [samples, setSamples] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchSamples = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getPrioritySamples();
      setSamples(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to load priority samples:", err);
      let safeError = "Failed to load prioritized alert queue. Please verify backend service availability.";
      if (err.response?.data?.detail && typeof err.response.data.detail === "string") {
        safeError = err.response.data.detail;
      }
      setError(safeError);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let ignore = false;
    const loadInitial = async () => {
      try {
        const data = await getPrioritySamples();
        if (!ignore) {
          setSamples(Array.isArray(data) ? data : []);
        }
      } catch (err) {
        if (!ignore) {
          console.error("Failed to load priority samples:", err);
          let safeError = "Failed to load prioritized alert queue. Please verify backend service availability.";
          if (err.response?.data?.detail && typeof err.response.data.detail === "string") {
            safeError = err.response.data.detail;
          }
          setError(safeError);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    };
    loadInitial();
    return () => {
      ignore = true;
    };
  }, []);

  return (
    <section className="ranking-panel alert-review-queue-panel" style={{ marginTop: "30px" }}>
      <div className="panel-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <div className="panel-label">SUPERVISORY ALERT REVIEW PRIORITIZATION</div>
          <h2 style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <ListOrdered size={22} color="var(--accent)" />
            Alert Review Queue
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: "14px", color: "var(--muted)", maxWidth: "680px" }}>
            Cross-entity prioritized alert samples nominated by automated detectors. Directs supervisor attention to specific alerts requiring immediate manual inspection.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span className="panel-meta">
            {samples.length > 0 ? `${samples.length} ALERTS RANKED` : "ALERT QUEUE"}
          </span>
          <button
            onClick={fetchSamples}
            disabled={loading}
            title="Refresh priority samples"
            style={{
              background: "rgba(255, 255, 255, 0.04)",
              border: "1px solid var(--line)",
              color: "var(--muted)",
              padding: "6px 10px",
              borderRadius: "4px",
              cursor: loading ? "not-allowed" : "pointer",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "12px",
              transition: "all 0.2s ease",
            }}
          >
            <RefreshCw size={13} className={loading ? "spin" : ""} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {loading && (
        <div style={{ padding: "24px 20px" }}>
          <div className="skeleton skeleton-card" style={{ height: "45px", marginBottom: "10px" }} />
          <div className="skeleton skeleton-card" style={{ height: "45px", marginBottom: "10px" }} />
          <div className="skeleton skeleton-card" style={{ height: "45px", marginBottom: "10px" }} />
          <div className="skeleton skeleton-card" style={{ height: "45px" }} />
        </div>
      )}

      {error && !loading && (
        <div className="error-state" style={{ margin: "20px", padding: "24px" }}>
          <AlertTriangle size={24} color="var(--amber)" />
          <h3 style={{ fontSize: "15px", margin: "10px 0 6px" }}>Priority Queue Unavailable</h3>
          <p style={{ fontSize: "13px", color: "var(--muted)", maxWidth: "500px", margin: "0 auto 16px" }}>
            {error}
          </p>
          <button
            onClick={fetchSamples}
            style={{
              padding: "6px 14px",
              fontSize: "12px",
              background: "var(--surface-2)",
              border: "1px solid var(--line)",
              color: "var(--text)",
              borderRadius: "4px",
              cursor: "pointer",
            }}
          >
            Retry Connection
          </button>
        </div>
      )}

      {!loading && !error && samples.length === 0 && (
        <div className="empty-state" style={{ minHeight: "180px", padding: "40px 20px" }}>
          <ShieldAlert size={28} color="var(--muted)" />
          <h3 style={{ marginTop: "12px", color: "var(--text)" }}>No prioritized alert samples available.</h3>
          <p style={{ maxWidth: "480px", color: "var(--muted)", fontSize: "13px" }}>
            No individual alerts currently meet the criteria for manual review prioritization. Ensure operational SOC records have been ingested.
          </p>
        </div>
      )}

      {!loading && !error && samples.length > 0 && (
        <div style={{ overflowX: "auto", width: "100%", WebkitOverflowScrolling: "touch" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "13px",
              textAlign: "left",
              minWidth: "860px",
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
                <th style={{ padding: "14px 16px", width: "55px" }}>Rank</th>
                <th style={{ padding: "14px 16px", width: "110px" }}>Alert ID</th>
                <th style={{ padding: "14px 16px", width: "190px" }}>Entity</th>
                <th style={{ padding: "14px 16px", width: "120px" }}>Priority Score</th>
                <th style={{ padding: "14px 16px", width: "100px" }}>Severity</th>
                <th style={{ padding: "14px 16px", width: "180px" }}>Triggered Rules</th>
                <th style={{ padding: "14px 16px" }}>Reason</th>
                <th style={{ padding: "14px 16px", width: "40px", textAlign: "right" }}></th>
              </tr>
            </thead>
            <tbody>
              {samples.map((sample, idx) => {
                const rank = (idx + 1).toString().padStart(2, "0");
                const sevLower = (sample.severity || "low").toLowerCase();
                const sevUpper = (sample.severity || "LOW").toUpperCase();
                const isTopPriority = idx === 0 || sample.priority_score >= 70;

                const rowBg = idx % 2 === 1
                  ? "rgba(255, 255, 255, 0.01)"
                  : "transparent";

                return (
                  <tr
                    key={`${sample.entity_name}-${sample.alert_id}-${idx}`}
                    style={{
                      borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      backgroundColor: rowBg,
                      transition: "background 0.2s ease",
                    }}
                    className="priority-table-row"
                  >
                    {/* 1. RANK */}
                    <td style={{ padding: "14px 16px", color: "var(--muted)", fontFamily: "monospace", fontWeight: 700 }}>
                      {rank}
                    </td>

                    {/* 2. ALERT ID */}
                    <td style={{ padding: "14px 16px", fontFamily: "monospace", fontWeight: 600, color: "var(--text)" }}>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "2px 6px",
                          borderRadius: "3px",
                          background: "rgba(86, 199, 255, 0.08)",
                          border: "1px solid rgba(86, 199, 255, 0.2)",
                          color: "var(--accent)",
                          fontSize: "12px",
                        }}
                      >
                        {sample.alert_id}
                      </span>
                    </td>

                    {/* 3. ENTITY */}
                    <td style={{ padding: "14px 16px" }}>
                      <Link
                        to={`/entities/${encodeURIComponent(sample.entity_name)}`}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          color: "var(--text)",
                          fontWeight: 600,
                          textDecoration: "none",
                        }}
                        title={`Inspect ${sample.entity_name} dossier`}
                      >
                        <span>{sample.entity_name}</span>
                        <ArrowUpRight size={12} color="var(--muted)" />
                      </Link>
                    </td>

                    {/* 4. PRIORITY SCORE */}
                    <td style={{ padding: "14px 16px" }}>
                      <span
                        style={{
                          fontSize: "14px",
                          fontWeight: 700,
                          color: isTopPriority ? "var(--red)" : "var(--amber)",
                        }}
                      >
                        {Number(sample.priority_score || 0).toFixed(1)}
                      </span>
                      <span style={{ color: "var(--muted)", fontSize: "11px", marginLeft: "4px" }}>/ 100</span>
                    </td>

                    {/* 5. SEVERITY */}
                    <td style={{ padding: "14px 16px" }}>
                      <span
                        style={{
                          display: "inline-block",
                          padding: "3px 8px",
                          borderRadius: "2px",
                          fontSize: "10px",
                          fontWeight: 700,
                          letterSpacing: "0.08em",
                          textTransform: "uppercase",
                          backgroundColor:
                            sevLower === "critical"
                              ? "rgba(239, 107, 114, 0.15)"
                              : sevLower === "high"
                              ? "rgba(229, 173, 90, 0.15)"
                              : sevLower === "medium"
                              ? "rgba(86, 199, 255, 0.12)"
                              : "rgba(87, 213, 140, 0.12)",
                          color:
                            sevLower === "critical"
                              ? "var(--red)"
                              : sevLower === "high"
                              ? "var(--amber)"
                              : sevLower === "medium"
                              ? "var(--accent)"
                              : "var(--green)",
                          border: `1px solid ${
                            sevLower === "critical"
                              ? "rgba(239, 107, 114, 0.3)"
                              : sevLower === "high"
                              ? "rgba(229, 173, 90, 0.3)"
                              : sevLower === "medium"
                              ? "rgba(86, 199, 255, 0.3)"
                              : "rgba(87, 213, 140, 0.3)"
                          }`,
                        }}
                      >
                        {sevUpper}
                      </span>
                    </td>

                    {/* 6. TRIGGERED RULES */}
                    <td style={{ padding: "14px 16px" }}>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                        {Array.isArray(sample.triggered_rules) && sample.triggered_rules.length > 0 ? (
                          sample.triggered_rules.map((rule) => (
                            <span
                              key={rule}
                              style={{
                                display: "inline-block",
                                padding: "2px 6px",
                                borderRadius: "2px",
                                fontSize: "10px",
                                fontWeight: 600,
                                background: "rgba(255, 255, 255, 0.05)",
                                border: "1px solid var(--line)",
                                color: "var(--text)",
                                letterSpacing: "0.04em",
                              }}
                            >
                              {formatRuleName(rule)}
                            </span>
                          ))
                        ) : (
                          <span style={{ color: "var(--muted)", fontSize: "12px" }}>None</span>
                        )}
                      </div>
                    </td>

                    {/* 7. REASON */}
                    <td style={{ padding: "14px 16px", color: "var(--muted)", fontSize: "12px", lineHeight: "1.4" }}>
                      {sample.reason || "—"}
                    </td>

                    {/* INSPECT ACTION */}
                    <td style={{ padding: "14px 16px", textAlign: "right" }}>
                      <Link
                        to={`/entities/${encodeURIComponent(sample.entity_name)}`}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          width: "28px",
                          height: "28px",
                          borderRadius: "2px",
                          border: "1px solid var(--line)",
                          color: "var(--muted)",
                          textDecoration: "none",
                        }}
                        title={`Inspect ${sample.entity_name}`}
                        aria-label={`Inspect ${sample.entity_name}`}
                      >
                        <ArrowUpRight size={13} />
                      </Link>
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
