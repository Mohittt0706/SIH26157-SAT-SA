import { useRef, useState } from "react";
import { Upload, FileText, X, ArrowRight, AlertTriangle } from "lucide-react";
import { Link } from "react-router-dom";
import { uploadCSV } from "../lib/api";
import usePageMetadata from "../hooks/usePageMetadata";
import BrandBlock from "../components/BrandBlock";

// A skip rate at or above this share of received rows is surfaced as a
// prominent warning rather than left as a quiet number in the stat grid.
const SIGNIFICANT_SKIP_RATIO = 0.2;

export default function UploadPage() {
  usePageMetadata({
    title: "Data Ingestion | VEIL",
    description: "Upload structured SOC operational records to begin supervisory analysis.",
    path: "/upload",
  });
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState("");
  const [showPreview, setShowPreview] = useState(false);
  const [previewData, setPreviewData] = useState({ headers: [], rows: [] });

  const handleFile = (selectedFile) => {
    setError("");
    setUploadResult(null);

    if (!selectedFile) return;

    const lowerName = selectedFile.name.toLowerCase();
    const isSupported = lowerName.endsWith(".csv") || lowerName.endsWith(".json");

    if (!isSupported) {
      setFile(null);
      setError("Please select a CSV or JSON file.");
      return;
    }

    if (selectedFile.name === "answer_key_INTERNAL_ONLY.csv") {
      setFile(null);
      setError("Internal answer key files cannot be uploaded. Please select the main SOC dataset CSV instead.");
      return;
    }

    setFile(selectedFile);
  };

  const handleInputChange = (event) => {
    handleFile(event.target.files?.[0]);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);

    const droppedFile = event.dataTransfer.files?.[0];
    handleFile(droppedFile);
  };

  const removeFile = () => {
    setFile(null);
    setUploadResult(null);
    setError("");
    setShowPreview(false);

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const uploadFile = async () => {
    if (!file) {
      setError("Please select a CSV or JSON file first.");
      return;
    }

    setIsUploading(true);
    setError("");
    setUploadResult(null);

    try {
      const data = await uploadCSV(file);
      setUploadResult(data);
    } catch (err) {
      console.error(err);

      let errorMessage = "Upload failed. Make sure the backend is running.";

      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (typeof detail === "object" && detail.missing_columns) {
          errorMessage = `Missing required columns: ${detail.missing_columns.join(", ")}`;
        } else if (typeof detail === "string") {
          errorMessage = detail;
        } else {
          errorMessage = "An unexpected error occurred during analysis. Please check your data format.";
        }
      }

      setError(errorMessage);
    } finally {
      setIsUploading(false);
    }
  };

  const openFile = async (event) => {
    if (event.target.closest(".remove-file")) return;
    if (!file) return;

    try {
      const text = await file.text();

      if (file.name.toLowerCase().endsWith(".json")) {
        const parsed = JSON.parse(text);
        const records = Array.isArray(parsed) ? parsed : parsed.alerts;
        if (Array.isArray(records) && records.length > 0) {
          const headers = Array.from(
            records.slice(0, 100).reduce((keys, record) => {
              Object.keys(record || {}).forEach((key) => keys.add(key));
              return keys;
            }, new Set())
          );
          const rows = records
            .slice(0, 100)
            .map((record) => headers.map((h) => String(record?.[h] ?? "")));
          setPreviewData({ headers, rows });
          setShowPreview(true);
        }
        return;
      }

      const lines = text.split("\n").map((line) => line.trim()).filter(Boolean);
      if (lines.length > 0) {
        const headers = lines[0]
          .split(",")
          .map((h) => h.replace(/^["']|["']$/g, "").trim());
        const rows = lines.slice(1, 101).map((line) => {
          const cells = line.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/);
          return cells.map((cell) => cell.replace(/^["']|["']$/g, "").trim());
        });
        setPreviewData({ headers, rows });
        setShowPreview(true);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const hasIngestedRows = uploadResult ? uploadResult.rows_inserted > 0 : false;
  const skipRatio =
    uploadResult && uploadResult.rows_received > 0
      ? uploadResult.rows_skipped / uploadResult.rows_received
      : 0;
  const hasSignificantSkips = hasIngestedRows && skipRatio >= SIGNIFICANT_SKIP_RATIO;

  return (
    <main className="upload-shell">
      <nav className="upload-nav">
        <BrandBlock />

        <div className="upload-nav-status">
          <span />
          AIR-GAPPED
        </div>
      </nav>

      <section className="upload-page">
        <div className="upload-heading">
          <div className="upload-eyebrow">
            01 / DATA INGESTION
          </div>

          <h1>
            ANALYZE
            <br />
            <span>SOC DATA.</span>
          </h1>

          <p>
            Upload structured SOC operational records to begin
            supervisory analysis.
          </p>
        </div>

        <div className="upload-workspace">
          <div className="workspace-header">
            <div>
              <div className="workspace-label">SOURCE DATA</div>
              <h2>Upload operational records</h2>
            </div>

            <div className="workspace-format">CSV / JSON</div>
          </div>

          {!file && (
            <div
              className={`drop-zone ${isDragging ? "dragging" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="drop-icon">
                <Upload size={22} strokeWidth={1.5} />
              </div>

              <h3>Drop your CSV or JSON file here</h3>

              <p>
                or{" "}
                <span className="browse-text">
                  browse files
                </span>
              </p>

              <span className="drop-hint">
                Supported formats: .csv, .json
              </span>

              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.json,text/csv,application/json"
                onChange={handleInputChange}
                hidden
              />
            </div>
          )}

          {file && !uploadResult && (
            <div
              className="selected-file"
              onClick={openFile}
              style={{ cursor: "pointer" }}
              title={`Click to preview ${file.name}`}
            >
              <div className="file-icon">
                <FileText size={21} strokeWidth={1.5} />
              </div>

              <div className="file-information">
                <strong>{file.name}</strong>
                <span>
                  {(file.size / 1024).toFixed(1)} KB (Click to view preview)
                </span>
              </div>

              <button
                className="remove-file"
                onClick={removeFile}
                aria-label="Remove file"
              >
                <X size={18} />
              </button>
            </div>
          )}

          {error && (
            <div className="upload-error">
              <span>!</span>
              {error}
            </div>
          )}

          {!uploadResult && (
            <div className="upload-footer">
              <div className="upload-info">
                <span>REQUIRED FIELDS</span>
                <p>
                  alert_id · entity_name · severity · created_time ·
                  closed_time · escalated · investigation_notes ·
                  asset_type
                </p>
              </div>

              <button
                className={`analyze-button ${isUploading ? "loading" : ""}`}
                onClick={uploadFile}
                disabled={!file || isUploading}
                aria-label={isUploading ? "Analyzing dataset" : "Validate and analyze"}
              >
                {isUploading ? "ANALYZING..." : "VALIDATE & ANALYZE"}
                <ArrowRight size={17} />
              </button>
            </div>
          )}

          {uploadResult && (
            <div className="upload-success">
              <div className="success-top">
                <div>
                  <div className="success-label">
                    {hasIngestedRows ? "INGESTION COMPLETE" : "NO RECORDS INGESTED"}
                  </div>

                  <h2>
                    {hasIngestedRows
                      ? "Dataset ready for analysis."
                      : "No records ingested."}
                  </h2>
                </div>

                <div className={`success-status${hasIngestedRows ? "" : " warning"}`}>
                  <span />
                  {hasIngestedRows ? "SUCCESS" : "WARNING"}
                </div>
              </div>

              {!hasIngestedRows && (
                <div className="upload-warning">
                  <AlertTriangle size={16} />
                  <span>
                    The file parsed correctly but contained no usable alert rows.
                    Check that the CSV has data rows below the header, and that each
                    row has an <code>alert_id</code>, <code>entity_name</code>, and a
                    valid <code>created_time</code>.
                  </span>
                </div>
              )}

              {hasSignificantSkips && (
                <div className="upload-warning">
                  <AlertTriangle size={16} />
                  <span>
                    <strong>{uploadResult.rows_skipped}</strong> of{" "}
                    {uploadResult.rows_received} rows ({Math.round(skipRatio * 100)}%)
                    were skipped during ingestion. Rows missing alert_id, entity_name,
                    or a valid created_time — or duplicate (entity_name, alert_id)
                    pairs within the file — are dropped. Review the source data before
                    trusting these results.
                  </span>
                </div>
              )}

              <div className="result-grid">
                <div>
                  <span>ROWS RECEIVED</span>
                  <strong>{uploadResult.rows_received}</strong>
                </div>

                <div>
                  <span>ROWS INSERTED</span>
                  <strong>{uploadResult.rows_inserted}</strong>
                </div>

                <div>
                  <span>ENTITIES FOUND</span>
                  <strong>
                    {uploadResult.entities_found?.count ?? 0}
                  </strong>
                </div>

                <div>
                  <span>ROWS SKIPPED</span>
                  <strong className={hasSignificantSkips ? "skipped-highlight" : ""}>
                    {uploadResult.rows_skipped}
                  </strong>
                </div>
              </div>

              <div className="date-range">
                <span>DATA RANGE</span>

                <strong>
                  {uploadResult.date_range?.start || "—"}{" "}
                  →{" "}
                  {uploadResult.date_range?.end || "—"}
                </strong>
              </div>

              {hasIngestedRows ? (
                <Link to="/dashboard" className="dashboard-button">
                  VIEW DASHBOARD
                  <ArrowRight size={17} />
                </Link>
              ) : (
                <button className="dashboard-button" onClick={removeFile}>
                  UPLOAD A DIFFERENT FILE
                  <ArrowRight size={17} />
                </button>
              )}
            </div>
          )}
        </div>
      </section>

      {/* INLINE FILE PREVIEW MODAL */}
      {showPreview && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0, 0, 0, 0.8)",
            backdropFilter: "blur(6px)",
            zIndex: 1000,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "20px",
          }}
          onClick={() => setShowPreview(false)}
        >
          <div
            style={{
              background: "var(--surface)",
              border: "1px solid var(--line)",
              borderRadius: "6px",
              width: "92%",
              maxWidth: "1000px",
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
              boxShadow: "0 20px 50px rgba(0,0,0,0.6)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                padding: "18px 24px",
                borderBottom: "1px solid var(--line)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div>
                <div
                  style={{
                    color: "var(--accent)",
                    fontSize: "11px",
                    fontWeight: "700",
                    letterSpacing: "0.15em",
                    marginBottom: "4px",
                  }}
                >
                  FILE PREVIEW
                </div>
                <strong style={{ fontSize: "15px", color: "var(--text)" }}>
                  {file.name}
                </strong>
                <span
                  style={{
                    fontSize: "12px",
                    color: "var(--muted)",
                    marginLeft: "12px",
                  }}
                >
                  {(file.size / 1024).toFixed(1)} KB · Showing first{" "}
                  {previewData.rows.length} rows
                </span>
              </div>
              <button
                onClick={() => setShowPreview(false)}
                style={{
                  background: "transparent",
                  border: "1px solid var(--line)",
                  color: "var(--text)",
                  cursor: "pointer",
                  padding: "6px 12px",
                  borderRadius: "4px",
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  fontSize: "12px",
                  fontWeight: "700",
                }}
              >
                <X size={16} />
                CLOSE
              </button>
            </div>

            <div style={{ padding: "0", overflow: "auto", flex: 1 }}>
              <table
                style={{
                  width: "100%",
                  borderCollapse: "collapse",
                  fontSize: "12px",
                  textAlign: "left",
                }}
              >
                <thead>
                  <tr
                    style={{
                      background: "rgba(255,255,255,0.03)",
                      borderBottom: "1px solid var(--line)",
                    }}
                  >
                    <th
                      style={{
                        padding: "12px 16px",
                        color: "var(--muted)",
                        fontSize: "11px",
                        letterSpacing: "0.1em",
                      }}
                    >
                      #
                    </th>
                    {previewData.headers.map((h, i) => (
                      <th
                        key={i}
                        style={{
                          padding: "12px 16px",
                          color: "var(--accent)",
                          fontSize: "11px",
                          letterSpacing: "0.1em",
                          textTransform: "uppercase",
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewData.rows.map((row, rIdx) => (
                    <tr
                      key={rIdx}
                      style={{
                        borderBottom: "1px solid rgba(255,255,255,0.04)",
                      }}
                    >
                      <td
                        style={{
                          padding: "10px 16px",
                          color: "var(--muted)",
                          fontSize: "11px",
                        }}
                      >
                        {rIdx + 1}
                      </td>
                      {row.map((cell, cIdx) => (
                        <td
                          key={cIdx}
                          style={{
                            padding: "10px 16px",
                            color: "#d0d5dc",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
