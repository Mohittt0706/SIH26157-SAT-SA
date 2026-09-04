import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  ShieldAlert,
  Activity,
  BarChart3,
  AlertTriangle,
} from "lucide-react";
import { getRiskScores } from "../lib/api";
import usePageMetadata from "../hooks/usePageMetadata";

export default function DashboardPage() {
  usePageMetadata({
    title: "Supervisory Overview | VEIL",
    description: "Assessment results generated from structured SOC operational data.",
    path: "/dashboard",
  });
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchScores = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getRiskScores();
        setEntities(data || []);
      } catch (err) {
        console.error(err);
        let safeError = "Failed to load risk scores. Please ensure the backend server is running.";
        if (err.response?.data?.detail && typeof err.response.data.detail === "string") {
          safeError = err.response.data.detail;
        }
        setError(safeError);
      } finally {
        setLoading(false);
      }
    };
    fetchScores();
  }, []);

  if (loading) {
    return (
      <main className="dashboard-shell">
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
            <span className="active">OVERVIEW</span>
          </div>
          <div className="dashboard-status">
            <span />
            OFFLINE MODE
          </div>
        </nav>
        <section className="dashboard-page" style={{ paddingTop: "20px" }}>
          <div className="dashboard-header" style={{ marginBottom: "20px" }}>
            <div>
              <div className="skeleton skeleton-text" style={{ width: "150px" }} />
              <div className="skeleton skeleton-title" style={{ width: "250px", height: "40px", marginTop: "10px" }} />
              <div className="skeleton skeleton-text" style={{ width: "350px", marginTop: "10px" }} />
            </div>
          </div>
          <div className="dashboard-metrics" style={{ marginBottom: "40px" }}>
            <div className="skeleton skeleton-card" style={{ height: "90px" }} />
            <div className="skeleton skeleton-card" style={{ height: "90px" }} />
            <div className="skeleton skeleton-card" style={{ height: "90px" }} />
          </div>
          <div className="dashboard-main-grid">
            <div className="skeleton skeleton-card" style={{ height: "300px" }} />
            <div className="skeleton skeleton-card" style={{ height: "300px" }} />
          </div>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="dashboard-shell">
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
            <span className="active">OVERVIEW</span>
          </div>
          <div className="dashboard-status">
            <span />
            OFFLINE MODE
          </div>
        </nav>
        <div className="error-state">
          <AlertTriangle size={32} />
          <h3>Analysis Failed</h3>
          <p>{error}</p>
        </div>
      </main>
    );
  }

  const totalAlerts = entities.reduce((sum, e) => sum + (e.alert_count || 0), 0);
  const reviewSignals = entities.reduce(
    (sum, e) => sum + (e.findings_summary?.length || 0),
    0
  );

  const driverCounts = {};
  entities.forEach((e) => {
    if (e.primary_driver && e.primary_driver !== "Normal") {
      driverCounts[e.primary_driver] = (driverCounts[e.primary_driver] || 0) + 1;
    }
  });
  const driverEntries = Object.entries(driverCounts).sort((a, b) => b[1] - a[1]);
  const totalDrivers = driverEntries.reduce((sum, [_, count]) => sum + count, 0);

  const getSignalText = (entity) => {
    if (entity.findings_summary && entity.findings_summary.length > 0) {
      return entity.findings_summary.join(", ");
    }
    const band = (entity.risk_band || "").toLowerCase();
    if (band === "medium") {
      return "No specific findings — statistical deviation only";
    }
    if (band === "low") {
      return "No significant findings";
    }
    return entity.primary_driver || "Normal";
  };

  return (
    <main className="dashboard-shell">
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
          <span className="active">OVERVIEW</span>
        </div>
        <div className="dashboard-status">
          <span />
          OFFLINE MODE
        </div>
      </nav>

      <section className="dashboard-page">
        {/* HEADER */}
        <div className="dashboard-header">
          <div>
            <div className="dashboard-eyebrow">
              02 / SUPERVISORY OVERVIEW
            </div>
            <h1>
              SOC
              <br />
              <span>OVERVIEW.</span>
            </h1>
            <p>
              Assessment results generated from structured SOC operational
              data.
            </p>
          </div>
          <div className="dataset-info">
            <span>ACTIVE DATASET</span>
            <strong>ACTIVE SOC DATASET</strong>
            <small>{totalAlerts} records · {entities.length} entities</small>
          </div>
        </div>

        {/* METRICS */}
        <div className="dashboard-metrics">
          <div className="dashboard-metric">
            <div className="metric-icon">
              <ShieldAlert size={17} />
            </div>
            <div>
              <span>ENTITIES ANALYZED</span>
              <strong>{entities.length}</strong>
            </div>
          </div>
          <div className="dashboard-metric">
            <div className="metric-icon">
              <Activity size={17} />
            </div>
            <div>
              <span>TOTAL ALERTS</span>
              <strong>{totalAlerts}</strong>
            </div>
          </div>
          <div className="dashboard-metric">
            <div className="metric-icon">
              <BarChart3 size={17} />
            </div>
            <div>
              <span>REVIEW SIGNALS</span>
              <strong>{reviewSignals < 10 ? `0${reviewSignals}` : `0${reviewSignals}`.slice(-2)}</strong>
            </div>
          </div>
        </div>

        {/* MAIN ANALYSIS */}
        <div className="dashboard-main-grid">
          {/* RANKING */}
          <section className="ranking-panel">
            <div className="panel-header">
              <div>
                <div className="panel-label">RISK RANKING</div>
                <h2>Entities requiring attention</h2>
              </div>
              <span className="panel-meta">SCORE / 100</span>
            </div>
            <div className="entity-table">
              <div className="entity-table-head">
                <span>#</span>
                <span>ENTITY</span>
                <span>SIGNAL</span>
                <span>SCORE</span>
                <span />
              </div>
              {entities.length === 0 ? (
                <div className="empty-state" style={{ minHeight: "200px", gridColumn: "1 / -1" }}>
                  <ShieldAlert size={24} />
                  <h3>No Entities</h3>
                  <p>No entities were found in the active dataset. Please upload a new dataset containing entity records.</p>
                </div>
              ) : (
                [...entities]
                  .sort((a, b) => b.risk_score - a.risk_score)
                  .map((entity, idx) => {
                    const rank = (idx + 1).toString().padStart(2, "0");
                    const bandLower = (entity.risk_band || "low").toLowerCase();
                    const scoreClass = `score-${bandLower}`;
                    return (
                      <Link
                        key={entity.entity_name}
                        to={`/entities/${encodeURIComponent(entity.entity_name)}`}
                        className="entity-row"
                      >
                        <span className="entity-rank">{rank}</span>
                        <span className="entity-title">{entity.entity_name}</span>
                        <span className={`entity-signal ${bandLower}`}>
                          <span className="signal-dot" />
                          {getSignalText(entity)}
                        </span>
                        <span className={`entity-score ${scoreClass}`}>
                          {Number(entity.risk_score).toFixed(1)}
                        </span>
                        <span className="entity-arrow">
                          <ArrowUpRight size={15} />
                        </span>
                      </Link>
                    );
                  })
              )}
            </div>
          </section>

          {/* SIDE PANEL */}
          <section className="signals-panel">
            <div className="panel-header">
              <div>
                <div className="panel-label">SIGNAL DISTRIBUTION</div>
                <h2>Review signals</h2>
              </div>
            </div>
            <div className="signal-list">
              {driverEntries.length === 0 ? (
                <div className="empty-state" style={{ minHeight: "150px", padding: "20px" }}>
                  <p>No review signals identified.</p>
                </div>
              ) : (
                driverEntries.map(([driver, count], idx) => {
                  const percent = totalDrivers > 0 ? Math.round((count / totalDrivers) * 100) : 0;
                  const num = (idx + 1).toString().padStart(2, "0");
                  return (
                    <div className="signal-item" key={driver}>
                      <div>
                        <span className="signal-number">{num}</span>
                        <strong>{driver}</strong>
                      </div>
                      <span className="signal-percent">{percent}%</span>
                    </div>
                  );
                })
              )}
            </div>
            <div className="review-note">
              <span>SUPERVISORY NOTE</span>
              <p>
                Signals indicate patterns requiring review. They do not by
                themselves establish a security failure.
              </p>
            </div>
          </section>
        </div>

        {/* BENCHMARK */}
        <section className="benchmark-section">
          <div className="panel-header">
            <div>
              <div className="panel-label">PEER BENCHMARKING</div>
              <h2>Operational deviation</h2>
            </div>
            <span className="panel-meta">
              ENTITY VS PEER MEDIAN
            </span>
          </div>
          <div className="benchmark-grid">
            <div className="empty-state" style={{ gridColumn: "1 / -1", minHeight: "150px" }}>
              <BarChart3 size={24} />
              <h3>Benchmarking Data</h3>
              <p>Select a specific entity from the risk ranking to view detailed peer benchmarking data and deviations.</p>
            </div>
          </div>
        </section>

        {/* FOOTNOTE */}
        <div className="dashboard-footnote">
          <span>ANALYSIS STATUS</span>
          <strong>REVIEW SIGNALS IDENTIFIED</strong>
          <p>
            Select an entity above to inspect evidence and findings.
          </p>
        </div>
      </section>
    </main>
  );
}

