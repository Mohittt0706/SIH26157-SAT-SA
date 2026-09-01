"use client";

import { use } from "react";
import Link from "next/link";
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

const MOCK_ENTITIES = {
  "Continental Banking Corp": {
    score: 87,
    severity: "high",
    signals: [
      { type: "Execution Gap", count: 42, description: "Discrepancy in automated script execution vs expected state." }
    ],
    benchmark: [
      { metric: "Closure Time", entity: 14, peer: 46 },
      { metric: "Escalation", entity: 3, peer: 18 },
      { metric: "Investigation", entity: 21, peer: 64 },
    ]
  },
  "Indus Financial Services": {
    score: 81,
    severity: "high",
    signals: [
      { type: "Execution Gap", count: 35, description: "Failed security policy application across endpoints." }
    ],
    benchmark: [
      { metric: "Closure Time", entity: 14, peer: 46 },
      { metric: "Escalation", entity: 3, peer: 18 },
      { metric: "Investigation", entity: 21, peer: 64 },
    ]
  },
  "Fortis Defense Systems": {
    score: 76,
    severity: "high",
    signals: [
      { type: "Anomaly", count: 18, description: "High frequency of failed authentication attempts from unknown IPs." }
    ],
    benchmark: [
      { metric: "Closure Time", entity: 14, peer: 46 },
      { metric: "Escalation", entity: 3, peer: 18 },
      { metric: "Investigation", entity: 21, peer: 64 },
    ]
  },
  "Delta Rail Systems": {
    score: 69,
    severity: "medium",
    signals: [
      { type: "Negative Space", count: 21, description: "Gaps in sensor reporting from remote field units." }
    ],
    benchmark: [
      { metric: "Closure Time", entity: 14, peer: 46 },
      { metric: "Escalation", entity: 3, peer: 18 },
      { metric: "Investigation", entity: 21, peer: 64 },
    ]
  }
};

const DEFAULT_ENTITY = {
  score: 30,
  severity: "low",
  signals: [
    { type: "Normal", count: 0, description: "No significant anomalies or execution gaps detected." }
  ],
  benchmark: [
    { metric: "Closure Time", entity: 45, peer: 46 },
    { metric: "Escalation", entity: 17, peer: 18 },
    { metric: "Investigation", entity: 62, peer: 64 },
  ]
};

function scoreClass(score) {
  if (score >= 70) return "score-high";
  if (score >= 40) return "score-medium";
  return "score-low";
}

export default function EntityDrillDownPage({ params }) {
  const resolvedParams = use(params);
  const entityName = decodeURIComponent(resolvedParams.entityName);
  const data = MOCK_ENTITIES[entityName] || DEFAULT_ENTITY;

  const isHighRisk = data.score >= 70;

  return (
    <main className="drilldown-shell">
      {/* NAVBAR */}
      <nav className="dashboard-nav">
        <Link href="/" className="dashboard-brand">
          <div className="dashboard-brand-mark">S</div>
          <div>
            <div className="dashboard-brand-name">SAT-SA</div>
            <div className="dashboard-brand-subtitle">SOC SUPERVISORY ANALYTICS</div>
          </div>
        </Link>
        <div className="dashboard-nav-links">
          <Link href="/upload">ANALYZE</Link>
          <Link href="/dashboard">OVERVIEW</Link>
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
          <Link href="/dashboard">
            <ArrowLeft size={15} />
            BACK TO OVERVIEW
          </Link>
        </div>

        {/* HEADER */}
        <div className="drilldown-header-container">
          <div className="drilldown-title">
            <div className="drilldown-eyebrow">03 / ENTITY DOSSIER</div>
            <h1>{entityName}</h1>
            <p>Supervisory assessment and evidence documentation.</p>
          </div>
          
          <div className={`drilldown-score-panel ${scoreClass(data.score)}`}>
            <span>RISK SCORE</span>
            <strong>{data.score}</strong>
            <small>/ 100</small>
          </div>
        </div>

        {/* STATUS BANNER */}
        {isHighRisk && (
          <div className="review-banner high-risk">
            <AlertTriangle size={20} strokeWidth={1.5} />
            <div>
              <strong>Manual Supervisory Review Recommended</strong>
              <p>Observed signals warrant manual supervisory review. Review identified signals and evidence below.</p>
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
              {data.signals.map((signal, idx) => (
                <div className="finding-card" key={idx}>
                  <div className="finding-card-header">
                    <FileText size={16} />
                    <strong>{signal.type}</strong>
                  </div>
                  <p className="finding-desc">{signal.description}</p>
                  <div className="finding-meta">
                    <span>EVIDENCE INSTANCES</span>
                    <strong>{signal.count}</strong>
                  </div>
                </div>
              ))}
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
            
            <div className="peer-chart-container">
              <ResponsiveContainer width="100%" height={250}>
                <BarChart
                  data={data.benchmark}
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
              {data.benchmark.map((item, idx) => (
                <div className="peer-metric-item" key={idx}>
                  <span>{item.metric.toUpperCase()}</span>
                  <div className="peer-metric-values">
                    <strong>{item.entity}</strong>
                    <small>Peer: {item.peer}</small>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </section>
    </main>
  );
}
