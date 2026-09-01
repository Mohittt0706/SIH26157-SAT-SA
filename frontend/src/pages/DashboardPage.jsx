import { Link } from "react-router-dom";
import {
  ArrowUpRight,
  ShieldAlert,
  Activity,
  BarChart3,
  ChevronRight,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

const entities = [
  {
    rank: "01",
    name: "Continental Banking Corp",
    score: 87,
    signal: "Execution Gap",
    severity: "high",
  },
  {
    rank: "02",
    name: "Indus Financial Services",
    score: 81,
    signal: "Execution Gap",
    severity: "high",
  },
  {
    rank: "03",
    name: "Fortis Defense Systems",
    score: 76,
    signal: "Anomaly",
    severity: "high",
  },
  {
    rank: "04",
    name: "Delta Rail Systems",
    score: 69,
    signal: "Negative Space",
    severity: "medium",
  },
  {
    rank: "05",
    name: "Aster Energy Solutions",
    score: 34,
    signal: "Normal",
    severity: "low",
  },
  {
    rank: "06",
    name: "Bharat Telecom Systems",
    score: 31,
    signal: "Normal",
    severity: "low",
  },
  {
    rank: "07",
    name: "National Port Services",
    score: 28,
    signal: "Normal",
    severity: "low",
  },
];

const benchmarkData = [
  { metric: "Closure Time", entity: 14, peer: 46 },
  { metric: "Escalation", entity: 3, peer: 18 },
  { metric: "Investigation", entity: 21, peer: 64 },
];

function scoreClass(score) {
  if (score >= 70) return "score-high";
  if (score >= 40) return "score-medium";
  return "score-low";
}

export default function DashboardPage() {
  return (
    <main className="dashboard-shell">
      {/* NAVBAR */}
      <nav className="dashboard-nav">
        <Link to="/" className="dashboard-brand">
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
            <strong>synthetic_soc_alerts.csv</strong>
            <small>639 records · 10 entities</small>
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
              <strong>10</strong>
            </div>
          </div>

          <div className="dashboard-metric">
            <div className="metric-icon">
              <Activity size={17} />
            </div>

            <div>
              <span>TOTAL ALERTS</span>
              <strong>639</strong>
            </div>
          </div>

          <div className="dashboard-metric">
            <div className="metric-icon">
              <BarChart3 size={17} />
            </div>

            <div>
              <span>REVIEW SIGNALS</span>
              <strong>04</strong>
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

              {entities.map((entity) => (
                <Link
                  key={entity.name}
                  to={`/entities/${encodeURIComponent(entity.name)}`}
                  className="entity-row"
                >
                  <span className="entity-rank">{entity.rank}</span>

                  <span className="entity-title">{entity.name}</span>

                  <span className={`entity-signal ${entity.severity}`}>
                    <span className="signal-dot" />
                    {entity.signal}
                  </span>

                  <span className={`entity-score ${scoreClass(entity.score)}`}>
                    {entity.score}
                  </span>

                  <span className="entity-arrow">
                    <ArrowUpRight size={15} />
                  </span>
                </Link>
              ))}
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
              <div className="signal-item">
                <div>
                  <span className="signal-number">02</span>
                  <strong>Execution Gap</strong>
                </div>
                <span className="signal-percent">50%</span>
              </div>

              <div className="signal-item">
                <div>
                  <span className="signal-number">01</span>
                  <strong>Negative Space</strong>
                </div>
                <span className="signal-percent">25%</span>
              </div>

              <div className="signal-item">
                <div>
                  <span className="signal-number">01</span>
                  <strong>Anomaly</strong>
                </div>
                <span className="signal-percent">25%</span>
              </div>
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
            <div className="benchmark-chart">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  data={benchmarkData}
                  margin={{
                    top: 15,
                    right: 15,
                    left: -10,
                    bottom: 5,
                  }}
                >
                  <CartesianGrid
                    stroke="rgba(255,255,255,0.07)"
                    vertical={false}
                  />

                  <XAxis
                    dataKey="metric"
                    tick={{
                      fill: "#8e96a0",
                      fontSize: 10,
                    }}
                    axisLine={false}
                    tickLine={false}
                  />

                  <YAxis
                    tick={{
                      fill: "#8e96a0",
                      fontSize: 10,
                    }}
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
                    barSize={24}
                  />

                  <Bar
                    dataKey="peer"
                    fill="#3b424b"
                    name="Peer Median"
                    barSize={24}
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

            <div className="benchmark-summary">
              <div className="benchmark-item">
                <span>CLOSURE TIME</span>
                <strong>
                  14<span> min</span>
                </strong>
                <small>Peer median: 46 min</small>
              </div>

              <div className="benchmark-item">
                <span>ESCALATION RATE</span>
                <strong>
                  3<span>%</span>
                </strong>
                <small>Peer median: 18%</small>
              </div>

              <div className="benchmark-item">
                <span>INVESTIGATION RATE</span>
                <strong>
                  21<span>%</span>
                </strong>
                <small>Peer median: 64%</small>
              </div>
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
