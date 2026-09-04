import { Link } from "react-router-dom";
import usePageMetadata from "../hooks/usePageMetadata";

export default function SecurityPage() {
  usePageMetadata({
    title: "Security Disclosure | VEIL",
    description: "Responsible security disclosure policy for the VEIL platform.",
    path: "/security",
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
          <h1 style={{ fontSize: "clamp(36px, 4.4vw, 62px)", margin: 0, letterSpacing: "-0.045em" }}>Responsible Disclosure</h1>
          <p style={{ maxWidth: "800px", marginTop: "20px" }}>
            We take the security of the VEIL platform seriously. This policy outlines our approach to coordinated vulnerability disclosure and safe security research.
          </p>
        </div>
      </section>

      <section className="capabilities-section" style={{ paddingTop: "40px" }}>
        <div className="capability-grid">
          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">01</div>
            <div>
              <h3>Disclosure Philosophy</h3>
              <p style={{ maxWidth: "800px" }}>
                We believe in coordinated disclosure. We encourage security researchers to report vulnerabilities to us safely and responsibly, allowing us time to remediate issues before they are made public.
              </p>
            </div>
          </article>
          
          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">02</div>
            <div>
              <h3>What Researchers Should Report</h3>
              <p style={{ maxWidth: "800px" }}>
                We welcome reports concerning authentication bypass, cross-site scripting (XSS), cross-site request forgery (CSRF), data leakage, and insecure direct object references (IDOR).
              </p>
            </div>
          </article>
          
          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">03</div>
            <div>
              <h3>What Not to Test</h3>
              <p style={{ maxWidth: "800px" }}>
                Researchers must NOT engage in Denial of Service (DoS) attacks, social engineering against our staff or users, physical security testing, or destructive data testing. Testing must only occur on instances you are authorized to target.
              </p>
            </div>
          </article>

          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">04</div>
            <div>
              <h3>Reporting Process</h3>
              <p style={{ maxWidth: "800px" }}>
                To report a vulnerability, please contact the designated security administrator for your VEIL deployment instance. [Placeholder: Configure SECURITY_CONTACT_EMAIL in your environment to display specific contact instructions].
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
