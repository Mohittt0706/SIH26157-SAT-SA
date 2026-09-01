import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, AlertTriangle, FileText, CheckCircle2 } from "lucide-react";
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
  
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDetails = async () => {
      try {
        const details = await getEntityDetails(entityName);
        if (!details) {
          setError("Entity not found.");
        } else {
          setData(details);
        }
      } catch (err) {
        console.error(err);
        if (err.response?.status === 404) {
          setError("Entity not found in active dataset.");
        } else {
          setError("Failed to load entity details.");
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
          <Link to="/" className="dashboard-brand">
            <div className="dashboard-brand-mark">V</div>
            <div>
              <div className="dashboard-brand-name">VEIL</div>
              <div className="dashboard-brand-subtitle">Supervisory Intelligence for SOC Assessment</div>
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
        <div className="loading-state">
          <div className="spinner" />
          <h3>Retrieving entity dossier...</h3>
          <p>Analyzing signals and benchmark data for {entityName}.</p>
        </div>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="drilldown-shell">
        <nav className="dashboard-nav">
          <Link to="/" className="dashboard-brand">
            <div className="dashboard-brand-mark">V</div>
            <div>
              <div className="dashboard-brand-name">VEIL</div>
              <div className="dashboard-brand-subtitle">Supervisory Intelligence for SOC Assessment</div>
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
          <Link to="/dashboard" style={{ marginTop: '20px', color: 'var(--accent)', textDecoration: 'underline' }}>
            Return to Dashboard
          </Link>
        </div>
      </main>
    );
  }

  const isHighRisk = data.risk_band === "critical" || data.risk_band === "high";
  const scoreClassStr = `score-${(data.risk_band || 'low').toLowerCase()}`;

  // Prepare benchmark data array
  const benchmarkArray = [];
  if (data.peer_metrics) {
    if (data.peer_metrics.avg_closure_seconds) {
      benchmarkArray.push({
        metric: "Closure (m)",
        entity: Math.round(data.peer_metrics.avg_closure_seconds.entity / 60),
        peer: Math.round(data.peer_metrics.avg_closure_seconds.peer_median / 60)
      });
    }
    if (data.peer_metrics.escalation_rate) {
      benchmarkArray.push({
        metric: "Escalation %",
        entity: Math.round(data.peer_metrics.escalation_rate.entity * 100),
        peer: Math.round(data.peer_metrics.escalation_rate.peer_median * 100)
      });
    }
    if (data.peer_metrics.avg_note_length) {
      benchmarkArray.push({
        metric: "Note Len",
        entity: Math.round(data.peer_metrics.avg_note_length.entity),
        peer: Math.round(data.peer_metrics.avg_note_length.peer_median)
      });
    }
    if (data.peer_metrics.alert_count) {
      benchmarkArray.push({
        metric: "Alerts",
        entity: data.peer_metrics.alert_count.entity,
        peer: data.peer_metrics.alert_count.peer_median
      });
    }
  }

  return (
    <main className="drilldown-shell">
      {/* NAVBAR */}
      <nav className="dashboard-nav">
        <Link to="/" className="dashboard-brand">
          <div className="dashboard-brand-mark">V</div>
          <div>
            <div className="dashboard-brand-name">VEIL</div>
            <div className="dashboard-brand-subtitle">Supervisory Intelligence for SOC Assessment</div>
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
          <Link to="/dashboard">
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

          <div className={`drilldown-score-panel ${scoreClassStr}`}>
            <span>RISK SCORE</span>
            <strong>{Number(data.risk_score).toFixed(1)}</strong>
            <small>/ 100</small>
          </div>
        </div>

        {/* STATUS BANNER */}
        {isHighRisk && (
          <div className="review-banner high-risk">
            <AlertTriangle size={20} strokeWidth={1.5} />
            <div>
              <strong>Manual Supervisory Review Recommended</strong>
              <p>Observed signals ({data.primary_driver}) warrant manual supervisory review. Review identified signals and evidence below.</p>
            </div>
          </div>
        )}

        {!isHighRisk && (
          <div className="review-banner low-risk">
            <CheckCircle2 size={20} strokeWidth={1.5} />
            <div>
              <strong>Entity Operational Status Acceptable</strong>
              <p>No immediate supervisory intervention required based on current operational patterns.</p>
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
                <div className="empty-state" style={{ minHeight: '150px' }}>
                  <CheckCircle2 size={24} color="var(--green)" />
                  <p>No anomalous findings detected for this entity.</p>
                </div>
              ) : (
                data.findings.map((finding, idx) => (
                  <div className="finding-card" key={idx}>
                    <div className="finding-card-header">
                      <FileText size={16} />
                      <strong>{finding.detector}: {finding.rule}</strong>
                    </div>
                    <p className="finding-desc">{finding.description}</p>
                    <div className="finding-meta">
                      <span>EVIDENCE INSTANCES</span>
                      <strong>{finding.evidence_count}</strong>
                    </div>
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
              <div className="empty-state" style={{ minHeight: '150px', marginTop: '20px' }}>
                <p>Peer benchmark data unavailable.</p>
              </div>
            ) : (
              <>
                <div className="peer-chart-container">
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart
                      data={benchmarkArray}
                      margin={{ top: 15, right: 15, left: -10, bottom: 5 }}
                    >
                      <CartesianGrid stroke="rgba(255,255,255,0.07)" vertical={false} />
                      <XAxis dataKey="metric" tick={{ fill: "#8e96a0", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "#8e96a0", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{
                          background: "#11151a",
                          border: "1px solid #2a3038",
                          color: "#f2f4f7",
                          fontSize: "11px",
                        }}
                      />
                      <Bar dataKey="entity" fill="#56c7ff" name="Entity" barSize={18} />
                      <Bar dataKey="peer" fill="#3b424b" name="Peer Median" barSize={18} />
                    </BarChart>
                  </ResponsiveContainer>
                  <div className="chart-legend">
                    <span><i className="legend-entity" />THIS ENTITY</span>
                    <span><i className="legend-peer" />PEER MEDIAN</span>
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
