import { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  EyeOff,
  FileCheck,
  Send,
  Info,
  ShieldCheck,
  History,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import {
  submitManualReview,
  getManualReviewHistory,
  getManualReviewComparison,
  getManualReviewMetrics,
  getBlindEvidence,
} from "../lib/api";
import usePageMetadata from "../hooks/usePageMetadata";
import BrandBlock from "../components/BrandBlock";

const EXACT_SIX_ENTITIES = [
  "Delta Rail Systems",
  "Indus Financial Services",
  "Continental Banking Corp",
  "Fortis Defense Systems",
  "Apex Power Grid Ltd",
  "Himalayan Healthcare Network",
];

// ---------------------------------------------------------------------------
// UI-form-value <-> backend-enum-value conversion. The form shows the
// human-readable labels below; the API boundary is the only place that
// translates them into the backend's ManualReviewCreate field names/values
// (supervisory_concern: bool, concern_type: snake_case, manual_priority:
// lowercase, manual_review_recommended: bool, evidence_sufficient: bool).
// ---------------------------------------------------------------------------

const CONCERN_TYPE_OPTIONS = [
  "Execution weakness",
  "Missing evidence",
  "Unusual behaviour",
  "Other",
  "No concern",
];

const CONCERN_TYPE_UI_TO_API = {
  "Execution weakness": "execution_weakness",
  "Missing evidence": "missing_evidence",
  "Unusual behaviour": "unusual_behaviour",
  "Other": "other",
  "No concern": "no_concern",
};

const CONCERN_TYPE_API_TO_UI = Object.fromEntries(
  Object.entries(CONCERN_TYPE_UI_TO_API).map(([ui, api]) => [api, ui])
);

const PRIORITY_OPTIONS = ["Critical", "High", "Medium", "Low"];

function priorityUiToApi(ui) {
  return (ui || "").toLowerCase();
}

function priorityApiToUi(api) {
  if (!api) return "";
  return api.charAt(0).toUpperCase() + api.slice(1);
}

function yesNoUiToBool(ui) {
  return ui === "Yes";
}

function boolToYesNoUi(value) {
  return value ? "Yes" : "No";
}

const EMPTY_FORM = {
  q1_concern: "",
  q2_concern_type: "",
  q3_priority: "",
  q4_recommended: "",
  q5_sufficient: "",
  q6_rationale: "",
};

/** UI-readable field values for one persisted ManualReviewOut row — used
 * only to display a *past* review's own judgement in the history expander.
 * Never used to prefill the live assessment form: a fresh blind review must
 * start empty, otherwise the reviewer is anchored by their own past answer. */
function formFromReview(review) {
  return {
    q1_concern: boolToYesNoUi(review.supervisory_concern),
    q2_concern_type: CONCERN_TYPE_API_TO_UI[review.concern_type] || review.concern_type,
    q3_priority: priorityApiToUi(review.manual_priority),
    q4_recommended: boolToYesNoUi(review.manual_review_recommended),
    q5_sufficient: boolToYesNoUi(review.evidence_sufficient),
    q6_rationale: review.rationale,
  };
}

/** Build the POST /api/manual-review body from the UI form — flat top-level
 * fields in the backend's own vocabulary, no `answers` wrapper, no
 * client-generated timestamp (the backend sets created_at itself). */
function formToPayload(entityName, formData) {
  return {
    entity_name: entityName,
    reviewer_id: "SUPERVISOR-EXP-01",
    supervisory_concern: yesNoUiToBool(formData.q1_concern),
    concern_type: CONCERN_TYPE_UI_TO_API[formData.q2_concern_type],
    manual_priority: priorityUiToApi(formData.q3_priority),
    manual_review_recommended: yesNoUiToBool(formData.q4_recommended),
    evidence_sufficient: yesNoUiToBool(formData.q5_sufficient),
    rationale: formData.q6_rationale.trim(),
  };
}

function formatSeconds(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  return `${(seconds / 60).toFixed(1)}m`;
}

function formatTimestamp(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

// ---------------------------------------------------------------------------
// Small aggregate-metrics panel — GET /api/manual-review/metrics.
// Shown on the entity-selection screen: it aggregates across every review
// already submitted, so surfacing it there doesn't leak anything about an
// entity not yet reviewed.
// ---------------------------------------------------------------------------

function ValidationMetricsPanel() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    getManualReviewMetrics()
      .then((data) => {
        if (!cancelled) setMetrics(data);
      })
      .catch((err) => {
        console.error("Failed to load manual-review metrics:", err);
        if (!cancelled) setError("Metrics unavailable.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const pct = (rate) => (rate === null || rate === undefined ? "—" : `${Math.round(rate * 100)}%`);

  return (
    <section
      className="ranking-panel"
      style={{ marginBottom: "28px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "6px", padding: "24px" }}
    >
      <div className="panel-header" style={{ marginBottom: "16px" }}>
        <div>
          <div className="panel-label">VALIDATION METRICS</div>
          <h2 style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <ShieldCheck size={20} color="var(--accent)" />
            Manual-vs-VEIL Agreement
          </h2>
          <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--muted)" }}>
            Aggregated across every manual review submitted so far, compared against VEIL&apos;s output at query time.
          </p>
        </div>
      </div>

      {error && <p style={{ fontSize: "13px", color: "var(--muted)" }}>{error}</p>}

      {!error && !metrics && (
        <div className="skeleton skeleton-card" style={{ height: "70px" }} />
      )}

      {!error && metrics && metrics.total_reviews === 0 && (
        <p style={{ fontSize: "13px", color: "var(--muted)", margin: 0 }}>
          No manual reviews have been submitted yet — metrics will appear here once at least one review exists.
        </p>
      )}

      {!error && metrics && metrics.total_reviews > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "14px" }}>
          <div style={{ background: "var(--surface-2)", padding: "14px 16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Total Reviews</span>
            <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--text)", marginTop: "4px" }}>{metrics.total_reviews}</div>
            <small style={{ fontSize: "11px", color: "var(--muted)" }}>{metrics.comparable_reviews} comparable to current dataset</small>
          </div>
          <div style={{ background: "var(--surface-2)", padding: "14px 16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Concern Agreement</span>
            <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--text)", marginTop: "4px" }}>{pct(metrics.concern_agreement_rate)}</div>
            <small style={{ fontSize: "11px", color: "var(--muted)" }}>{metrics.concern_agreement_count} of {metrics.comparable_reviews}</small>
          </div>
          <div style={{ background: "var(--surface-2)", padding: "14px 16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Priority Agreement</span>
            <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--text)", marginTop: "4px" }}>{pct(metrics.priority_agreement_rate)}</div>
            <small style={{ fontSize: "11px", color: "var(--muted)" }}>{metrics.priority_agreement_count} of {metrics.comparable_reviews}</small>
          </div>
          <div style={{ background: "var(--surface-2)", padding: "14px 16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
            <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Recommendation Agreement</span>
            <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--text)", marginTop: "4px" }}>{pct(metrics.recommendation_agreement_rate)}</div>
            <small style={{ fontSize: "11px", color: "var(--muted)" }}>{metrics.recommendation_agreement_count} of {metrics.comparable_reviews}</small>
          </div>
          <div style={{ background: "var(--surface-2)", padding: "14px 16px", borderRadius: "4px", border: "1px solid var(--accent)" }}>
            <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Overall Agreement</span>
            <div style={{ fontSize: "22px", fontWeight: 700, color: "var(--accent)", marginTop: "4px" }}>{pct(metrics.overall_agreement_rate)}</div>
            <small style={{ fontSize: "11px", color: "var(--muted)" }}>{metrics.overall_agreement_count} of {metrics.comparable_reviews}</small>
          </div>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Prior-reviews notice + expander. Shows this reviewer's OWN past answers
// and rationale for this entity — never a VEIL conclusion, and never the
// backend comparison (that stays gated behind a *new* submission). A row
// here is exactly the same shape returned by GET /manual-review/{entity},
// which has no risk_score/risk_band/primary_driver/findings field at all.
// ---------------------------------------------------------------------------

function PriorReviewsPanel({ reviews }) {
  const [expanded, setExpanded] = useState(false);

  if (!reviews || reviews.length === 0) return null;

  return (
    <div
      style={{
        background: "rgba(255, 255, 255, 0.03)",
        border: "1px solid var(--line)",
        borderRadius: "6px",
        padding: "16px 20px",
        marginBottom: "24px",
      }}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        style={{
          background: "transparent",
          border: "none",
          padding: 0,
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          cursor: "pointer",
          color: "var(--text)",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: "10px", fontSize: "13px", fontWeight: 600 }}>
          <History size={16} color="var(--muted)" />
          {reviews.length} previous {reviews.length === 1 ? "review" : "reviews"} recorded for this entity
        </span>
        {expanded ? <ChevronUp size={16} color="var(--muted)" /> : <ChevronDown size={16} color="var(--muted)" />}
      </button>

      {expanded && (
        <div style={{ marginTop: "16px", display: "flex", flexDirection: "column", gap: "14px" }}>
          {reviews.map((review) => {
            const ui = formFromReview(review);
            return (
              <div
                key={review.id}
                style={{
                  background: "var(--surface-2)",
                  border: "1px solid var(--line)",
                  borderRadius: "4px",
                  padding: "14px 16px",
                  fontSize: "12px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "8px", marginBottom: "8px" }}>
                  <span style={{ color: "var(--muted)", fontFamily: "monospace" }}>{formatTimestamp(review.created_at)}</span>
                  <span style={{ color: "var(--muted)" }}>Reviewer: {review.reviewer_id || "—"}</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "6px 16px", color: "var(--text)" }}>
                  <span>Concern: <strong>{ui.q1_concern}</strong></span>
                  <span>Type: <strong>{ui.q2_concern_type}</strong></span>
                  <span>Priority: <strong>{ui.q3_priority}</strong></span>
                  <span>Recommended: <strong>{ui.q4_recommended}</strong></span>
                  <span>Evidence sufficient: <strong>{ui.q5_sufficient}</strong></span>
                </div>
                <p style={{ margin: "8px 0 0", color: "var(--muted)", lineHeight: 1.5, whiteSpace: "pre-wrap" }}>{ui.q6_rationale}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ManualReviewPage() {
  usePageMetadata({
    title: "Manual Expert Review | VEIL",
    description: "Human-in-the-loop independent operational review and blind assessment.",
    path: "/manual-review",
  });

  const { entityName: paramEntityName } = useParams();
  const navigate = useNavigate();

  const rawDecoded = paramEntityName ? decodeURIComponent(paramEntityName) : null;
  const selectedEntity = EXACT_SIX_ENTITIES.includes(rawDecoded) ? rawDecoded : null;

  const [loadingEntity, setLoadingEntity] = useState(false);
  const [evidence, setEvidence] = useState(null);
  const [evidenceError, setEvidenceError] = useState(null);

  // Reviews that existed *before* this page load — shown read-only in
  // PriorReviewsPanel, never used to prefill the live form and never the
  // trigger for showing a comparison.
  const [priorReviews, setPriorReviews] = useState([]);
  const [historyError, setHistoryError] = useState(null);

  // The review created by THIS session's submission, if any. Its presence
  // (not `priorReviews.length > 0`) is what gates the comparison view —
  // selecting an already-reviewed entity must always land back in the blind
  // phase, never resume showing a previous comparison.
  const [justSubmittedReview, setJustSubmittedReview] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [comparisonError, setComparisonError] = useState(null);

  const [formData, setFormData] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // Blind phase only: fetch the blind dossier and this entity's own review
  // history (for the "N previous reviews" notice — their own past answers,
  // never VEIL output). Deliberately never calls getEntityDetails or
  // getManualReviewComparison here — those must not run until a *new*
  // review is submitted in this session, even if older reviews already
  // exist for this entity.
  useEffect(() => {
    if (!selectedEntity) return;

    let isCancelled = false;

    const loadData = async () => {
      setLoadingEntity(true);
      setFormError(null);
      setSubmitError(null);
      setEvidence(null);
      setEvidenceError(null);
      setPriorReviews([]);
      setHistoryError(null);
      setJustSubmittedReview(null);
      setComparison(null);
      setComparisonError(null);
      setFormData(EMPTY_FORM);

      try {
        const historyResult = await getManualReviewHistory(selectedEntity);
        if (!isCancelled) setPriorReviews(historyResult);
      } catch (err) {
        console.error("Failed to load review history:", err);
        if (!isCancelled) setHistoryError("Failed to load prior review history for this entity.");
      }

      try {
        const evidenceResult = await getBlindEvidence(selectedEntity);
        if (!isCancelled) setEvidence(evidenceResult);
      } catch (err) {
        console.error("Failed to load blind evidence:", err);
        if (!isCancelled) {
          setEvidenceError(
            err.response?.data?.detail || "Failed to load the blind evidence dossier for this entity."
          );
        }
      }

      if (!isCancelled) setLoadingEntity(false);
    };

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [selectedEntity]);

  const handleSelectEntity = (entity) => {
    navigate(`/manual-review/${encodeURIComponent(entity)}`);
  };

  const handleBackToSelection = () => {
    navigate("/manual-review");
  };

  const handleFormChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    if (formError) setFormError(null);
  };

  const validateForm = () => {
    if (!formData.q1_concern) return "Question 1: Supervisory concern present is required.";
    if (!formData.q2_concern_type) return "Question 2: Concern type is required.";
    if (!formData.q3_priority) return "Question 3: Manual reviewer priority is required.";
    if (!formData.q4_recommended) return "Question 4: Manual review recommended is required.";
    if (!formData.q5_sufficient) return "Question 5: Evidence sufficient is required.";
    if (!formData.q6_rationale || !formData.q6_rationale.trim()) {
      return "Question 6: Reviewer rationale explanation is required.";
    }
    return null;
  };

  const handleSubmitReview = async (e) => {
    e.preventDefault();
    const error = validateForm();
    if (error) {
      setFormError(error);
      return;
    }

    setSubmitting(true);
    setFormError(null);
    setSubmitError(null);

    const payload = formToPayload(selectedEntity, formData);

    try {
      const created = await submitManualReview(payload);
      setJustSubmittedReview(created);

      try {
        const comparisonResult = await getManualReviewComparison(selectedEntity);
        setComparison(comparisonResult);
      } catch (err) {
        console.error("Failed to load comparison after submission:", err);
        setComparisonError("Review saved, but the comparison could not be loaded.");
      }
    } catch (err) {
      console.error("Submission error:", err);
      const detail = err.response?.data?.detail;
      setSubmitError(
        typeof detail === "string"
          ? detail
          : "Failed to submit the review to the backend. Nothing was saved — please retry."
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="dashboard-shell">
      {/* NAVBAR */}
      <nav className="dashboard-nav">
        <BrandBlock />
        <div className="dashboard-nav-links">
          <Link to="/upload">ANALYZE</Link>
          <Link to="/dashboard">OVERVIEW</Link>
          <span className="active">MANUAL REVIEW</span>
          <Link to="/audit">AUDIT</Link>
        </div>
        <div className="dashboard-status">
          <span />
          AIR-GAPPED
        </div>
      </nav>

      <section className="dashboard-page">
        {/* HEADER */}
        <div className="dashboard-header" style={{ marginBottom: "32px" }}>
          <div>
            <div className="dashboard-eyebrow">03 / HUMAN-IN-THE-LOOP SUPERVISORY REVIEW</div>
            <h1>
              MANUAL
              <br />
              <span>EXPERT REVIEW.</span>
            </h1>
            <p style={{ maxWidth: "680px", color: "var(--muted)", fontSize: "15px", marginTop: "12px", lineHeight: "1.5" }}>
              Independent human supervisory evaluation layer. Conducts blind assessments of operational telemetry before comparing supervisor findings against VEIL analytical conclusions.
            </p>
          </div>
          <div className="dataset-info">
            <span>SUPERVISOR OPERATOR</span>
            <strong>EXPERT AUDIT CONSOLE</strong>
            <small>ID: SUP-EXPERT-01 · Strict Blind Protocol</small>
          </div>
        </div>

        {/* ========================================================
            VIEW 1: ENTITY SELECTION SCREEN
            ======================================================== */}
        {!selectedEntity && (
          <div>
            <ValidationMetricsPanel />

            <div className="panel-header" style={{ marginBottom: "16px" }}>
              <div>
                <div className="panel-label">TARGET SELECTION</div>
                <h2>Supervisory Review Entities</h2>
                <p style={{ margin: "4px 0 0", fontSize: "14px", color: "var(--muted)" }}>
                  Select an organization from the designated supervisory evaluation cohort to begin blind dossier review.
                </p>
              </div>
              <span className="panel-meta">6 EVALUATION ENTITIES</span>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))", gap: "20px", marginTop: "20px" }}>
              {EXACT_SIX_ENTITIES.map((name, idx) => (
                <div
                  key={name}
                  style={{
                    background: "var(--surface)",
                    border: "1px solid var(--line)",
                    borderRadius: "6px",
                    padding: "24px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
                      <span style={{ fontSize: "11px", fontFamily: "monospace", color: "var(--muted)", fontWeight: 700 }}>
                        {(idx + 1).toString().padStart(2, "0")} / 06
                      </span>
                    </div>
                    <h3 style={{ fontSize: "18px", margin: "0 0 8px", color: "var(--text)" }}>{name}</h3>
                    <p style={{ fontSize: "13px", color: "var(--muted)", margin: "0 0 16px", lineHeight: "1.4" }}>
                      Operational evidence dossier available for blind review. Analytical scores remain hidden until a review is submitted.
                    </p>
                  </div>

                  <button
                    onClick={() => handleSelectEntity(name)}
                    style={{
                      padding: "10px 16px",
                      background: "rgba(86, 199, 255, 0.12)",
                      border: "1px solid var(--accent)",
                      color: "var(--accent)",
                      borderRadius: "4px",
                      fontWeight: 600,
                      fontSize: "13px",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "8px",
                      marginTop: "16px",
                    }}
                  >
                    <FileCheck size={15} />
                    <span>Open Review Dossier</span>
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ========================================================
            VIEW 2: WORKFLOW SCREEN
            ======================================================== */}
        {selectedEntity && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px", flexWrap: "wrap", gap: "12px" }}>
              <button
                onClick={handleBackToSelection}
                style={{ background: "transparent", border: "none", color: "var(--accent)", fontSize: "13px", fontWeight: 600, cursor: "pointer", padding: 0 }}
              >
                ← Return to Entity Selection
              </button>
              <span style={{ fontSize: "13px", color: "var(--muted)" }}>
                Target: <strong style={{ color: "var(--text)" }}>{selectedEntity}</strong>
              </span>
            </div>

            {loadingEntity && (
              <div style={{ padding: "40px", textAlign: "center" }}>
                <div className="skeleton skeleton-card" style={{ height: "120px", marginBottom: "20px" }} />
                <div className="skeleton skeleton-card" style={{ height: "240px" }} />
              </div>
            )}

            {!loadingEntity && (
              <div>
                {!justSubmittedReview && (
                  <div
                    style={{
                      background: "rgba(86, 199, 255, 0.05)",
                      border: "1px solid rgba(86, 199, 255, 0.3)",
                      borderRadius: "6px",
                      padding: "20px 24px",
                      marginBottom: "28px",
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "16px",
                    }}
                  >
                    <EyeOff size={24} color="var(--accent)" style={{ flexShrink: 0, marginTop: "2px" }} />
                    <div>
                      <strong style={{ fontSize: "14px", letterSpacing: "0.08em", color: "var(--accent)", textTransform: "uppercase" }}>
                        BLIND REVIEW IN EFFECT
                      </strong>
                      <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--text)", lineHeight: "1.5" }}>
                        VEIL analytical conclusions (risk score, risk band, primary driver, and detector findings) are never
                        requested by this page until after you submit an assessment in this session — even if this entity
                        was reviewed before.
                      </p>
                    </div>
                  </div>
                )}

                {historyError && (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--amber)", fontSize: "13px", marginBottom: "16px" }}>
                    <AlertTriangle size={16} />
                    <span>{historyError}</span>
                  </div>
                )}

                {!justSubmittedReview && <PriorReviewsPanel reviews={priorReviews} />}

                {/* ----------------------------------------------------
                    1. BLIND EVIDENCE DOSSIER
                    ---------------------------------------------------- */}
                <section
                  className="ranking-panel"
                  style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "6px", padding: "24px", marginBottom: "30px" }}
                >
                  <div className="panel-header" style={{ marginBottom: "20px" }}>
                    <div>
                      <div className="panel-label">SECTION 01 / EVIDENCE DOSSIER</div>
                      <h2>Operational Telemetry Evidence</h2>
                      <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--muted)" }}>
                        Factual descriptive metrics and raw alert records for {selectedEntity}. No peer comparison of any kind
                        is included here by design.
                      </p>
                    </div>
                    <span className="panel-meta">RAW TELEMETRY</span>
                  </div>

                  {evidenceError && (
                    <div className="error-state" style={{ minHeight: "120px", padding: "24px" }}>
                      <AlertTriangle size={22} color="var(--amber)" />
                      <h3 style={{ fontSize: "14px", margin: "8px 0 4px" }}>Evidence Unavailable</h3>
                      <p style={{ fontSize: "12px", color: "var(--muted)" }}>{evidenceError}</p>
                    </div>
                  )}

                  {!evidenceError && !evidence && (
                    <div className="skeleton skeleton-card" style={{ height: "160px" }} />
                  )}

                  {!evidenceError && evidence && (
                    <>
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
                          gap: "16px",
                          marginBottom: "20px",
                        }}
                      >
                        <div style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
                          <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                            Total Alerts
                          </span>
                          <div style={{ fontSize: "24px", fontWeight: 700, margin: "8px 0 4px", color: "var(--text)" }}>
                            {evidence.aggregates.total_alerts}
                          </div>
                          <small style={{ fontSize: "11px", color: "var(--muted)" }}>
                            {evidence.aggregates.open_alerts} open · {evidence.aggregates.closed_alerts} closed
                          </small>
                        </div>

                        <div style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
                          <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                            Avg Closure Duration
                          </span>
                          <div style={{ fontSize: "24px", fontWeight: 700, margin: "8px 0 4px", color: "var(--text)" }}>
                            {evidence.aggregates.avg_closure_seconds != null
                              ? formatSeconds(evidence.aggregates.avg_closure_seconds)
                              : "—"}
                          </div>
                          <small style={{ fontSize: "11px", color: "var(--muted)" }}>this entity only</small>
                        </div>

                        <div style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
                          <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                            Escalated Rate
                          </span>
                          <div style={{ fontSize: "24px", fontWeight: 700, margin: "8px 0 4px", color: "var(--text)" }}>
                            {(evidence.aggregates.escalated_rate * 100).toFixed(1)}%
                          </div>
                          <small style={{ fontSize: "11px", color: "var(--muted)" }}>
                            {evidence.aggregates.escalated_count} of {evidence.aggregates.total_alerts}
                          </small>
                        </div>

                        <div style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
                          <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                            Avg Note Length
                          </span>
                          <div style={{ fontSize: "24px", fontWeight: 700, margin: "8px 0 4px", color: "var(--text)" }}>
                            {Math.round(evidence.aggregates.avg_investigation_note_length)} chars
                          </div>
                          <small style={{ fontSize: "11px", color: "var(--muted)" }}>this entity only</small>
                        </div>
                      </div>

                      {/* Severity / asset-type breakdown */}
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: "16px", marginBottom: "24px" }}>
                        <div style={{ background: "var(--surface-2)", padding: "14px 16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
                          <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Severity Distribution</span>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "8px" }}>
                            {Object.entries(evidence.aggregates.severity_distribution).map(([sev, count]) => (
                              <span key={sev} style={{ fontSize: "12px", color: "var(--text)", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "3px", padding: "3px 8px" }}>
                                {sev}: {count}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div style={{ background: "var(--surface-2)", padding: "14px 16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
                          <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase" }}>Asset Type Distribution</span>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "8px" }}>
                            {Object.entries(evidence.aggregates.asset_type_distribution).map(([type, count]) => (
                              <span key={type} style={{ fontSize: "12px", color: "var(--text)", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "3px", padding: "3px 8px" }}>
                                {type}: {count}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>

                      {/* The actual evidence a supervisor reviews: every alert record. */}
                      <div style={{ overflowX: "auto", width: "100%", maxHeight: "420px", overflowY: "auto", border: "1px solid var(--line)", borderRadius: "4px" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px", textAlign: "left", minWidth: "760px" }}>
                          <thead>
                            <tr
                              style={{
                                borderBottom: "1px solid var(--line)",
                                color: "var(--muted)",
                                fontSize: "10px",
                                letterSpacing: "0.08em",
                                textTransform: "uppercase",
                                position: "sticky",
                                top: 0,
                                background: "var(--surface)",
                              }}
                            >
                              <th style={{ padding: "10px 14px" }}>Alert ID</th>
                              <th style={{ padding: "10px 14px" }}>Severity</th>
                              <th style={{ padding: "10px 14px" }}>Asset Type</th>
                              <th style={{ padding: "10px 14px" }}>Created</th>
                              <th style={{ padding: "10px 14px" }}>Closed</th>
                              <th style={{ padding: "10px 14px" }}>Duration</th>
                              <th style={{ padding: "10px 14px" }}>Escalated</th>
                              <th style={{ padding: "10px 14px" }}>Investigation Notes</th>
                            </tr>
                          </thead>
                          <tbody>
                            {evidence.alerts.map((alert) => (
                              <tr key={alert.alert_id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                                <td style={{ padding: "10px 14px", fontFamily: "monospace", color: "var(--text)" }}>{alert.alert_id}</td>
                                <td style={{ padding: "10px 14px", color: "var(--text)", textTransform: "capitalize" }}>{alert.severity}</td>
                                <td style={{ padding: "10px 14px", color: "var(--muted)" }}>{alert.asset_type}</td>
                                <td style={{ padding: "10px 14px", color: "var(--muted)" }}>{formatTimestamp(alert.created_time)}</td>
                                <td style={{ padding: "10px 14px", color: "var(--muted)" }}>{formatTimestamp(alert.closed_time)}</td>
                                <td style={{ padding: "10px 14px", color: "var(--muted)" }}>{formatSeconds(alert.closure_duration_seconds)}</td>
                                <td style={{ padding: "10px 14px" }}>
                                  <span style={{ color: alert.escalated ? "var(--green)" : "var(--muted)" }}>
                                    {alert.escalated ? "Yes" : "No"}
                                  </span>
                                </td>
                                <td style={{ padding: "10px 14px", color: "var(--muted)", maxWidth: "320px" }}>
                                  {alert.investigation_notes || "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </section>

                {/* ----------------------------------------------------
                    2. REVIEWER ASSESSMENT FORM — always shown for a fresh
                    blind review, regardless of prior review history. Only
                    disappears once THIS session has submitted a new review.
                    Always starts empty (EMPTY_FORM) — never prefilled from
                    a past review, so the reviewer isn't anchored.
                    ---------------------------------------------------- */}
                {!justSubmittedReview && (
                  <form
                    onSubmit={handleSubmitReview}
                    className="ranking-panel"
                    style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "6px", padding: "28px", marginBottom: "30px" }}
                  >
                    <div className="panel-header" style={{ marginBottom: "24px" }}>
                      <div>
                        <div className="panel-label">SECTION 02 / EXPERT ASSESSMENT</div>
                        <h2>Independent Human Evaluation</h2>
                        <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--muted)" }}>
                          Complete all six assessment questions based solely on the operational telemetry presented above.
                        </p>
                      </div>
                      <span className="panel-meta">6 REQUIRED FIELDS</span>
                    </div>

                    {formError && (
                      <div style={{ background: "rgba(239, 107, 114, 0.12)", border: "1px solid rgba(239, 107, 114, 0.3)", borderRadius: "4px", padding: "12px 16px", marginBottom: "20px", color: "var(--red)", fontSize: "13px", display: "flex", alignItems: "center", gap: "10px" }}>
                        <AlertCircle size={16} />
                        <span>{formError}</span>
                      </div>
                    )}

                    {submitError && (
                      <div style={{ background: "rgba(239, 107, 114, 0.12)", border: "1px solid rgba(239, 107, 114, 0.3)", borderRadius: "4px", padding: "12px 16px", marginBottom: "20px", color: "var(--red)", fontSize: "13px", display: "flex", alignItems: "center", gap: "10px" }}>
                        <AlertCircle size={16} />
                        <span>{submitError}</span>
                      </div>
                    )}

                    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
                      {/* Q1 */}
                      <div>
                        <label style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "var(--text)", marginBottom: "10px" }}>
                          1. Supervisory concern present? <span style={{ color: "var(--red)" }}>*</span>
                        </label>
                        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                          {["Yes", "No"].map((opt) => (
                            <button
                              type="button"
                              key={opt}
                              onClick={() => handleFormChange("q1_concern", opt)}
                              style={{
                                padding: "8px 20px",
                                borderRadius: "4px",
                                fontSize: "13px",
                                fontWeight: 600,
                                cursor: "pointer",
                                background: formData.q1_concern === opt ? "rgba(86, 199, 255, 0.18)" : "var(--surface-2)",
                                border: `1px solid ${formData.q1_concern === opt ? "var(--accent)" : "var(--line)"}`,
                                color: formData.q1_concern === opt ? "var(--accent)" : "var(--text)",
                              }}
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Q2 */}
                      <div>
                        <label style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "var(--text)", marginBottom: "10px" }}>
                          2. Concern type <span style={{ color: "var(--red)" }}>*</span>
                        </label>
                        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                          {CONCERN_TYPE_OPTIONS.map((opt) => (
                            <button
                              type="button"
                              key={opt}
                              onClick={() => handleFormChange("q2_concern_type", opt)}
                              style={{
                                padding: "8px 16px",
                                borderRadius: "4px",
                                fontSize: "13px",
                                fontWeight: 600,
                                cursor: "pointer",
                                background: formData.q2_concern_type === opt ? "rgba(86, 199, 255, 0.18)" : "var(--surface-2)",
                                border: `1px solid ${formData.q2_concern_type === opt ? "var(--accent)" : "var(--line)"}`,
                                color: formData.q2_concern_type === opt ? "var(--accent)" : "var(--text)",
                              }}
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Q3 */}
                      <div>
                        <label style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "var(--text)", marginBottom: "10px" }}>
                          3. Manual reviewer priority <span style={{ color: "var(--red)" }}>*</span>
                        </label>
                        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                          {PRIORITY_OPTIONS.map((opt) => {
                            const isSelected = formData.q3_priority === opt;
                            const colorMap = { Critical: "var(--red)", High: "var(--amber)", Medium: "var(--accent)", Low: "var(--green)" };
                            return (
                              <button
                                type="button"
                                key={opt}
                                onClick={() => handleFormChange("q3_priority", opt)}
                                style={{
                                  padding: "8px 18px",
                                  borderRadius: "4px",
                                  fontSize: "13px",
                                  fontWeight: 700,
                                  cursor: "pointer",
                                  background: isSelected ? "rgba(255, 255, 255, 0.08)" : "var(--surface-2)",
                                  border: `1px solid ${isSelected ? colorMap[opt] : "var(--line)"}`,
                                  color: isSelected ? colorMap[opt] : "var(--text)",
                                }}
                              >
                                {opt}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* Q4 */}
                      <div>
                        <label style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "var(--text)", marginBottom: "10px" }}>
                          4. Manual review recommended? <span style={{ color: "var(--red)" }}>*</span>
                        </label>
                        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                          {["Yes", "No"].map((opt) => (
                            <button
                              type="button"
                              key={opt}
                              onClick={() => handleFormChange("q4_recommended", opt)}
                              style={{
                                padding: "8px 20px",
                                borderRadius: "4px",
                                fontSize: "13px",
                                fontWeight: 600,
                                cursor: "pointer",
                                background: formData.q4_recommended === opt ? "rgba(86, 199, 255, 0.18)" : "var(--surface-2)",
                                border: `1px solid ${formData.q4_recommended === opt ? "var(--accent)" : "var(--line)"}`,
                                color: formData.q4_recommended === opt ? "var(--accent)" : "var(--text)",
                              }}
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Q5 */}
                      <div>
                        <label style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "var(--text)", marginBottom: "10px" }}>
                          5. Evidence sufficient? <span style={{ color: "var(--red)" }}>*</span>
                        </label>
                        <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
                          {["Yes", "No"].map((opt) => (
                            <button
                              type="button"
                              key={opt}
                              onClick={() => handleFormChange("q5_sufficient", opt)}
                              style={{
                                padding: "8px 20px",
                                borderRadius: "4px",
                                fontSize: "13px",
                                fontWeight: 600,
                                cursor: "pointer",
                                background: formData.q5_sufficient === opt ? "rgba(86, 199, 255, 0.18)" : "var(--surface-2)",
                                border: `1px solid ${formData.q5_sufficient === opt ? "var(--accent)" : "var(--line)"}`,
                                color: formData.q5_sufficient === opt ? "var(--accent)" : "var(--text)",
                              }}
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Q6 */}
                      <div>
                        <label style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "var(--text)", marginBottom: "8px" }}>
                          6. Reviewer rationale <span style={{ color: "var(--red)" }}>*</span>
                        </label>
                        <p style={{ margin: "0 0 10px", fontSize: "12px", color: "var(--muted)" }}>
                          Detailed supervisory narrative explaining your determination based solely on the observed operational records.
                        </p>
                        <textarea
                          rows={4}
                          value={formData.q6_rationale}
                          onChange={(e) => handleFormChange("q6_rationale", e.target.value)}
                          placeholder="Provide supervisory rationale justifying concern presence, priority level, and review recommendation..."
                          style={{
                            width: "100%",
                            background: "var(--surface-2)",
                            border: "1px solid var(--line)",
                            borderRadius: "4px",
                            padding: "12px 14px",
                            color: "var(--text)",
                            fontSize: "13px",
                            lineHeight: "1.5",
                            resize: "vertical",
                            fontFamily: "inherit",
                          }}
                        />
                      </div>
                    </div>

                    <div style={{ marginTop: "32px", display: "flex", justifyContent: "flex-end" }}>
                      <button
                        type="submit"
                        disabled={submitting}
                        style={{
                          padding: "12px 28px",
                          background: submitting ? "var(--surface-2)" : "var(--accent)",
                          color: submitting ? "var(--muted)" : "#0b0d10",
                          border: "none",
                          borderRadius: "4px",
                          fontSize: "14px",
                          fontWeight: 700,
                          letterSpacing: "0.04em",
                          cursor: submitting ? "not-allowed" : "pointer",
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <Send size={15} />
                        <span>{submitting ? "Submitting Assessment..." : "Submit Supervisory Assessment"}</span>
                      </button>
                    </div>
                  </form>
                )}

                {/* ----------------------------------------------------
                    3. POST-SUBMISSION CONFIRMATION & COMPARISON — only
                    once THIS session has actually submitted a new review.
                    ---------------------------------------------------- */}
                {justSubmittedReview && (
                  <div>
                    <div
                      style={{
                        background: "rgba(87, 213, 140, 0.08)",
                        border: "1px solid rgba(87, 213, 140, 0.3)",
                        borderRadius: "6px",
                        padding: "20px 24px",
                        marginBottom: "30px",
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "16px",
                      }}
                    >
                      <CheckCircle2 size={24} color="var(--green)" style={{ flexShrink: 0, marginTop: "2px" }} />
                      <div style={{ flex: 1 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px", marginBottom: "4px" }}>
                          <strong style={{ fontSize: "15px", color: "var(--green)" }}>Supervisory Assessment Recorded</strong>
                          <span style={{ fontSize: "11px", color: "var(--muted)", fontFamily: "monospace" }}>
                            {formatTimestamp(justSubmittedReview.created_at)}
                          </span>
                        </div>
                        <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--text)" }}>
                          Blind review complete. VEIL&apos;s conclusions are now revealed below for comparison.
                        </p>
                      </div>
                    </div>

                    <section
                      className="ranking-panel"
                      style={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: "6px", padding: "28px", marginBottom: "30px" }}
                    >
                      <div className="panel-header" style={{ marginBottom: "24px" }}>
                        <div>
                          <div className="panel-label">SECTION 03 / COMPARISON ANALYSIS</div>
                          <h2>Manual Review vs VEIL Output</h2>
                          <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--muted)" }}>
                            Computed by the backend from the review just submitted — not re-derived here.
                          </p>
                        </div>
                        <span className="panel-meta">VERIFICATION MATRIX</span>
                      </div>

                      {comparisonError && (
                        <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--amber)", fontSize: "13px", marginBottom: "16px" }}>
                          <AlertTriangle size={16} />
                          <span>{comparisonError}</span>
                        </div>
                      )}

                      {!comparisonError && !comparison && (
                        <div className="skeleton skeleton-card" style={{ height: "160px" }} />
                      )}

                      {!comparisonError && comparison && !comparison.available && (
                        <div className="empty-state" style={{ minHeight: "120px", padding: "24px" }}>
                          <Info size={20} color="var(--muted)" />
                          <p style={{ fontSize: "13px", color: "var(--muted)", margin: "8px 0 0" }}>{comparison.reason}</p>
                        </div>
                      )}

                      {!comparisonError && comparison && comparison.available && (
                        <>
                          <div
                            style={{
                              background: "var(--surface-2)",
                              border: "1px solid var(--line)",
                              borderRadius: "6px",
                              padding: "16px 20px",
                              marginBottom: "24px",
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              flexWrap: "wrap",
                              gap: "12px",
                            }}
                          >
                            <div>
                              <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                                Overall Agreement
                              </span>
                              <div style={{ fontSize: "18px", fontWeight: 700, color: comparison.overall_agreement ? "var(--green)" : "var(--amber)", marginTop: "4px" }}>
                                {comparison.overall_agreement ? "Concordant" : "Discrepant"}
                              </div>
                            </div>
                            <Link
                              to={`/entities/${encodeURIComponent(selectedEntity)}`}
                              style={{ display: "inline-flex", alignItems: "center", gap: "6px", fontSize: "12px", padding: "6px 12px", borderRadius: "4px", background: "rgba(86, 199, 255, 0.1)", border: "1px solid var(--accent)", color: "var(--accent)", textDecoration: "none", fontWeight: 600 }}
                            >
                              <span>Inspect Full VEIL Dossier</span>
                            </Link>
                          </div>

                          <div style={{ overflowX: "auto", width: "100%" }}>
                            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px", textAlign: "left", minWidth: "620px" }}>
                              <thead>
                                <tr style={{ borderBottom: "1px solid var(--line)", color: "var(--muted)", fontSize: "11px", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                                  <th style={{ padding: "12px 16px", width: "200px" }}>Dimension</th>
                                  <th style={{ padding: "12px 16px" }}>Manual Review</th>
                                  <th style={{ padding: "12px 16px" }}>VEIL Output</th>
                                  <th style={{ padding: "12px 16px", width: "130px" }}>Status</th>
                                </tr>
                              </thead>
                              <tbody>
                                <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                                  <td style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text)" }}>Concern Present</td>
                                  <td style={{ padding: "14px 16px" }}>{comparison.manual_concern ? "Yes" : "No"}</td>
                                  <td style={{ padding: "14px 16px" }}>{comparison.veil_concern ? "Yes" : "No"}</td>
                                  <td style={{ padding: "14px 16px" }}>
                                    <span style={{ color: comparison.concern_agrees ? "var(--green)" : "var(--amber)", fontWeight: 600, fontSize: "12px" }}>
                                      {comparison.concern_agrees ? "Agreement" : "Discrepancy"}
                                    </span>
                                  </td>
                                </tr>
                                <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                                  <td style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text)" }}>Priority / Risk Band</td>
                                  <td style={{ padding: "14px 16px", textTransform: "capitalize" }}>{comparison.manual_priority}</td>
                                  <td style={{ padding: "14px 16px", textTransform: "capitalize" }}>{comparison.veil_risk_band}</td>
                                  <td style={{ padding: "14px 16px" }}>
                                    <span style={{ color: comparison.priority_agrees ? "var(--green)" : "var(--amber)", fontWeight: 600, fontSize: "12px" }}>
                                      {comparison.priority_agrees ? "Exact Match" : "Tier Mismatch"}
                                    </span>
                                  </td>
                                </tr>
                                <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                                  <td style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text)" }}>Review Recommended</td>
                                  <td style={{ padding: "14px 16px" }}>{comparison.manual_review_recommended ? "Yes" : "No"}</td>
                                  <td style={{ padding: "14px 16px" }}>{comparison.veil_prioritized ? "Yes" : "No"}</td>
                                  <td style={{ padding: "14px 16px" }}>
                                    <span style={{ color: comparison.recommendation_agrees ? "var(--green)" : "var(--amber)", fontWeight: 600, fontSize: "12px" }}>
                                      {comparison.recommendation_agrees ? "Agreement" : "Discrepancy"}
                                    </span>
                                  </td>
                                </tr>
                              </tbody>
                            </table>
                          </div>
                        </>
                      )}

                      <div style={{ marginTop: "20px" }}>
                        <div style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>
                          Recorded Human Rationale
                        </div>
                        <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.5", color: "var(--text)", whiteSpace: "pre-wrap" }}>
                          {justSubmittedReview.rationale || "No rationale recorded."}
                        </p>
                      </div>
                    </section>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
