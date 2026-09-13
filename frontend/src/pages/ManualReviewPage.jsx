import { useEffect, useState } from "react";
import { Link, useParams, useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  AlertCircle,
  EyeOff,
  Eye,
  FileCheck,
  Send,
  RotateCcw,
  ExternalLink,
  Info,
} from "lucide-react";
import {
  getEntityDetails,
  submitManualReview,
  getManualReview,
  getBlindEvidence,
} from "../lib/api";
import usePageMetadata from "../hooks/usePageMetadata";

const EXACT_SIX_ENTITIES = [
  "Delta Rail Systems",
  "Indus Financial Services",
  "Continental Banking Corp",
  "Fortis Defense Systems",
  "Apex Power Grid Ltd",
  "Himalayan Healthcare Network",
];

const LOCAL_STORAGE_KEY = "veil_manual_reviews_v1";

function loadSavedReviews() {
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveReviewLocally(entityName, review) {
  try {
    const current = loadSavedReviews();
    current[entityName] = review;
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(current));
  } catch (err) {
    console.error("Failed to save review to localStorage:", err);
  }
}

function determineAlignment(manualPriority, veilRiskBand) {
  if (!manualPriority || !veilRiskBand) return { label: "Indeterminate", class: "align-neutral" };
  const mp = manualPriority.toLowerCase();
  const vb = veilRiskBand.toLowerCase();
  if (mp === vb) {
    return { label: "Full Concordance", class: "align-full", desc: "Human assessment and VEIL composite output are in exact tier agreement." };
  }
  const tiers = ["low", "medium", "high", "critical"];
  const mIdx = tiers.indexOf(mp);
  const vIdx = tiers.indexOf(vb);
  if (mIdx !== -1 && vIdx !== -1 && Math.abs(mIdx - vIdx) === 1) {
    return { label: "Adjacent Alignment", class: "align-adjacent", desc: "Human assessment and VEIL output differ by exactly one priority tier." };
  }
  return { label: "Divergent Assessment", class: "align-divergent", desc: "Human assessment and VEIL output diverge significantly across multiple tiers." };
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

  const [localReviews, setLocalReviews] = useState(loadSavedReviews);
  const [loadingEntity, setLoadingEntity] = useState(false);
  const [telemetry, setTelemetry] = useState(null);
  const [veilData, setVeilData] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [apiPersistenceStatus, setApiPersistenceStatus] = useState(null);

  // Assessment Form State
  const [formData, setFormData] = useState({
    q1_concern: "",
    q2_concern_type: "",
    q3_priority: "",
    q4_recommended: "",
    q5_sufficient: "",
    q6_rationale: "",
  });

  const [formError, setFormError] = useState(null);

  // Load entity operational telemetry and existing review
  useEffect(() => {
    if (!selectedEntity) {
      return;
    }

    let isCancelled = false;

    const loadData = async () => {
      setLoadingEntity(true);
      setFormError(null);
      setApiPersistenceStatus(null);

      // Reset form
      setFormData({
        q1_concern: "",
        q2_concern_type: "",
        q3_priority: "",
        q4_recommended: "",
        q5_sufficient: "",
        q6_rationale: "",
      });

      try {
        let backendReview = null;
        try {
          backendReview = await getManualReview(selectedEntity);
        } catch {
          // Backend endpoint not present
        }

        const existingReview = backendReview || localReviews[selectedEntity];
        if (existingReview && existingReview.answers && !isCancelled) {
          setFormData(existingReview.answers);
        }

        let blindEvidence = null;
        try {
          blindEvidence = await getBlindEvidence(selectedEntity);
        } catch {
          // Ignored
        }

        const details = await getEntityDetails(selectedEntity);
        if (!isCancelled) {
          setVeilData(details);
          if (blindEvidence) {
            setTelemetry(blindEvidence);
          } else if (details) {
            setTelemetry({
              entity_name: details.entity_name,
              alert_count: details.alert_count,
              peer_metrics: details.peer_metrics || {},
              raw_alerts_available: false,
            });
          }
        }
      } catch (err) {
        console.error("Error loading entity data for review:", err);
      } finally {
        if (!isCancelled) {
          setLoadingEntity(false);
        }
      }
    };

    loadData();

    return () => {
      isCancelled = true;
    };
  }, [selectedEntity, localReviews]);

  const activeReview = selectedEntity ? localReviews[selectedEntity] : null;
  const isCompleted = Boolean(activeReview);

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

    const reviewPayload = {
      entity_name: selectedEntity,
      timestamp: new Date().toISOString(),
      reviewer_id: "SUPERVISOR-EXP-01",
      answers: {
        q1_concern: formData.q1_concern,
        q2_concern_type: formData.q2_concern_type,
        q3_priority: formData.q3_priority,
        q4_recommended: formData.q4_recommended,
        q5_sufficient: formData.q5_sufficient,
        q6_rationale: formData.q6_rationale.trim(),
      },
    };

    try {
      const backendResult = await submitManualReview(selectedEntity, reviewPayload);
      if (backendResult) {
        setApiPersistenceStatus({
          savedToBackend: true,
          message: "Assessment successfully stored in backend repository.",
        });
      } else {
        setApiPersistenceStatus({
          savedToBackend: false,
          message: "Backend API required for this workflow is not currently available.",
        });
      }

      saveReviewLocally(selectedEntity, reviewPayload);
      setLocalReviews((prev) => ({ ...prev, [selectedEntity]: reviewPayload }));
    } catch (err) {
      console.error("Submission error:", err);
      saveReviewLocally(selectedEntity, reviewPayload);
      setLocalReviews((prev) => ({ ...prev, [selectedEntity]: reviewPayload }));
      setApiPersistenceStatus({
        savedToBackend: false,
        message: "Backend API required for this workflow is not currently available.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetReview = () => {
    if (!selectedEntity) return;
    const current = { ...localReviews };
    delete current[selectedEntity];
    localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(current));
    setLocalReviews(current);
    setFormData({
      q1_concern: "",
      q2_concern_type: "",
      q3_priority: "",
      q4_recommended: "",
      q5_sufficient: "",
      q6_rationale: "",
    });
  };

  return (
    <main className="dashboard-shell">
      {/* NAVBAR */}
      <nav className="dashboard-nav">
        <Link to="/" className="dashboard-brand" aria-label="VEIL Home">
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
          <Link to="/dashboard">OVERVIEW</Link>
          <span className="active">MANUAL REVIEW</span>
          <Link to="/audit">AUDIT</Link>
        </div>
        <div className="dashboard-status">
          <span />
          OFFLINE MODE
        </div>
      </nav>

      <section className="dashboard-page">
        {/* HEADER */}
        <div className="dashboard-header" style={{ marginBottom: "32px" }}>
          <div>
            <div className="dashboard-eyebrow">
              03 / HUMAN-IN-THE-LOOP SUPERVISORY REVIEW
            </div>
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
            VIEW 1: ENTITY SELECTION SCREEN (When no entity is chosen)
            ======================================================== */}
        {!selectedEntity && (
          <div>
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

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
                gap: "20px",
                marginTop: "20px",
              }}
            >
              {EXACT_SIX_ENTITIES.map((name, idx) => {
                const review = localReviews[name];
                const reviewed = Boolean(review);

                return (
                  <div
                    key={name}
                    style={{
                      background: "var(--surface)",
                      border: `1px solid ${reviewed ? "rgba(87, 213, 140, 0.3)" : "var(--line)"}`,
                      borderRadius: "6px",
                      padding: "24px",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      transition: "all 0.2s ease",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
                        <span style={{ fontSize: "11px", fontFamily: "monospace", color: "var(--muted)", fontWeight: 700 }}>
                          {(idx + 1).toString().padStart(2, "0")} / 06
                        </span>
                        {reviewed ? (
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "5px",
                              padding: "2px 8px",
                              borderRadius: "3px",
                              background: "rgba(87, 213, 140, 0.12)",
                              border: "1px solid rgba(87, 213, 140, 0.3)",
                              color: "var(--green)",
                              fontSize: "11px",
                              fontWeight: 700,
                            }}
                          >
                            <CheckCircle2 size={12} />
                            COMPLETED
                          </span>
                        ) : (
                          <span
                            style={{
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "5px",
                              padding: "2px 8px",
                              borderRadius: "3px",
                              background: "rgba(255, 255, 255, 0.04)",
                              border: "1px solid var(--line)",
                              color: "var(--muted)",
                              fontSize: "11px",
                              fontWeight: 600,
                            }}
                          >
                            <EyeOff size={12} />
                            PENDING REVIEW
                          </span>
                        )}
                      </div>

                      <h3 style={{ fontSize: "18px", margin: "0 0 8px", color: "var(--text)" }}>
                        {name}
                      </h3>

                      <p style={{ fontSize: "13px", color: "var(--muted)", margin: "0 0 16px", lineHeight: "1.4" }}>
                        {reviewed
                          ? `Reviewed on ${new Date(review.timestamp).toLocaleDateString()} — Priority assessed: ${review.answers.q3_priority}`
                          : "Operational evidence dossier unreviewed. Analytical scores remain blinded until manual assessment submission."}
                      </p>
                    </div>

                    <button
                      onClick={() => handleSelectEntity(name)}
                      style={{
                        padding: "10px 16px",
                        background: reviewed ? "var(--surface-2)" : "rgba(86, 199, 255, 0.12)",
                        border: `1px solid ${reviewed ? "var(--line)" : "var(--accent)"}`,
                        color: reviewed ? "var(--text)" : "var(--accent)",
                        borderRadius: "4px",
                        fontWeight: 600,
                        fontSize: "13px",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "8px",
                        marginTop: "16px",
                        transition: "all 0.2s ease",
                      }}
                    >
                      {reviewed ? (
                        <>
                          <Eye size={15} />
                          <span>View Review & Comparison</span>
                        </>
                      ) : (
                        <>
                          <FileCheck size={15} />
                          <span>Start Manual Review</span>
                        </>
                      )}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ========================================================
            VIEW 2: WORKFLOW SCREEN (When an entity is selected)
            ======================================================== */}
        {selectedEntity && (
          <div>
            {/* BACK BUTTON & ENTITY HEADER */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px", flexWrap: "wrap", gap: "12px" }}>
              <button
                onClick={handleBackToSelection}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--accent)",
                  fontSize: "13px",
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: 0,
                }}
              >
                ← Return to Entity Selection
              </button>

              <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                <span style={{ fontSize: "13px", color: "var(--muted)" }}>
                  Target: <strong style={{ color: "var(--text)" }}>{selectedEntity}</strong>
                </span>
                {isCompleted && (
                  <button
                    onClick={handleResetReview}
                    title="Clear saved review and conduct re-assessment"
                    style={{
                      background: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid var(--line)",
                      color: "var(--muted)",
                      padding: "4px 10px",
                      borderRadius: "3px",
                      fontSize: "11px",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    <RotateCcw size={11} />
                    Re-evaluate
                  </button>
                )}
              </div>
            </div>

            {loadingEntity && (
              <div style={{ padding: "40px", textAlign: "center" }}>
                <div className="skeleton skeleton-card" style={{ height: "120px", marginBottom: "20px" }} />
                <div className="skeleton skeleton-card" style={{ height: "240px" }} />
              </div>
            )}

            {!loadingEntity && (
              <div>
                {/* ----------------------------------------------------
                    BLIND REVIEW PROTOCOL BANNER
                    ---------------------------------------------------- */}
                {!isCompleted && (
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
                      <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
                        <strong style={{ fontSize: "14px", letterSpacing: "0.08em", color: "var(--accent)", textTransform: "uppercase" }}>
                          BLIND REVIEW IN EFFECT
                        </strong>
                        <span style={{ fontSize: "11px", background: "rgba(86, 199, 255, 0.15)", padding: "2px 6px", borderRadius: "2px", color: "var(--accent)" }}>
                          SUPERVISORY INTEGRITY PROTOCOL
                        </span>
                      </div>
                      <p style={{ margin: 0, fontSize: "13px", color: "var(--text)", lineHeight: "1.5" }}>
                        VEIL analytical conclusions (risk score, risk band, primary driver, anomaly scores, and model recommendations) are intentionally hidden until you submit your independent assessment.
                      </p>
                    </div>
                  </div>
                )}

                {/* ----------------------------------------------------
                    1. BLIND EVIDENCE DOSSIER (Descriptive Operational Telemetry)
                    ---------------------------------------------------- */}
                <section
                  className="ranking-panel"
                  style={{
                    background: "var(--surface)",
                    border: "1px solid var(--line)",
                    borderRadius: "6px",
                    padding: "24px",
                    marginBottom: "30px",
                  }}
                >
                  <div className="panel-header" style={{ marginBottom: "20px" }}>
                    <div>
                      <div className="panel-label">SECTION 01 / EVIDENCE DOSSIER</div>
                      <h2>Operational Telemetry Evidence</h2>
                      <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--muted)" }}>
                        Factual descriptive metrics derived from SOC alert telemetry for {selectedEntity}.
                      </p>
                    </div>
                    <span className="panel-meta">RAW TELEMETRY</span>
                  </div>

                  {/* Operational Telemetry Grid */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                      gap: "16px",
                      marginBottom: "20px",
                    }}
                  >
                    <div style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
                      <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                        Total Alert Volume
                      </span>
                      <div style={{ fontSize: "24px", fontWeight: 700, margin: "8px 0 4px", color: "var(--text)" }}>
                        {telemetry?.alert_count ?? "—"}
                      </div>
                      <small style={{ fontSize: "11px", color: "var(--muted)" }}>
                        Peer median: {telemetry?.peer_metrics?.alert_count?.peer_median ?? "—"} alerts
                      </small>
                    </div>

                    <div style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
                      <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                        Avg Alert Closure Duration
                      </span>
                      <div style={{ fontSize: "24px", fontWeight: 700, margin: "8px 0 4px", color: "var(--text)" }}>
                        {telemetry?.peer_metrics?.avg_closure_seconds?.entity != null
                          ? `${Number(telemetry.peer_metrics.avg_closure_seconds.entity).toFixed(0)}s`
                          : "—"}
                      </div>
                      <small style={{ fontSize: "11px", color: "var(--muted)" }}>
                        Peer median: {telemetry?.peer_metrics?.avg_closure_seconds?.peer_median != null
                          ? `${Number(telemetry.peer_metrics.avg_closure_seconds.peer_median).toFixed(0)}s`
                          : "—"}
                      </small>
                    </div>

                    <div style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
                      <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                        Escalation Rate
                      </span>
                      <div style={{ fontSize: "24px", fontWeight: 700, margin: "8px 0 4px", color: "var(--text)" }}>
                        {telemetry?.peer_metrics?.escalation_rate?.entity != null
                          ? `${(Number(telemetry.peer_metrics.escalation_rate.entity) * 100).toFixed(1)}%`
                          : "—"}
                      </div>
                      <small style={{ fontSize: "11px", color: "var(--muted)" }}>
                        Peer median: {telemetry?.peer_metrics?.escalation_rate?.peer_median != null
                          ? `${(Number(telemetry.peer_metrics.escalation_rate.peer_median) * 100).toFixed(1)}%`
                          : "—"}
                      </small>
                    </div>

                    <div style={{ background: "var(--surface-2)", padding: "16px", borderRadius: "4px", border: "1px solid var(--line)" }}>
                      <span style={{ fontSize: "11px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                        Avg Investigation Note Length
                      </span>
                      <div style={{ fontSize: "24px", fontWeight: 700, margin: "8px 0 4px", color: "var(--text)" }}>
                        {telemetry?.peer_metrics?.avg_note_length?.entity != null
                          ? `${Number(telemetry.peer_metrics.avg_note_length.entity).toFixed(0)} chars`
                          : "—"}
                      </div>
                      <small style={{ fontSize: "11px", color: "var(--muted)" }}>
                        Peer median: {telemetry?.peer_metrics?.avg_note_length?.peer_median != null
                          ? `${Number(telemetry.peer_metrics.avg_note_length.peer_median).toFixed(0)} chars`
                          : "—"}
                      </small>
                    </div>
                  </div>

                  {/* Backend Status Note on Raw Alert Records */}
                  <div
                    style={{
                      background: "rgba(255, 255, 255, 0.02)",
                      border: "1px solid var(--line)",
                      borderRadius: "4px",
                      padding: "12px 16px",
                      fontSize: "12px",
                      color: "var(--muted)",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                    }}
                  >
                    <Info size={16} color="var(--accent)" style={{ flexShrink: 0 }} />
                    <span>
                      <strong>Operational Telemetry Integrity Notice:</strong> Evidence provided contains strictly factual operational records. No automated verdicts, risk scores, or diagnostic interpretations are included in this blind phase.
                    </span>
                  </div>
                </section>

                {/* ----------------------------------------------------
                    2. REVIEWER ASSESSMENT FORM (Before submission)
                    ---------------------------------------------------- */}
                {!isCompleted && (
                  <form
                    onSubmit={handleSubmitReview}
                    className="ranking-panel"
                    style={{
                      background: "var(--surface)",
                      border: "1px solid var(--line)",
                      borderRadius: "6px",
                      padding: "28px",
                      marginBottom: "30px",
                    }}
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
                      <div
                        style={{
                          background: "rgba(239, 107, 114, 0.12)",
                          border: "1px solid rgba(239, 107, 114, 0.3)",
                          borderRadius: "4px",
                          padding: "12px 16px",
                          marginBottom: "20px",
                          color: "var(--red)",
                          fontSize: "13px",
                          display: "flex",
                          alignItems: "center",
                          gap: "10px",
                        }}
                      >
                        <AlertCircle size={16} />
                        <span>{formError}</span>
                      </div>
                    )}

                    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
                      {/* Q1: Supervisory concern present? */}
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
                                transition: "all 0.15s ease",
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

                      {/* Q2: Concern type */}
                      <div>
                        <label style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "var(--text)", marginBottom: "10px" }}>
                          2. Concern type <span style={{ color: "var(--red)" }}>*</span>
                        </label>
                        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                          {["Execution weakness", "Missing evidence", "Unusual behaviour", "Other", "No concern"].map((opt) => (
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
                                transition: "all 0.15s ease",
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

                      {/* Q3: Manual reviewer priority */}
                      <div>
                        <label style={{ display: "block", fontSize: "14px", fontWeight: 600, color: "var(--text)", marginBottom: "10px" }}>
                          3. Manual reviewer priority <span style={{ color: "var(--red)" }}>*</span>
                        </label>
                        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
                          {["Critical", "High", "Medium", "Low"].map((opt) => {
                            const isSelected = formData.q3_priority === opt;
                            const colorMap = {
                              Critical: "var(--red)",
                              High: "var(--amber)",
                              Medium: "var(--accent)",
                              Low: "var(--green)",
                            };
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
                                  transition: "all 0.15s ease",
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

                      {/* Q4: Manual review recommended? */}
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
                                transition: "all 0.15s ease",
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

                      {/* Q5: Evidence sufficient? */}
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
                                transition: "all 0.15s ease",
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

                      {/* Q6: Reviewer rationale */}
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

                    {/* SUBMIT BUTTON */}
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
                          transition: "all 0.2s ease",
                        }}
                      >
                        <Send size={15} />
                        <span>{submitting ? "Submitting Assessment..." : "Submit Supervisory Assessment"}</span>
                      </button>
                    </div>
                  </form>
                )}

                {/* ----------------------------------------------------
                    3. POST-SUBMISSION CONFIRMATION & COMPARISON
                    ---------------------------------------------------- */}
                {isCompleted && (
                  <div>
                    {/* CONFIRMATION BANNER */}
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
                          <strong style={{ fontSize: "15px", color: "var(--green)" }}>
                            Supervisory Assessment Submitted & Recorded
                          </strong>
                          <span style={{ fontSize: "11px", color: "var(--muted)", fontFamily: "monospace" }}>
                            {activeReview?.timestamp ? new Date(activeReview.timestamp).toLocaleString() : ""}
                          </span>
                        </div>
                        <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--text)" }}>
                          Blind review complete. Analytical VEIL conclusions are now revealed below for supervisory concordance verification.
                        </p>
                        {apiPersistenceStatus && !apiPersistenceStatus.savedToBackend && (
                          <div style={{ marginTop: "10px", fontSize: "12px", color: "var(--amber)", display: "flex", alignItems: "center", gap: "6px" }}>
                            <Info size={13} />
                            <span>Backend API required for persistent storage is not currently available. Review preserved in session state.</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* COMPARISON SECTION: MANUAL REVIEW VS VEIL OUTPUT */}
                    <section
                      className="ranking-panel"
                      style={{
                        background: "var(--surface)",
                        border: "1px solid var(--line)",
                        borderRadius: "6px",
                        padding: "28px",
                        marginBottom: "30px",
                      }}
                    >
                      <div className="panel-header" style={{ marginBottom: "24px" }}>
                        <div>
                          <div className="panel-label">SECTION 03 / COMPARISON ANALYSIS</div>
                          <h2>Manual Review vs VEIL Output</h2>
                          <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--muted)" }}>
                            Comparative analysis contrasting independent human supervisory findings with automated VEIL model conclusions.
                          </p>
                        </div>
                        <span className="panel-meta">VERIFICATION MATRIX</span>
                      </div>

                      {/* ALIGNMENT STATUS BADGE */}
                      {(() => {
                        const align = determineAlignment(activeReview?.answers?.q3_priority, veilData?.risk_band);
                        return (
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
                                Supervisory Concordance Assessment
                              </span>
                              <div style={{ fontSize: "18px", fontWeight: 700, color: "var(--text)", marginTop: "4px" }}>
                                {align.label}
                              </div>
                              <small style={{ color: "var(--muted)", fontSize: "12px" }}>
                                {align.desc}
                              </small>
                            </div>
                            <div style={{ display: "flex", gap: "10px" }}>
                              <Link
                                to={`/entities/${encodeURIComponent(selectedEntity)}`}
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  gap: "6px",
                                  fontSize: "12px",
                                  padding: "6px 12px",
                                  borderRadius: "4px",
                                  background: "rgba(86, 199, 255, 0.1)",
                                  border: "1px solid var(--accent)",
                                  color: "var(--accent)",
                                  textDecoration: "none",
                                  fontWeight: 600,
                                }}
                              >
                                <span>Inspect Full VEIL Dossier</span>
                                <ExternalLink size={12} />
                              </Link>
                            </div>
                          </div>
                        );
                      })()}

                      {/* COMPARISON TABLE */}
                      <div style={{ overflowX: "auto", width: "100%", marginBottom: "28px" }}>
                        <table
                          style={{
                            width: "100%",
                            borderCollapse: "collapse",
                            fontSize: "13px",
                            textAlign: "left",
                            minWidth: "680px",
                          }}
                        >
                          <thead>
                            <tr
                              style={{
                                borderBottom: "1px solid var(--line)",
                                color: "var(--muted)",
                                fontSize: "11px",
                                letterSpacing: "0.08em",
                                textTransform: "uppercase",
                              }}
                            >
                              <th style={{ padding: "12px 16px", width: "220px" }}>Dimension</th>
                              <th style={{ padding: "12px 16px" }}>Independent Human Review</th>
                              <th style={{ padding: "12px 16px" }}>VEIL Automated Output</th>
                              <th style={{ padding: "12px 16px", width: "140px" }}>Status</th>
                            </tr>
                          </thead>
                          <tbody>
                            {/* 1. Supervisory Concern */}
                            <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                              <td style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text)" }}>
                                Supervisory Concern
                              </td>
                              <td style={{ padding: "14px 16px" }}>
                                <strong style={{ color: activeReview?.answers?.q1_concern === "Yes" ? "var(--amber)" : "var(--green)" }}>
                                  {activeReview?.answers?.q1_concern || "—"}
                                </strong>
                              </td>
                              <td style={{ padding: "14px 16px" }}>
                                <strong style={{ color: (veilData?.risk_band || "").toLowerCase() !== "low" ? "var(--amber)" : "var(--green)" }}>
                                  {(veilData?.risk_band || "").toLowerCase() !== "low" ? "Elevated Risk Flagged" : "Normal Baseline"}
                                </strong>
                              </td>
                              <td style={{ padding: "14px 16px" }}>
                                {(() => {
                                  const humanConcern = activeReview?.answers?.q1_concern === "Yes";
                                  const veilConcern = (veilData?.risk_band || "").toLowerCase() !== "low";
                                  const match = humanConcern === veilConcern;
                                  return (
                                    <span style={{ color: match ? "var(--green)" : "var(--amber)", fontWeight: 600, fontSize: "12px" }}>
                                      {match ? "Agreement" : "Discrepancy"}
                                    </span>
                                  );
                                })()}
                              </td>
                            </tr>

                            {/* 2. Concern Classification */}
                            <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                              <td style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text)" }}>
                                Primary Issue / Driver
                              </td>
                              <td style={{ padding: "14px 16px" }}>
                                <span>{activeReview?.answers?.q2_concern_type || "—"}</span>
                              </td>
                              <td style={{ padding: "14px 16px" }}>
                                <span>{veilData?.primary_driver || "Baseline Alignment"}</span>
                              </td>
                              <td style={{ padding: "14px 16px", color: "var(--muted)", fontSize: "12px" }}>
                                Operational Context
                              </td>
                            </tr>

                            {/* 3. Priority / Risk Tier */}
                            <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                              <td style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text)" }}>
                                Priority / Risk Band
                              </td>
                              <td style={{ padding: "14px 16px" }}>
                                <span
                                  style={{
                                    display: "inline-block",
                                    padding: "3px 8px",
                                    borderRadius: "2px",
                                    fontSize: "11px",
                                    fontWeight: 700,
                                    textTransform: "uppercase",
                                    background: "rgba(255, 255, 255, 0.08)",
                                    border: "1px solid var(--line)",
                                    color: "var(--text)",
                                  }}
                                >
                                  {activeReview?.answers?.q3_priority}
                                </span>
                              </td>
                              <td style={{ padding: "14px 16px" }}>
                                <span
                                  style={{
                                    display: "inline-block",
                                    padding: "3px 8px",
                                    borderRadius: "2px",
                                    fontSize: "11px",
                                    fontWeight: 700,
                                    textTransform: "uppercase",
                                    background: "rgba(86, 199, 255, 0.12)",
                                    border: "1px solid rgba(86, 199, 255, 0.3)",
                                    color: "var(--accent)",
                                  }}
                                >
                                  {veilData?.risk_band} ({Number(veilData?.risk_score || 0).toFixed(1)}/100)
                                </span>
                              </td>
                              <td style={{ padding: "14px 16px" }}>
                                {(() => {
                                  const mp = (activeReview?.answers?.q3_priority || "").toLowerCase();
                                  const vb = (veilData?.risk_band || "").toLowerCase();
                                  const match = mp === vb;
                                  return (
                                    <span style={{ color: match ? "var(--green)" : "var(--amber)", fontWeight: 600, fontSize: "12px" }}>
                                      {match ? "Exact Match" : "Tier Shift"}
                                    </span>
                                  );
                                })()}
                              </td>
                            </tr>

                            {/* 4. Manual Review Recommendation */}
                            <tr style={{ borderBottom: "1px solid rgba(255, 255, 255, 0.04)" }}>
                              <td style={{ padding: "14px 16px", fontWeight: 600, color: "var(--text)" }}>
                                Supervisory Review Required
                              </td>
                              <td style={{ padding: "14px 16px" }}>
                                <strong>{activeReview?.answers?.q4_recommended}</strong>
                              </td>
                              <td style={{ padding: "14px 16px" }}>
                                <strong>
                                  {(veilData?.risk_score || 0) >= 45 ? "Yes (High/Critical Tier)" : "No (Baseline Monitoring)"}
                                </strong>
                              </td>
                              <td style={{ padding: "14px 16px" }}>
                                {(() => {
                                  const hRec = activeReview?.answers?.q4_recommended === "Yes";
                                  const vRec = (veilData?.risk_score || 0) >= 45;
                                  const match = hRec === vRec;
                                  return (
                                    <span style={{ color: match ? "var(--green)" : "var(--amber)", fontWeight: 600, fontSize: "12px" }}>
                                      {match ? "Agreement" : "Discrepancy"}
                                    </span>
                                  );
                                })()}
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>

                      {/* RATIONALE & EVIDENCE CONTRAST */}
                      <div
                        style={{
                          display: "grid",
                          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                          gap: "20px",
                          marginTop: "20px",
                        }}
                      >
                        {/* Human Rationale */}
                        <div
                          style={{
                            background: "var(--surface-2)",
                            border: "1px solid var(--line)",
                            borderRadius: "4px",
                            padding: "18px",
                          }}
                        >
                          <div style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>
                            Recorded Human Rationale
                          </div>
                          <p style={{ margin: 0, fontSize: "13px", lineHeight: "1.5", color: "var(--text)", whiteSpace: "pre-wrap" }}>
                            {activeReview?.answers?.q6_rationale || "No rationale provided."}
                          </p>
                        </div>

                        {/* VEIL Automated Evidence Findings */}
                        <div
                          style={{
                            background: "var(--surface-2)",
                            border: "1px solid var(--line)",
                            borderRadius: "4px",
                            padding: "18px",
                          }}
                        >
                          <div style={{ fontSize: "12px", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "8px" }}>
                            VEIL Automated Findings Summary
                          </div>
                          {veilData?.findings && veilData.findings.length > 0 ? (
                            <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "13px", color: "var(--text)", lineHeight: "1.6" }}>
                              {veilData.findings.map((f, i) => (
                                <li key={i}>
                                  <strong>{f.rule}</strong>: {f.description} ({f.evidence_count} evidence items)
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p style={{ margin: 0, fontSize: "13px", color: "var(--muted)" }}>
                              No anomalous rule violations identified by automated detectors.
                            </p>
                          )}
                        </div>
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
