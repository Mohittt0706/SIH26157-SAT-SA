// Lucide icons could be added here if needed

function getSignalLevel(score) {
  if (score >= 0.7) return { label: "HIGH", color: "var(--red)" };
  if (score >= 0.3) return { label: "MEDIUM", color: "var(--amber)" };
  return { label: "LOW", color: "var(--green)" };
}

function formatDetectorName(detector) {
  if (!detector) return "Operational Signal";
  switch (detector.toLowerCase()) {
    case "execution_gap":
      return "Execution Gap";
    case "negative_space":
      return "Negative Space";
    case "anomaly":
      return "Anomaly Detection";
    default:
      return detector.replace(/_/g, " ");
  }
}

export default function WhyFlaggedPanel({ data }) {
  if (!data) return null;

  const componentScores = data.component_scores || {};
  const egScore = componentScores.execution_gap ?? 0;
  const nsScore = componentScores.negative_space ?? 0;
  const anScore = componentScores.anomaly ?? 0;

  const egLevel = getSignalLevel(egScore);
  const nsLevel = getSignalLevel(nsScore);
  const anLevel = getSignalLevel(anScore);

  // Identify the highest component driver
  const components = [
    { key: "execution_gap", name: "Execution Gap", score: egScore, level: egLevel },
    { key: "negative_space", name: "Negative Space", score: nsScore, level: nsLevel },
    { key: "anomaly", name: "Anomaly", score: anScore, level: anLevel },
  ];
  components.sort((a, b) => b.score - a.score);
  const topComponent = components[0];

  const primaryDriverName = data.primary_driver
    ? formatDetectorName(data.primary_driver)
    : topComponent.name;

  const primaryDriverLevel = getSignalLevel(topComponent.score);

  // Collect all real evidence items from findings
  const findings = data.findings || [];
  const primaryFindings = findings.filter(
    (f) =>
      f.detector?.toLowerCase() === (data.primary_driver || topComponent.key).toLowerCase()
  );

  const mainFinding = primaryFindings[0] || findings[0];

  return (
    <section className="ranking-panel" style={{ marginTop: "30px" }}>
      <div className="panel-header">
        <div>
          <div className="panel-label">EXPLAINABILITY & REASONING</div>
          <h2>WHY FLAGGED?</h2>
          <p style={{ margin: "4px 0 0", fontSize: "12px", color: "var(--muted)", maxWidth: "650px" }}>
            Direct supervisory explanation connecting the composite risk score to operational evidence without requiring algorithmic interpretation.
          </p>
        </div>
        <span className="panel-meta">EVIDENCE-BACKED EXPLANATION</span>
      </div>

      <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "20px" }}>
        {/* Top Driver Highlight Card */}
        <div
          style={{
            background: "rgba(255, 255, 255, 0.02)",
            border: "1px solid var(--line)",
            borderRadius: "2px",
            padding: "20px",
            display: "flex",
            flexDirection: "column",
            gap: "12px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px" }}>
            <span style={{ fontSize: "11px", color: "var(--muted)", letterSpacing: "0.1em", fontWeight: 700 }}>
              PRIMARY DRIVER
            </span>
            <span
              style={{
                fontSize: "12px",
                fontWeight: 700,
                color: primaryDriverLevel.color,
                letterSpacing: "0.08em",
              }}
            >
              {primaryDriverName.toUpperCase()} — {primaryDriverLevel.label}
            </span>
          </div>

          <div>
            <h3 style={{ margin: "0 0 6px", fontSize: "16px", color: "var(--text)" }}>
              {mainFinding?.rule ? `${formatDetectorName(mainFinding.detector)}: ${mainFinding.rule.replace(/_/g, " ")}` : "Operational Baseline Alignment"}
            </h3>
            <p style={{ margin: 0, fontSize: "14px", color: "var(--muted)", lineHeight: 1.6 }}>
              {mainFinding?.description ||
                "This entity's operational telemetry aligns with expected peer baselines. No significant deviations or performative closure patterns were detected."}
            </p>
          </div>

          {/* Primary Evidence Items */}
          {mainFinding?.evidence && mainFinding.evidence.length > 0 && (
            <div style={{ marginTop: "8px", borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: "12px" }}>
              <span style={{ fontSize: "11px", color: "var(--accent)", letterSpacing: "0.08em", fontWeight: 700, display: "block", marginBottom: "8px" }}>
                SUPPORTING OPERATIONAL EVIDENCE ({mainFinding.evidence.length} SAMPLED ROWS)
              </span>
              <ul style={{ margin: 0, paddingLeft: "18px", display: "flex", flexDirection: "column", gap: "6px" }}>
                {mainFinding.evidence.map((ev, i) => (
                  <li key={i} style={{ fontSize: "13px", color: "var(--text)", lineHeight: 1.5 }}>
                    <strong>{ev.detail}</strong>
                    <span style={{ color: "var(--muted)", marginLeft: "6px" }}>— {ev.reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(!mainFinding || !mainFinding.evidence || mainFinding.evidence.length === 0) && (
            <div style={{ marginTop: "4px", fontSize: "13px", color: "var(--muted)", fontStyle: "italic" }}>
              No specific evidence items available for this signal.
            </div>
          )}
        </div>

        {/* Secondary Signal Breakdown Grid */}
        <div>
          <div style={{ fontSize: "11px", color: "var(--muted)", letterSpacing: "0.1em", fontWeight: 700, marginBottom: "10px" }}>
            DETECTOR SIGNAL LEVELS
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: "12px",
            }}
          >
            {/* Execution Gap */}
            <div
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--line)",
                padding: "14px 16px",
                borderRadius: "2px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text)" }}>Execution Gap</span>
                <span style={{ fontSize: "11px", fontWeight: 700, color: egLevel.color }}>
                  {egLevel.label} ({egScore.toFixed(2)})
                </span>
              </div>
              <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)", lineHeight: 1.4 }}>
                {egScore >= 0.3
                  ? "Elevated fast closure rates or template investigation notes observed."
                  : "Investigation notes and closure times are consistent with genuine analysis."}
              </p>
            </div>

            {/* Negative Space */}
            <div
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--line)",
                padding: "14px 16px",
                borderRadius: "2px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text)" }}>Negative Space</span>
                <span style={{ fontSize: "11px", fontWeight: 700, color: nsLevel.color }}>
                  {nsLevel.label} ({nsScore.toFixed(2)})
                </span>
              </div>
              <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)", lineHeight: 1.4 }}>
                {nsScore >= 0.3
                  ? "Suspicious silence, missing severity categories, or asset blindness detected."
                  : "Expected telemetry distribution aligns with peer volume and severity baselines."}
              </p>
            </div>

            {/* Anomaly */}
            <div
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--line)",
                padding: "14px 16px",
                borderRadius: "2px",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text)" }}>Isolation Anomaly</span>
                <span style={{ fontSize: "11px", fontWeight: 700, color: anLevel.color }}>
                  {anLevel.label} ({anScore.toFixed(2)})
                </span>
              </div>
              <p style={{ margin: 0, fontSize: "12px", color: "var(--muted)", lineHeight: 1.4 }}>
                {anScore >= 0.3
                  ? "Multi-dimensional feature vector isolates entity significantly from cluster peers."
                  : "Operational metrics cluster naturally within the peer cohort."}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
