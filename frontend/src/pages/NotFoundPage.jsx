import { Link } from "react-router-dom";
import { ArrowLeft, ShieldAlert } from "lucide-react";
import usePageMetadata from "../hooks/usePageMetadata";
import BrandBlock from "../components/BrandBlock";

export default function NotFoundPage() {
  usePageMetadata({
    title: "Page Not Found | VEIL",
    description: "The requested page could not be found.",
  });

  return (
    <main className="dashboard-shell" style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <nav className="dashboard-nav">
        <BrandBlock />
        <div className="dashboard-status">
          <span />
          AIR-GAPPED
        </div>
      </nav>

      <section style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem', textAlign: 'center' }}>
        <div style={{ color: 'var(--accent)', marginBottom: '1.5rem' }}>
          <ShieldAlert size={48} strokeWidth={1} />
        </div>
        
        <div className="dashboard-eyebrow" style={{ marginBottom: '1rem' }}>
          404 / NOT FOUND
        </div>
        
        <h1 style={{ fontSize: '2.5rem', marginBottom: '1rem', lineHeight: 1.1 }}>
          SECURE AREA
          <br />
          <span style={{ color: 'var(--muted)' }}>NOT FOUND.</span>
        </h1>
        
        <p style={{ color: 'var(--muted)', maxWidth: '400px', marginBottom: '2rem', lineHeight: 1.6 }}>
          The requested operational view does not exist or has been restricted. Please return to the active dashboard.
        </p>
        
        <Link 
          to="/dashboard" 
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            background: 'var(--surface)',
            border: '1px solid var(--line)',
            padding: '12px 24px',
            color: 'var(--text)',
            fontSize: '12px',
            fontWeight: '700',
            letterSpacing: '0.12em',
            textDecoration: 'none',
            borderRadius: '4px',
            transition: 'background 0.2s',
          }}
          onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)'}
          onMouseOut={(e) => e.currentTarget.style.background = 'var(--surface)'}
        >
          <ArrowLeft size={16} />
          RETURN TO DASHBOARD
        </Link>
      </section>
    </main>
  );
}
