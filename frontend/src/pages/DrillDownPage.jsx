import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, AlertTriangle, FileText, CheckCircle2 } from "lucide-react";
import usePageMetadata from "../hooks/usePageMetadata";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { getEntityDetails } from "../lib/api";

export default function DrillDownPage() {
  const { entityName: paramEntityName } = useParams();
  const entityName = decodeURIComponent(paramEntityName || "");

  usePageMetadata({
    title: `${entityName} | VEIL Supervisory Assessment`,
    description: `Supervisory assessment and evidence documentation for ${entityName}.`,
    path: `/entities/${paramEntityName}`,
  });

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDetails = async () => {
      if (!entityName) return;
      try {
        setLoading(true);
        setError(null);
        const details = await getEntityDetails(entityName);
        if (!details) {
          setError("Entity not found.");
        } else {
          setData(details);
        }
      } catch (err) {
        console.error(err);
        if (err.response?.status === 404) {
          setError(`Entity '${entityName}' not found in active dataset.`);
        } else {
          setError(
            err.response?.data?.detail || "Failed to load entity details."
          );
        }
      } finally {
        setLoading(false);
      }
    };
    fetchDetails();
  }, [entityName]);

  if (loading) {
    return (
      <main className="drilldown-shell">
        <nav className="dashboard-nav">
          <Link to="/" className="dashboard-brand" aria-label="VEIL Home">
            <div className="dashboard-brand-mark">V</div>
            <div>
              <div className="dashboard-brand-name">VEIL</div>
              <div className="dashboard-brand-subtitle">
                Supervisory Intelligence for SOC Assessment
              </div>
            </div>
          </Link>
          <div className="dashboard-nav-links">
            <Link to="/upload">ANALYZE</Link>
            <Link to="/dashboard">OVERVIEW</Link>
            <span className="active">DRILLDOWN</span>
          </div>
          <div className="dashboard-status">
            <span />
            OFFLINE MODE
          </div>
        </nav>
        <section className="drilldown-page" style={{ paddingTop: "20px" }}>
          <div className="drilldown-header-container" style={{ marginBottom: "20px" }}>
            <div className="drilldown-title">
               <div className="skeleton skeleton-text" style={{ width: "120px" }} />
               <div className="skeleton skeleton-title" style={{ width: "300px", height: "40px", marginTop: "10px" }} />
               <div className="skeleton skeleton-text" style={{ width: "350px", marginTop: "10px" }} />
            </div>
            <div className="drilldown-scores-container" style={{ display: "flex", gap: "20px" }}>
               <div className="skeleton skeleton-card" style={{ width: "180px", height: "90px" }} />
               <div className="skeleton skeleton-card" style={{ width: "250px", height: "90px" }} />
            </div>
          </div>
          
          <div className="skeleton skeleton-card" style={{ height: "70px", marginBottom: "30px" }} />

          <div className="drilldown-main-grid">
            <div className="skeleton skeleton-card" style={{ height: "400px" }} />
            <div className="skeleton skeleton-card" style={{ height: "400px" }} />
          </div>
        </section>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="drilldown-shell">
        <nav className="dashboard-nav">
          <Link to="/" className="dashboard-brand" aria-label="VEIL Home">
            <div className="dashboard-brand-mark">V</div>
            <div>
              <div className="dashboard-brand-name">VEIL</div>
              <div className="dashboard-brand-subtitle">
                Supervisory Intelligence for SOC Assessment
              </div>
            </div>
          </Link>
          <div className="dashboard-nav-links">
            <Link to="/upload">ANALYZE</Link>
            <Link to="/dashboard">OVERVIEW</Link>
            <span className="active">DRILLDOWN</span>
          </div>
        </nav>
        <div className="error-state">
          <AlertTriangle size={32} />
          <h3>Entity Unavailable</h3>
          <p>{error || "Entity not found."}</p>
          <Link
            to="/dashboard"
            style={{
              marginTop: "20px",
              color: "var(--accent)",
              textDecoration: "underline",
            }}
          >
            Return to Dashboard
          </Link>
        </div>
      </main>
    );
  }

  const bandLower = (data.risk_band || "low").toLowerCase();
  const isHighRisk = bandLower === "critical" || bandLower === "high";
  const scoreClassStr = `score-${bandLower}`;

  // Prepare benchmark data array using exact backend peer_metrics field names
  const benchmarkArray = [];
  if (data.peer_metrics) {
    if (data.peer_metrics.avg_closure_seconds) {
      benchmarkArray.push({
        metric: "Closure (m)",
        fieldName: "avg_closure_seconds",
        entity: Math.round(data.peer_metrics.avg_closure_seconds.entity / 60),
        peer: Math.round(
          data.peer_metrics.avg_closure_seconds.peer_median / 60
        ),
      });
    }
    if (data.peer_metrics.escalation_rate) {
      benchmarkArray.push({
        metric: "Escalation %",
        fieldName: "escalation_rate",
        entity: Math.round(data.peer_metrics.escalation_rate.entity * 100),
        peer: Math.round(data.peer_metrics.escalation_rate.peer_median * 100),
      });
    }
    if (data.peer_metrics.avg_note_length) {
      benchmarkArray.push({
        metric: "Note Len",
        fieldName: "avg_note_length",
        entity: Math.round(data.peer_metrics.avg_note_length.entity),
        peer: Math.round(data.peer_metrics.avg_note_length.peer_median),
      });
    }
    if (data.peer_metrics.alert_count) {
      benchmarkArray.push({
        metric: "Alerts",
        fieldName: "alert_count",
        entity: data.peer_metrics.alert_count.entity,
        peer: Math.round(data.peer_metrics.alert_count.peer_median),
      });
    }
  }

  const primaryDriverText =
    data.primary_driver ||
    (data.findings && data.findings.length > 0
      ? data.findings[0].detector.replace("_", " ")
      : "operational patterns");

  return (
    <main className="drilldown-shell">
      {/* NAVBAR */}
      <nav className="dashboard-nav">
        <Link to="/" className="dashboard-brand" aria-label="VEIL Home">
          <div className="dashboard-brand-mark">V</div>
          <div>
            <div className="dashboard-brand-name">VEIL</div>
            <div className="dashboard-brand-subtitle">
              Supervisory Intelligence for SOC Assessment
            </div>
          </div>
        </Link>
        <div className="dashboard-nav-links">
          <Link to="/upload">ANALYZE</Link>
          <Link to="/dashboard">OVERVIEW</Link>
          <span className="active">DRILLDOWN</span>
        </div>
        <div className="dashboard-status">
          <span />
          OFFLINE MODE
        </div>
      </nav>

      <section className="drilldown-page">
        {/* BACK BUTTON */}
        <div className="drilldown-back">
          <Link to="/dashboard" aria-label="Back to overview">
            <ArrowLeft size={15} />
            BACK TO OVERVIEW
          </Link>
        </div>

        {/* HEADER */}
        <div className="drilldown-header-container">
          <div className="drilldown-title">
            <div className="drilldown-eyebrow">03 / ENTITY DOSSIER</div>
            <h1>{data.entity_name}</h1>
            <p>Supervisory assessment and evidence documentation.</p>
          </div>

          <div
            className="drilldown-scores-container"
            style={{ display: "flex", gap: "20px" }}
          >
            <div className={`drilldown-score-panel ${scoreClassStr}`}>
              <span>RISK SCORE</span>
              <strong>{Number(data.risk_score).toFixed(1)}</strong>
              <small>/ 100</small>
            </div>

            {data.component_scores && (
              <div
                className="drilldown-component-scores"
                style={{
                  display: "flex",
                  gap: "15px",
                  background: "rgba(255,255,255,0.02)",
                  padding: "15px 20px",
                  borderRadius: "4px",
                  border: "1px solid rgba(255,255,255,0.05)",
                }}
              >
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      color: "#8e96a0",
                      letterSpacing: "0.5px",
                    }}
                  >
                    EXECUTION GAP
                  </span>
                  <strong style={{ fontSize: "1.2rem", color: "#f2f4f7" }}>
                    {(data.component_scores.execution_gap || 0).toFixed(2)}
                  </strong>
                </div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      color: "#8e96a0",
                      letterSpacing: "0.5px",
                    }}
                  >
                    NEGATIVE SPACE
                  </span>
                  <strong style={{ fontSize: "1.2rem", color: "#f2f4f7" }}>
                    {(data.component_scores.negative_space || 0).toFixed(2)}
                  </strong>
                </div>
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <span
                    style={{
                      fontSize: "0.75rem",
                      color: "#8e96a0",
                      letterSpacing: "0.5px",
                    }}
                  >
                    ANOMALY
                  </span>
                  <strong style={{ fontSize: "1.2rem", color: "#f2f4f7" }}>
                    {(data.component_scores.anomaly || 0).toFixed(2)}
                  </strong>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* STATUS BANNER */}
        {isHighRisk && (
          <div className="review-banner high-risk">
            <AlertTriangle size={20} strokeWidth={1.5} />
            <div>
              <strong>Manual Supervisory Review Recommended</strong>
              <p>
                Observed signals ({primaryDriverText}) warrant manual supervisory
                review. Review identified signals and evidence below.
              </p>
            </div>
          </div>
        )}

        {!isHighRisk && (
          <div className="review-banner low-risk">
            <CheckCircle2 size={20} strokeWidth={1.5} />
            <div>
              <strong>Entity Operational Status Acceptable</strong>
              <p>
                No immediate supervisory intervention required based on current
                operational patterns.
              </p>
            </div>
          </div>
        )}

        <div className="drilldown-main-grid">
          {/* FINDINGS */}
          <section className="findings-panel">
            <div className="panel-header">
              <div>
                <div className="panel-label">EVIDENCE GATHERED</div>
                <h2>Review Signals</h2>
              </div>
            </div>

            <div className="findings-grid">
              {!data.findings || data.findings.length === 0 ? (
                <div className="empty-state" style={{ minHeight: "150px" }}>
                  <CheckCircle2 size={24} color="var(--green)" />
                  <h3>No Review Signals</h3>
                  <p>No anomalous findings detected for this entity. Operational patterns are within expected baselines.</p>
                </div>
              ) : (
                data.findings.map((finding, idx) => (
                  <div className="finding-card" key={idx}>
                    <div className="finding-card-header">
                      <FileText size={16} />
                      <strong>
                        {finding.detector}: {finding.rule}
                      </strong>
                    </div>
                    <p className="finding-desc">{finding.description}</p>
                    <div className="finding-meta">
                      <span>EVIDENCE INSTANCES</span>
                      <strong>{finding.evidence_count}</strong>
                    </div>
                    {finding.evidence && finding.evidence.length > 0 && (
                      <div
                        className="finding-evidence-list"
                        style={{
                          marginTop: "10px",
                          paddingTop: "10px",
                          borderTop: "1px solid rgba(255,255,255,0.05)",
                          fontSize: "0.85rem",
                          color: "#8e96a0",
                          display: "flex",
                          flexDirection: "column",
                          gap: "6px",
                        }}
                      >
                        {finding.evidence.map((ev, i) => {
                          const alertId =
                            ev.alert_id ||
                            (ev.detail
                              ? ev.detail.includes(" — ")
                                ? ev.detail.split(" — ").pop()
                                : ev.detail
                              : `EVIDENCE-${i + 1}`);
                          return (
                            <div key={i} style={{ display: "flex", gap: "8px" }}>
                              <span
                                style={{
                                  color: "#f2f4f7",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                {alertId}
                              </span>
                              <span>-</span>
                              <span>{ev.reason}</span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </section>

          {/* BENCHMARK (SIDE) */}
          <section className="peer-panel">
            <div className="panel-header">
              <div>
                <div className="panel-label">PEER BENCHMARKING</div>
                <h2>Deviation Details</h2>
              </div>
            </div>

            {benchmarkArray.length === 0 ? (
              <div
                className="empty-state"
                style={{ minHeight: "150px", marginTop: "20px" }}
              >
                <h3>No Benchmark Data</h3>
                <p>Peer benchmark data is currently unavailable for this entity. Check back after next data ingestion.</p>
              </div>
            ) : (
              <>
                <div className="peer-chart-container" role="img" aria-label={`Bar chart comparing ${entityName} metrics to peer medians`}>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart
                      data={benchmarkArray}
                      margin={{ top: 15, right: 15, left: -10, bottom: 5 }}
                    >
                      <CartesianGrid
                        stroke="rgba(255,255,255,0.07)"
                        vertical={false}
                      />
                      <XAxis
                        dataKey="metric"
                        tick={{ fill: "#8e96a0", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis
                        tick={{ fill: "#8e96a0", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <Tooltip
                        contentStyle={{
                          background: "#11151a",
                          border: "1px solid #2a3038",
                          color: "#f2f4f7",
                          fontSize: "11px",
                        }}
                      />
                      <Bar
                        dataKey="entity"
                        fill="#56c7ff"
                        name="Entity"
                        barSize={18}
                      />
                      <Bar
                        dataKey="peer"
                        fill="#3b424b"
                        name="Peer Median"
                        barSize={18}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                  <div className="chart-legend">
                    <span>
                      <i className="legend-entity" />
                      THIS ENTITY
                    </span>
                    <span>
                      <i className="legend-peer" />
                      PEER MEDIAN
                    </span>
                  </div>
                </div>

                <div className="peer-metrics-list">
                  {benchmarkArray.map((item, idx) => (
                    <div className="peer-metric-item" key={idx}>
                      <span>{item.metric.toUpperCase()}</span>
                      <div className="peer-metric-values">
                        <strong>{item.entity}</strong>
                        <small>Peer: {item.peer}</small>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}

