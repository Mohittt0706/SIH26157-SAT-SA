import { Link } from "react-router-dom";
import usePageMetadata from "../hooks/usePageMetadata";

export default function AccessibilityPage() {
  usePageMetadata({
    title: "Accessibility | VEIL",
    description: "Accessibility statement and compliance for the VEIL Supervisory Assessment platform.",
    path: "/accessibility",
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
          <h1 style={{ fontSize: "clamp(36px, 4.4vw, 62px)", margin: 0, letterSpacing: "-0.045em" }}>Accessibility</h1>
          <p style={{ maxWidth: "800px", marginTop: "20px" }}>
            The VEIL platform is committed to ensuring digital accessibility for people with disabilities. We continually improve the user experience for everyone and apply the relevant accessibility standards.
          </p>
        </div>
      </section>

      <section className="capabilities-section" style={{ paddingTop: "40px" }}>
        <div className="capability-grid">
          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">01</div>
            <div>
              <h3>Keyboard Navigation</h3>
              <p style={{ maxWidth: "800px" }}>
                All interactive elements, including data tables, forms, and charts, are fully accessible via keyboard navigation. Visual focus indicators are provided to aid navigation without a mouse.
              </p>
            </div>
          </article>
          
          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">02</div>
            <div>
              <h3>Screen Reader Support</h3>
              <p style={{ maxWidth: "800px" }}>
                We provide appropriate ARIA labels and semantic HTML markup to ensure that screen readers can effectively interpret and vocalize the content, particularly regarding complex operational data.
              </p>
            </div>
          </article>
          
          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">03</div>
            <div>
              <h3>Visual Design & Contrast</h3>
              <p style={{ maxWidth: "800px" }}>
                VEIL utilizes a high-contrast dark theme designed to minimize eye strain during extended analytical sessions. We aim to conform to WCAG contrast requirements across text and graphical elements.
              </p>
            </div>
          </article>

          <article className="capability" style={{ minHeight: "auto", padding: "40px 0" }}>
            <div className="capability-number">04</div>
            <div>
              <h3>Reduced Motion</h3>
              <p style={{ maxWidth: "800px" }}>
                The interface respects system-level reduced motion preferences. When enabled by the user, non-essential animations such as loading shimmers and transitions are disabled.
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
          <Link to="/accessibility">Accessibility</Link>
        </div>
      </footer>
    </main>
  );
}
