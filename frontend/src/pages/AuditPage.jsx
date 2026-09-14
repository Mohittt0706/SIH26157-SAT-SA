import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Shield,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { getAuditRuns, getAuditRunDetail } from "../lib/api";
import usePageMetadata from "../hooks/usePageMetadata";
import BrandBlock from "../components/BrandBlock";

export default function AuditPage() {
  const [runs, setRuns] = useState([]);
  const [detail, setDetail] = useState(null);
  const [loadingRuns, setLoadingRuns] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState(null);
  const [searchParams] = useSearchParams();
  const detailRef = useRef(null);

  usePageMetadata({
    title: "Audit & Assessment History | VEIL",
    description:
      "Traceable assessment runs with reproducible detector configuration and results.",
    path: "/audit",
  });

  // Fetch audit runs
  useEffect(() => {
    const fetchRuns = async () => {
      try {
        setLoadingRuns(true);
        setError(null);
        const data = await getAuditRuns();
        setRuns(data || []);
      } catch (err) {
        console.error(err);
        setError("Unable to load audit history.");
      } finally {
        setLoadingRuns(false);
      }
    };
    fetchRuns();
  }, []);

  // Fetch audit run detail
  useEffect(() => {
    const fetchDetail = async () => {
      const param = searchParams.get("runId");
      if (param) {
        const id = parseInt(param, 10);
        if (!isNaN(id)) {
          try {
            setLoadingDetail(true);
            const d = await getAuditRunDetail(id);
            setDetail(d);
          } catch (err) {
            console.error(err);
            setError("Unable to load audit details.");
          } finally {
            setLoadingDetail(false);
          }
        }
      }
    };
    fetchDetail();
  }, [searchParams]);

  // If no run ID in URL but a run is selected, update detail
  useEffect(() => {
    if (runs.length > 0 && !detail && !loadingDetail) {
      // Auto-load the most recent run
      getAuditRunDetail(runs[0].id).then(
        (d) => {
          setDetail(d);
          setLoadingDetail(false);
        }
      ).catch(
        (err) => {
          console.error(err);
          setError("Unable to load audit details.");
          setLoadingDetail(false);
        }
      );
    }
  }, [runs, detail, loadingDetail]);

  // Scroll the detail card into view whenever a new run is loaded, so
  // selecting a row gives immediate, visible feedback.
  useEffect(() => {
    if (detail && detailRef.current) {
      detailRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [detail]);

  // Handle run selection from the table
  const handleRunSelect = (runId, event) => {
    if (event) event.stopPropagation();
    getAuditRunDetail(runId).then(
      (d) => {
        setDetail(d);
        // Update URL to show the run ID
        const run = runs.find((r) => r.id === runId);
        if (run) {
          // Use push to update URL without replacing history
          window.history.pushState(
            {},
            "",
            `/audit?runId=${runId}`
          );
        }
      }
    ).catch((err) => {
      console.error(err);
      setError("Unable to load audit details.");
    });
  };

  if (loadingRuns) {
    return (
      <main className="audit-shell">
        <nav className="dashboard-nav">
          <BrandBlock />
          <div className="dashboard-nav-links">
            <Link to="/upload">ANALYZE</Link>
            <Link to="/dashboard">OVERVIEW</Link>
            <Link to="/manual-review">MANUAL REVIEW</Link>
            <span className="active">AUDIT</span>
          </div>
          <div className="dashboard-status">
            <span />
            AIR-GAPPED
          </div>
        </nav>
        <section className="audit-page">
          <div className="audit-content">
            <div className="audit-loader">
              <Loader2 size={48} />
              <p>Loading audit history...</p>
            </div>
          </div>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="audit-shell">
        <nav className="dashboard-nav">
          <BrandBlock />
          <div className="dashboard-nav-links">
            <Link to="/upload">ANALYZE</Link>
            <Link to="/dashboard">OVERVIEW</Link>
            <Link to="/manual-review">MANUAL REVIEW</Link>
            <span className="active">AUDIT</span>
          </div>
          <div className="dashboard-status">
            <span />
            AIR-GAPPED
          </div>
        </nav>
        <section className="audit-page">
          <div className="audit-content">
            <div className="error-state">
              <AlertCircle size={32} />
              <h3>Unable to load audit history.</h3>
              <p>{error}</p>
            </div>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="audit-shell">
      <nav className="dashboard-nav">
        <BrandBlock />
        <div className="dashboard-nav-links">
            <Link to="/upload">ANALYZE</Link>
            <Link to="/dashboard">OVERVIEW</Link>
            <Link to="/manual-review">MANUAL REVIEW</Link>
            <span className="active">AUDIT</span>
        </div>
        <div className="dashboard-status">
          <span />
          AIR-GAPPED
        </div>
      </nav>

      <section className="audit-page">
        <div className="audit-content">
          {/* RUN LIST SECTION */}
          <div className="audit-runs-section">
            <div className="section-header">
              <h2>AUDIT & ASSESSMENT HISTORY</h2>
              <p>
                "Every assessment run preserves the source metadata, detector
                configuration, and resulting risk scores so historical findings can
                be traced and reproduced."
              </p>
            </div>

            {runs.length === 0 ? (
              <div className="empty-state">
                <Shield size={48} />
                <h3>No assessment runs available.</h3>
                <p>
                  No assessment runs have been recorded yet. Upload a CSV or JSON
                  dataset to begin assessment runs.
                </p>
              </div>
            ) : (
              <div className="runs-table">
                <table>
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Timestamp</th>
                      <th>Source</th>
                      <th>Format</th>
                      <th>Rows</th>
                      <th>Entities</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr
                        key={run.id}
                        className={detail?.id === run.id ? "selected" : undefined}
                        onClick={(e) => handleRunSelect(run.id, e)}
                      >
                        <td>{run.id}</td>
                        <td>
                          {new Date(run.timestamp).toLocaleDateString()} {
                            new Date(
                              run.timestamp
                            ).toLocaleTimeString()
                          }
                        </td>
                        <td>{run.filename}</td>
                        <td>{run.format}</td>
                        <td>{run.rows_received}</td>
                        <td>{run.entity_count}</td>
                        <td>
                          <button
                            type="button"
                            className="view-button"
                            onClick={(e) => handleRunSelect(run.id, e)}
                          >
                            VIEW DETAILS
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Empty state when no runs */}
            {runs.length === 0 && (
              <p className="empty-state-message">
                No assessment runs available. Start by uploading a dataset.
              </p>
            )}
          </div>

          {/* DETAIL VIEW SECTION */}
          {detail && (
            <div className="audit-detail-section" ref={detailRef}>
              <div className="section-nav">
                <Link
                  to={`/audit?runId=${detail.id}`}
                  style={{ marginBottom: "20px", display: "inline-block" }}
                >
                  &larr; Back to runs
                </Link>
              </div>

              <div className="detail-cards">
                {/* A. RUN INFORMATION */}
                <div className="detail-card">
                  <div className="card-header">
                    <h3>RUN INFORMATION</h3>
                  </div>
                  <div className="card-body">
                    <div className="detail-row">
                      <span className="detail-label">Run ID</span>
                      <span>{detail.id}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Timestamp</span>
                      <span>
                        {new Date(detail.timestamp).toLocaleDateString()} {
                          new Date(detail.timestamp).toLocaleTimeString()
                        }
                      </span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Filename</span>
                      <span>{detail.filename}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Format</span>
                      <span>{detail.format}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Rows received</span>
                      <span>{detail.rows_received}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Rows inserted</span>
                      <span>{detail.rows_inserted}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Rows skipped</span>
                      <span>{detail.rows_skipped}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Entity count</span>
                      <span>{detail.entity_count}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Analysis start</span>
                      <span>{detail.data_range_start}</span>
                    </div>
                    <div className="detail-row">
                      <span className="detail-label">Analysis end</span>
                      <span>{detail.data_range_end}</span>
                    </div>
                  </div>
                </div>

                {/* B. DETECTOR CONFIGURATION */}
                <div className="detail-card">
                  <div className="card-header">
                    <h3>DETECTOR CONFIGURATION</h3>
                  </div>
                  <div className="card-body">
                    <div className="config-grid">
                      {/* EXECUTION GAP */}
                      <div className="config-group">
                        <div className="config-group-header">
                          <span>EXECUTION GAP</span>
                        </div>
                        <div className="config-group-body">
                          {detail.detector_config?.fast_closure_threshold_seconds !== undefined && (
                            <div className="config-item">
                              <span>Fast Closure Threshold</span>
                              <span>{detail.detector_config.fast_closure_threshold_seconds}s</span>
                            </div>
                          )}
                          {detail.detector_config?.min_note_length !== undefined && (
                            <div className="config-item">
                              <span>Minimum Note Length</span>
                              <span>{detail.detector_config.min_note_length}</span>
                            </div>
                          )}
                          {detail.detector_config?.min_duplicate_multiplicity !== undefined && (
                            <div className="config-item">
                              <span>Minimum Duplicate Multiplicity</span>
                              <span>{detail.detector_config.min_duplicate_multiplicity}</span>
                            </div>
                          )}
                          {detail.detector_config?.template_duplicate_z_threshold !== undefined && (
                            <div className="config-item">
                              <span>Template Duplicate Z-Threshold</span>
                              <span>{detail.detector_config.template_duplicate_z_threshold}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* NEGATIVE SPACE */}
                      <div className="config-group">
                        <div className="config-group-header">
                          <span>NEGATIVE SPACE</span>
                        </div>
                        <div className="config-group-body">
                          {detail.detector_config?.low_volume_z_threshold !== undefined && (
                            <div className="config-item">
                              <span>Ramp Endpoint</span>
                              <span>{detail.detector_config.low_volume_z_threshold}</span>
                            </div>
                          )}
                          {detail.detector_config?.min_peers_with_severity !== undefined && (
                            <div className="config-item">
                              <span>Minimum Peers With Severity</span>
                              <span>{detail.detector_config.min_peers_with_severity}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* ANOMALY DETECTION */}
                      <div className="config-group">
                        <div className="config-group-header">
                          <span>ANOMALY DETECTION</span>
                        </div>
                        <div className="config-group-body">
                          {detail.detector_config?.iforest_random_state !== undefined && (
                            <div className="config-item">
                              <span>Isolation Forest Random State</span>
                              <span>{detail.detector_config.iforest_random_state}</span>
                            </div>
                          )}
                          {detail.detector_config?.iforest_n_estimators !== undefined && (
                            <div className="config-item">
                              <span>Number of Estimators</span>
                              <span>{detail.detector_config.iforest_n_estimators}</span>
                            </div>
                          )}
                          {detail.detector_config?.iforest_contamination !== undefined && (
                            <div className="config-item">
                              <span>Contamination</span>
                              <span>{detail.detector_config.iforest_contamination}</span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* RISK SCORING */}
                      <div className="config-group">
                        <div className="config-group-header">
                          <span>RISK SCORING</span>
                        </div>
                        <div className="config-group-body">
                          {detail.detector_config?.weight_execution_gap !== undefined && (
                            <div className="config-item">
                              <span>Execution Gap Weight</span>
                              <span>{detail.detector_config.weight_execution_gap}</span>
                            </div>
                          )}
                          {detail.detector_config?.weight_negative_space !== undefined && (
                            <div className="config-item">
                              <span>Negative Space Weight</span>
                              <span>{detail.detector_config.weight_negative_space}</span>
                            </div>
                          )}
                          {detail.detector_config?.weight_anomaly !== undefined && (
                            <div className="config-item">
                              <span>Anomaly Weight</span>
                              <span>{detail.detector_config.weight_anomaly}</span>
                            </div>
                          )}
                          {detail.detector_config?.floor_attenuation !== undefined && (
                            <div className="config-item">
                              <span>Floor Attenuation</span>
                              <span>{detail.detector_config.floor_attenuation}</span>
                            </div>
                          )}
                          {detail.detector_config?.risk_band_critical_threshold !== undefined && (
                            <div className="config-item">
                              <span>Critical Threshold</span>
                              <span>{detail.detector_config.risk_band_critical_threshold}</span>
                            </div>
                          )}
                          {detail.detector_config?.risk_band_high_threshold !== undefined && (
                            <div className="config-item">
                              <span>High Threshold</span>
                              <span>{detail.detector_config.risk_band_high_threshold}</span>
                            </div>
                          )}
                          {detail.detector_config?.risk_band_medium_threshold !== undefined && (
                            <div className="config-item">
                              <span>Medium Threshold</span>
                              <span>{detail.detector_config.risk_band_medium_threshold}</span>
                            </div>
                          )}
                          {detail.detector_config?.finding_summary_threshold !== undefined && (
                            <div className="config-item">
                              <span>Finding Summary Threshold</span>
                              <span>{detail.detector_config.finding_summary_threshold}</span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* C. RESULTS SNAPSHOT */}
                <div className="detail-card">
                  <div className="card-header">
                    <h3>RESULTS SNAPSHOT</h3>
                  </div>
                  <div className="card-body">
                    {detail.results_snapshot && detail.results_snapshot.length > 0 ? (
                      <div className="results-table">
                        <table>
                          <thead>
                            <tr>
                              <th>Entity</th>
                              <th>Risk Score</th>
                              <th>Risk Band</th>
                              <th>Exec Gap</th>
                              <th>Neg Space</th>
                              <th>Anomaly</th>
                            </tr>
                          </thead>
                          <tbody>
                            {detail.results_snapshot.map((entity, idx) => (
                              <tr key={idx} style={{ borderBottom: idx % 2 === 0 ? "1px solid var(--line)" : "none" }}>
                                <td>{entity.entity_name}</td>
                                <td>{entity.risk_score}</td>
                                <td>
                                  <span className={`risk-band-${entity.risk_band.toLowerCase()}`}>
                                    {entity.risk_band}
                                  </span>
                                </td>
                                <td>{(entity.execution_gap_component_score || 0).toFixed(2)}</td>
                                <td>{(entity.negative_space_component_score || 0).toFixed(2)}</td>
                                <td>{(entity.anomaly_component_score || 0).toFixed(2)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {detail.results_snapshot.length === 0 && (
                          <p className="empty-state-small">
                            No entity results found.
                          </p>
                        )}
                      </div>
                    ) : (
                      <p className="empty-state-small">
                        No entity results available.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}