import { Link } from "react-router-dom";
import { ArrowUpRight, ShieldAlert, AlertCircle, Clock, ShieldCheck, CheckCircle2 } from "lucide-react";

/**
 * Maps the risk band to a supervisory review priority recommendation.
 * Grounded strictly in the existing risk_band field from the backend.
 */
function getReviewPriority(riskBand, riskScore) {
  const band = (riskBand || "").toLowerCase();
  if (band === "critical" || riskScore >= 70) {
    return {
      label: "Immediate Review",
      level: "critical",
      badgeClass: "badge-critical",
      icon: ShieldAlert,
    };
  }
  if (band === "high" || riskScore >= 45) {
    return {
      label: "High Priority",
      level: "high",
      badgeClass: "badge-high",
      icon: AlertCircle,
    };
  }
  if (band === "medium" || riskScore >= 20) {
    return {
      label: "Review",
      level: "medium",
      badgeClass: "badge-medium",
      icon: Clock,
    };
  }
  return {
    label: "Monitor",
    level: "low",
    badgeClass: "badge-low",
    icon: ShieldCheck,
  };
}

function formatPrimaryDriver(driver) {
  if (!driver || driver === "Normal" || driver === "None") {
    return "Baseline Alignment";
  }
  return driver.replace(/_/g, " ");
}

export default function SupervisoryReviewPriority({ entities = [] }) {
  if (!entities || entities.length === 0) {
    return (
      <section className="ranking-panel" style={{ marginTop: "30px" }}>
        <div className="panel-header">
          <div>
            <div className="panel-label">SUPERVISORY REVIEW PRIORITIZATION</div>
            <h2>Supervisory Review Priority</h2>
          </div>
          <span className="panel-meta">QUEUE / 0 ENTITIES</span>
        </div>
        <div className="empty-state" style={{ minHeight: "180px", padding: "40px 20px" }}>
          <CheckCircle2 size={28} color="var(--green)" />
          <h3 style={{ marginTop: "12px", color: "var(--text)" }}>No Review Items Pending</h3>
          <p style={{ maxWidth: "480px", color: "var(--muted)", fontSize: "14px" }}>
            No entities are currently prioritized for supervisory review. Upload a SOC alert dataset from the Analyze page to populate the priority queue.
          </p>
        </div>
      </section>
    );
  }

  const sorted = [...entities].sort(
    (a, b) => (b.risk_score || 0) - (a.risk_score || 0) || (a.entity_name || "").localeCompare(b.entity_name || "")
  );

  return (
    <section className="ranking-panel" style={{ marginTop: "30px" }}>
      <div className="panel-header">
        <div>
          <div className="panel-label">SUPERVISORY REVIEW PRIORITIZATION</div>
          <h2>Supervisory Review Priority</h2>
          <p style={{ margin: "4px 0 0", fontSize: "14px", color: "var(--muted)", maxWidth: "600px" }}>
            Prioritized order for supervisory assessment based on composite risk signals and peer deviations. Final determinations remain with the human supervisor.
          </p>
        </div>
        <span className="panel-meta">RANKED BY RISK SCORE</span>
      </div>

      <div style={{ overflowX: "auto", width: "100%" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: "13px",
            textAlign: "left",
            minWidth: "720px",
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
              <th style={{ padding: "14px 16px", width: "60px" }}>Rank</th>
              <th style={{ padding: "14px 16px" }}>Entity</th>
              <th style={{ padding: "14px 16px", width: "120px" }}>Risk Score</th>
              <th style={{ padding: "14px 16px", width: "110px" }}>Risk Band</th>
              <th style={{ padding: "14px 16px" }}>Primary Driver / Reason</th>
              <th style={{ padding: "14px 16px", width: "160px" }}>Review Priority</th>
              <th style={{ padding: "14px 16px", width: "50px", textAlign: "right" }}></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((entity, idx) => {
              const rank = (idx + 1).toString().padStart(2, "0");
              const priority = getReviewPriority(entity.risk_band, entity.risk_score);
              const PriorityIcon = priority.icon;
              const bandUpper = (entity.risk_band || "LOW").toUpperCase();
              const scoreClass = `score-${(entity.risk_band || "low").toLowerCase()}`;

              // Background tint for top priority items
              const rowBg = idx === 0 && priority.level === "critical"
                ? "rgba(239, 107, 114, 0.04)"
                : idx % 2 === 1
                ? "rgba(255, 255, 255, 0.01)"
                : "transparent";

              return (
                <tr
                  key={entity.entity_name}
                  style={{
                    borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                    backgroundColor: rowBg,
                    transition: "background 0.2s ease",
                  }}
                  className="priority-table-row"
                >
                  <td style={{ padding: "14px 16px", color: "var(--muted)", fontFamily: "monospace", fontWeight: 700 }}>
                    {rank}
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    <Link
                      to={`/entities/${encodeURIComponent(entity.entity_name)}`}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "8px",
                        color: "var(--text)",
                        fontWeight: 600,
                        textDecoration: "none",
                      }}
                    >
                      <span>{entity.entity_name}</span>
                      <small style={{ color: "var(--muted)", fontWeight: 400 }}>
                        ({entity.alert_count ?? 0} alerts)
                      </small>
                    </Link>
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    <span className={`entity-score ${scoreClass}`} style={{ fontSize: "14px", fontWeight: 700 }}>
                      {Number(entity.risk_score || 0).toFixed(1)}
                    </span>
                    <span style={{ color: "var(--muted)", fontSize: "11px", marginLeft: "4px" }}>/ 100</span>
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "3px 8px",
                        borderRadius: "2px",
                        fontSize: "11px",
                        fontWeight: 700,
                        letterSpacing: "0.08em",
                        textTransform: "uppercase",
                        backgroundColor:
                          bandUpper === "CRITICAL"
                            ? "rgba(239, 107, 114, 0.15)"
                            : bandUpper === "HIGH"
                            ? "rgba(229, 173, 90, 0.15)"
                            : bandUpper === "MEDIUM"
                            ? "rgba(86, 199, 255, 0.12)"
                            : "rgba(87, 213, 140, 0.12)",
                        color:
                          bandUpper === "CRITICAL"
                            ? "var(--red)"
                            : bandUpper === "HIGH"
                            ? "var(--amber)"
                            : bandUpper === "MEDIUM"
                            ? "var(--accent)"
                            : "var(--green)",
                        border: `1px solid ${
                          bandUpper === "CRITICAL"
                            ? "rgba(239, 107, 114, 0.3)"
                            : bandUpper === "HIGH"
                            ? "rgba(229, 173, 90, 0.3)"
                            : bandUpper === "MEDIUM"
                            ? "rgba(86, 199, 255, 0.3)"
                            : "rgba(87, 213, 140, 0.3)"
                        }`,
                      }}
                    >
                      {bandUpper}
                    </span>
                  </td>
                  <td style={{ padding: "14px 16px", color: "var(--muted)" }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                      <span style={{ color: "var(--text)", fontWeight: 500 }}>
                        {formatPrimaryDriver(entity.primary_driver)}
                      </span>
                      {entity.findings_summary && entity.findings_summary.length > 0 && (
                        <small style={{ color: "var(--muted)", fontSize: "11px" }}>
                          {entity.findings_summary.join(" · ")}
                        </small>
                      )}
                    </div>
                  </td>
                  <td style={{ padding: "14px 16px" }}>
                    <div
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "6px",
                        padding: "4px 10px",
                        borderRadius: "2px",
                        fontSize: "11px",
                        fontWeight: 700,
                        letterSpacing: "0.06em",
                        backgroundColor:
                          priority.level === "critical"
                            ? "rgba(239, 107, 114, 0.18)"
                            : priority.level === "high"
                            ? "rgba(229, 173, 90, 0.18)"
                            : priority.level === "medium"
                            ? "rgba(86, 199, 255, 0.12)"
                            : "rgba(87, 213, 140, 0.12)",
                        color:
                          priority.level === "critical"
                            ? "var(--red)"
                            : priority.level === "high"
                            ? "var(--amber)"
                            : priority.level === "medium"
                            ? "var(--accent)"
                            : "var(--green)",
                      }}
                    >
                      <PriorityIcon size={12} />
                      <span>{priority.label}</span>
                    </div>
                  </td>
                  <td style={{ padding: "14px 16px", textAlign: "right" }}>
                    <Link
                      to={`/entities/${encodeURIComponent(entity.entity_name)}`}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: "28px",
                        height: "28px",
                        borderRadius: "2px",
                        border: "1px solid var(--line)",
                        color: "var(--muted)",
                      }}
                      title={`Inspect ${entity.entity_name} dossier`}
                      aria-label={`Inspect ${entity.entity_name} dossier`}
                    >
                      <ArrowUpRight size={14} />
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
