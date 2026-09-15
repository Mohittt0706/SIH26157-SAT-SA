import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import usePageMetadata from "../hooks/usePageMetadata";
import BrandBlock from "../components/BrandBlock";
import { getRiskScores } from "../lib/api";

const capabilities = [
  {
    number: "01",
    title: "Execution Gap",
    text: "Identify operational patterns that may indicate superficial or inconsistent alert handling.",
  },
  {
    number: "02",
    title: "Negative Space",
    text: "Surface unusual reductions or absences in expected SOC activity that may warrant review.",
  },
  {
    number: "03",
    title: "Anomaly Detection",
    text: "Highlight unusual operational patterns and significant deviations in alert activity.",
  },
  {
    number: "04",
    title: "Peer Benchmarking",
    text: "Compare operational metrics across peer entities to expose meaningful deviations.",
  },
];

// Landing-page preview is bound to the live dataset (GET /api/risk-scores)
// rather than illustrative fixtures — a judge/reviewer landing here first
// must see the same entities and numbers the dashboard shows next, not a
// static showcase that quietly diverges from whatever is actually loaded.
// This page has no blind-review constraint (unlike ManualReviewPage), so
// showing risk_score here is fine.
const PRIMARY_DRIVER_LABELS = {
  execution_gap: "Execution Gap",
  negative_space: "Negative Space",
  anomaly: "Anomaly",
};

const PREVIEW_ENTITY_LIMIT = 4;

function median(sortedValues) {
  const n = sortedValues.length;
  if (n === 0) return null;
  const mid = Math.floor(n / 2);
  return n % 2 === 0 ? (sortedValues[mid - 1] + sortedValues[mid]) / 2 : sortedValues[mid];
}

export default function LandingPage() {
  usePageMetadata({
    title: "VEIL | Supervisory Intelligence",
    description: "Evidence-backed signals for human review — not definitive security verdicts.",
    path: "/",
  });

  // null = still loading (distinct from an empty array, an actually-empty
  // dataset — e.g. nothing uploaded yet).
  const [riskScores, setRiskScores] = useState(null);
  const [riskScoresError, setRiskScoresError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getRiskScores()
      .then((data) => {
        if (!cancelled) setRiskScores(data);
      })
      .catch((err) => {
        console.error("Failed to load risk scores for landing preview:", err);
        if (!cancelled) setRiskScoresError("Live data unavailable.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadingPreview = riskScores === null && !riskScoresError;
  const hasData = Array.isArray(riskScores) && riskScores.length > 0;

  const sortedByScoreDesc = hasData ? [...riskScores].sort((a, b) => b.risk_score - a.risk_score) : [];
  const previewEntities = sortedByScoreDesc.slice(0, PREVIEW_ENTITY_LIMIT);

  const entityCount = hasData ? riskScores.length : null;
  const alertCount = hasData ? riskScores.reduce((sum, r) => sum + (r.alert_count || 0), 0) : null;

  const scoresAsc = hasData ? sortedByScoreDesc.map((r) => r.risk_score).reverse() : [];
  const highScore = scoresAsc.length ? scoresAsc[scoresAsc.length - 1] : null;
  const lowScore = scoresAsc.length ? scoresAsc[0] : null;
  const mediumScore = median(scoresAsc);

  return (
    <main className="site-shell">
      {/* NAVBAR */}
      <nav className="navbar">
        <BrandBlock />

        <div className="nav-links">
          <a href="#platform">Platform</a>
          <a href="#capabilities">Capabilities</a>
          <a href="#workflow">How It Works</a>
        </div>

        <div className="nav-status">
          {/* Static — describes how VEIL is deployed (air-gapped, no
              external network dependency), not the browser's own
              connectivity. A machine inside an air-gapped network reports
              navigator.onLine === false, which would say nothing true or
              useful about this system, so this never reads it. */}
          <span className="status-dot" />
          AIR-GAPPED
        </div>
      </nav>

      {/* HERO */}
      <section className="hero-section" id="platform">
        <div className="hero-copy">
          <div className="eyebrow">
            SUPERVISORY INTELLIGENCE / SOC ASSESSMENT
          </div>

          <h1>
            SEE THE SIGNAL
            <br />
            <span>BEHIND SOC ACTIVITY.</span>
          </h1>

          <p className="hero-description">
            VEIL analyzes structured SOC operational data to surface
            execution gaps, negative space, anomalies, and peer deviations
            requiring supervisory attention.
          </p>

          <div className="hero-actions">
            <Link to="/upload" className="primary-button">
              START ANALYSIS
              <span>→</span>
            </Link>

            <a href="#workflow" className="secondary-button">
              EXPLORE PLATFORM
            </a>
          </div>

          <div className="hero-note">
            <span>01</span>
            Evidence-backed signals, not definitive security verdicts.
          </div>
        </div>

        {/* ANALYTICAL PREVIEW */}
        <div className="analytics-preview">
          <div className="preview-header">
            <div>
              <div className="preview-kicker">SOC SUPERVISORY OVERVIEW</div>
              <div className="preview-title">Operational Snapshot</div>
            </div>

            <div className="preview-live">
              <span className="status-dot" />
              LOCAL
            </div>
          </div>

          <div className="metrics-grid">
            <div className="metric">
              <span>ENTITIES</span>
              <strong>{entityCount === null ? "—" : entityCount}</strong>
            </div>

            <div className="metric">
              <span>ALERTS</span>
              <strong>{alertCount === null ? "—" : alertCount}</strong>
            </div>

            <div className="metric">
              <span>REVIEW SIGNALS</span>
              <strong>04</strong>
            </div>
          </div>

          <div className="preview-chart">
            <div className="chart-header">
              <span>RISK DISTRIBUTION</span>
              <span>0 — 100</span>
            </div>

            {!loadingPreview && !hasData && (
              <p style={{ fontSize: "12px", color: "var(--muted)", margin: "19px 0 0" }}>
                {riskScoresError || "No dataset loaded yet — upload one to see live signals."}
              </p>
            )}

            {(loadingPreview || hasData) && (
              <div className="chart-bars">
                <div className="chart-row">
                  <span>HIGH</span>
                  <div className="bar-track">
                    <div className="bar-fill high" style={hasData ? { width: `${highScore}%` } : undefined} />
                  </div>
                  <b>{hasData ? highScore.toFixed(0) : "—"}</b>
                </div>

                <div className="chart-row">
                  <span>MEDIUM</span>
                  <div className="bar-track">
                    <div className="bar-fill medium" style={hasData ? { width: `${mediumScore}%` } : undefined} />
                  </div>
                  <b>{hasData ? mediumScore.toFixed(0) : "—"}</b>
                </div>

                <div className="chart-row">
                  <span>LOW</span>
                  <div className="bar-track">
                    <div className="bar-fill low" style={hasData ? { width: `${lowScore}%` } : undefined} />
                  </div>
                  <b>{hasData ? lowScore.toFixed(0) : "—"}</b>
                </div>
              </div>
            )}
          </div>

          <div className="preview-table">
            <div className="table-heading">
              <span>ENTITY</span>
              <span>SIGNAL</span>
              <span>SCORE</span>
            </div>

            {!loadingPreview && !hasData && (
              <p style={{ fontSize: "12px", color: "var(--muted)", margin: "12px 0" }}>
                {riskScoresError ? "" : "Upload a dataset to populate this preview."}
              </p>
            )}

            {previewEntities.map((entity) => (
              <div className="table-row" key={entity.entity_name}>
                <span className="entity-name">{entity.entity_name}</span>
                <span className="signal-text">
                  {PRIMARY_DRIVER_LABELS[entity.primary_driver] || entity.primary_driver || "—"}
                </span>
                <span className="entity-score">{entity.risk_score.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* INTRO */}
      <section className="intro-section">
        <div className="section-label">WHY VEIL</div>

        <div className="intro-content">
          <h2>
            Operational data contains more
            <br />
            than just alert counts.
          </h2>

          <p>
            Supervisory assessment requires looking beyond individual cases.
            VEIL turns structured SOC activity into patterns, comparisons,
            and evidence that help reviewers focus their attention where it
            matters most.
          </p>
        </div>
      </section>

      {/* CAPABILITIES */}
      <section className="capabilities-section" id="capabilities">
        <div className="section-topline">
          <div className="section-label">CORE CAPABILITIES</div>
          <div className="section-index">04 SIGNAL TYPES</div>
        </div>

        <div className="capability-grid">
          {capabilities.map((item) => (
            <article className="capability" key={item.number}>
              <div className="capability-number">{item.number}</div>

              <div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </div>

              <div className="capability-arrow">↗</div>
            </article>
          ))}
        </div>
      </section>

      {/* WORKFLOW */}
      <section className="workflow-section" id="workflow">
        <div className="section-label">HOW IT WORKS</div>

        <h2>
          FROM SOC DATA
          <br />
          TO SUPERVISORY SIGNAL.
        </h2>

        <div className="workflow-line">
          <div className="workflow-step">
            <span>01</span>
            <h3>UPLOAD</h3>
            <p>Structured CSV or JSON records.</p>
          </div>

          <div className="workflow-connector" />

          <div className="workflow-step">
            <span>02</span>
            <h3>ANALYZE</h3>
            <p>Rules, statistical analysis, and anomaly detection.</p>
          </div>

          <div className="workflow-connector" />

          <div className="workflow-step">
            <span>03</span>
            <h3>BENCHMARK</h3>
            <p>Compare operational metrics across peer entities.</p>
          </div>

          <div className="workflow-connector" />

          <div className="workflow-step">
            <span>04</span>
            <h3>REVIEW</h3>
            <p>Inspect findings, evidence, and deviations.</p>
          </div>
        </div>
      </section>

      {/* DISCLAIMER / PRODUCT POSITIONING */}
      <section className="positioning-section">
        <div className="positioning-number">00</div>

        <div className="positioning-copy">
          <div className="section-label">PRODUCT POSITIONING</div>

          <h2>VEIL IS NOT A SIEM.</h2>

          <p>
            It does not replace threat detection infrastructure. VEIL sits
            above structured SOC operational data to support supervisory
            assessment and prioritize cases for manual review.
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section">
        <div>
          <div className="section-label">READY TO ASSESS?</div>

          <h2>
            SURFACE WHAT
            <br />
            NEEDS REVIEW.
          </h2>
        </div>

        <Link to="/upload" className="cta-button">
          START ANALYSIS
          <span>→</span>
        </Link>
      </section>

      {/* FOOTER */}
      <footer className="footer">
        <div>
          <strong>VEIL</strong>
          <span>Supervisory Intelligence for SOC Assessment</span>
        </div>

        <div className="footer-meta">
          <Link to="/privacy">Privacy Policy</Link>
          <Link to="/terms">Terms of Use</Link>
          <Link to="/security">Security Disclosure</Link>
          <Link to="/accessibility">Accessibility</Link>
        </div>
      </footer>
    </main>
  );
}
