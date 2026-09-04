import { Link } from "react-router-dom";
import usePageMetadata from "../hooks/usePageMetadata";

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

const entities = [
  {
    name: "Continental Banking Corp",
    score: 87,
    signal: "Execution Gap",
  },
  {
    name: "Indus Financial Services",
    score: 81,
    signal: "Execution Gap",
  },
  {
    name: "Fortis Defense Systems",
    score: 76,
    signal: "Anomaly",
  },
  {
    name: "Delta Rail Systems",
    score: 69,
    signal: "Negative Space",
  },
];

export default function LandingPage() {
  usePageMetadata({
    title: "VEIL | Supervisory Intelligence",
    description: "Evidence-backed signals for human review — not definitive security verdicts.",
    path: "/",
  });
  return (
    <main className="site-shell">
      {/* NAVBAR */}
      <nav className="navbar">
        <div className="brand">
          <div className="brand-mark">V</div>
          <div>
            <div className="brand-name">VEIL</div>
            <div className="brand-subtitle">Supervisory Intelligence for SOC Assessment</div>
          </div>
        </div>

        <div className="nav-links">
          <a href="#platform">Platform</a>
          <a href="#capabilities">Capabilities</a>
          <a href="#workflow">How It Works</a>
        </div>

        <div className="nav-status">
          <span className="status-dot" />
          OFFLINE MODE
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
              <strong>10</strong>
            </div>

            <div className="metric">
              <span>ALERTS</span>
              <strong>639</strong>
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

            <div className="chart-bars">
              <div className="chart-row">
                <span>HIGH</span>
                <div className="bar-track">
                  <div className="bar-fill high" />
                </div>
                <b>87</b>
              </div>

              <div className="chart-row">
                <span>MEDIUM</span>
                <div className="bar-track">
                  <div className="bar-fill medium" />
                </div>
                <b>61</b>
              </div>

              <div className="chart-row">
                <span>LOW</span>
                <div className="bar-track">
                  <div className="bar-fill low" />
                </div>
                <b>28</b>
              </div>
            </div>
          </div>

          <div className="preview-table">
            <div className="table-heading">
              <span>ENTITY</span>
              <span>SIGNAL</span>
              <span>SCORE</span>
            </div>

            {entities.map((entity) => (
              <div className="table-row" key={entity.name}>
                <span className="entity-name">{entity.name}</span>
                <span className="signal-text">{entity.signal}</span>
                <span className="entity-score">{entity.score}</span>
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
