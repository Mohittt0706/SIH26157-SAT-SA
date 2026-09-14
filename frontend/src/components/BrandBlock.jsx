import { Link } from "react-router-dom";
import veilLogo from "../assets/veil-logo.png";

/**
 * The VEIL brand block — logo mark, name, and subtitle — shown in every
 * page's navbar. Single source of truth for the logo: every page used to
 * carry its own copy of this markup, and five of them had silently drifted
 * to an older bordered-box "V" placeholder instead of the actual shield
 * logo used on the landing page. Import this everywhere instead of
 * re-pasting the markup, so a future logo change only happens in one place.
 */
export default function BrandBlock() {
  return (
    <Link to="/" className="brand" aria-label="VEIL Home">
      <div className="brand-mark">
        <img src={veilLogo} alt="VEIL logo" className="brand-logo" />
      </div>
      <div>
        <div className="brand-name">VEIL</div>
        <div className="brand-subtitle">Supervisory Intelligence for SOC Assessment</div>
      </div>
    </Link>
  );
}
