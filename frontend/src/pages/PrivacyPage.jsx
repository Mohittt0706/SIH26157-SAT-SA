import { Link } from "react-router-dom";
import usePageMetadata from "../hooks/usePageMetadata";

export default function PrivacyPage() {
  usePageMetadata({
    title: "Privacy Policy | VEIL",
    description: "Privacy and data handling policies for the VEIL Supervisory Assessment platform.",
    path: "/privacy",
  });

  return (
    <main className="site-shell">
      {/* NAVBAR */}
      <nav className="navbar">
        <Link to="/" className="brand" aria-label="VEIL Home">
          <div className="brand-mark">V</div>
          <div>
            <div className="brand-name">VEIL</div>
            <div className="brand-subtitle">Supervisory Intelligence for SOC Assessment</div>
          </div>
        </Link>
        <div className="nav-links">
          <Link to="/upload">Analyze</Link>
          <Link to="/dashboard">Overview</Link>
        </div>
      </nav>

      <section className="intro-section" style={{ paddingBottom: "40px", borderBottom: "none" }}>
        <div className="section-label">LEGAL & COMPLIANCE</div>
        <div className="intro-content" style={{ gridTemplateColumns: "1fr" }}>
          <h1 style={{ fontSize: "clamp(36px, 4.4vw, 62px)", margin: 0, letterSpacing: "-0.045em" }}>Privacy Policy</h1>
          <p style={{ maxWidth: "800px", marginTop: "20px" }}>
            This Privacy Policy outlines how the VEIL Supervisory Intelligence platform handles data uploaded for SOC Assessment. VEIL is designed as a localized, air-gapped capable analytics tool.
          </p>
        </div>
      </section>

      <section className="capabilities-section" style={{ paddingTop: "40px" }}>
        <div className="capability-grid">
          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">01</div>
            <div>
              <h3>Data Collection and Upload</h3>
              <p style={{ maxWidth: "800px" }}>
                Users upload structured Security Operations Center (SOC) operational data in CSV or JSON format. This data typically includes alert metadata, analyst notes, resolution times, and entity identifiers. We do not automatically collect data from your infrastructure.
              </p>
            </div>
          </article>
          
          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">02</div>
            <div>
              <h3>Purpose of Processing</h3>
              <p style={{ maxWidth: "800px" }}>
                The uploaded SOC data is processed strictly to provide supervisory intelligence. The system calculates risk scores, identifies execution gaps, detects anomalies, and benchmarks entities against peer medians to assist human reviewers in prioritizing assessments.
              </p>
            </div>
          </article>
          
          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">03</div>
            <div>
              <h3>Storage and Retention</h3>
              <p style={{ maxWidth: "800px" }}>
                VEIL operates securely and processes data ephemerally during active sessions. Unless explicitly integrated with a persistent data store by your deployment administrator, uploaded data and generated findings are discarded upon application reset.
              </p>
            </div>
          </article>
          
          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">04</div>
            <div>
              <h3>User Responsibility</h3>
              <p style={{ maxWidth: "800px" }}>
                Users are responsible for ensuring that uploaded datasets are appropriately anonymized or cleared of Personally Identifiable Information (PII) before ingestion, consistent with their organization's internal data governance policies.
              </p>
            </div>
          </article>
        </div>
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
          <Link to="/security">Security</Link>
        </div>
      </footer>
    </main>
  );
}
