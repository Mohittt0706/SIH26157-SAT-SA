import { useRef, useState } from "react";
import { Upload, FileText, X, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { uploadCSV } from "../lib/api";

export default function UploadPage() {
  const fileInputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [error, setError] = useState("");

  const handleFile = (selectedFile) => {
    setError("");
    setUploadResult(null);

    if (!selectedFile) return;

    const isCsv = selectedFile.name.toLowerCase().endsWith(".csv");

    if (!isCsv) {
      setFile(null);
      setError("Please select a CSV file.");
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

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const uploadFile = async () => {
    if (!file) {
      setError("Please select a CSV file first.");
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
          errorMessage = JSON.stringify(detail);
        }
      }

      setError(errorMessage);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <main className="upload-shell">
      <nav className="upload-nav">
        <Link to="/" className="upload-brand">
          <div className="upload-brand-mark">V</div>

          <div>
            <div className="upload-brand-name">VEIL</div>
            <div className="upload-brand-subtitle">
              Supervisory Intelligence for SOC Assessment
            </div>
          </div>
        </Link>

        <div className="upload-nav-status">
          <span />
          OFFLINE MODE
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

            <div className="workspace-format">CSV ONLY</div>
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

              <h3>Drop your CSV file here</h3>

              <p>
                or{" "}
                <span className="browse-text">
                  browse files
                </span>
              </p>

              <span className="drop-hint">
                Supported format: .csv
              </span>

              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                onChange={handleInputChange}
                hidden
              />
            </div>
          )}

          {file && !uploadResult && (
            <div className="selected-file">
              <div className="file-icon">
                <FileText size={21} strokeWidth={1.5} />
              </div>

              <div className="file-information">
                <strong>{file.name}</strong>
                <span>
                  {(file.size / 1024).toFixed(1)} KB
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
                className="analyze-button"
                onClick={uploadFile}
                disabled={!file || isUploading}
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
                    INGESTION COMPLETE
                  </div>

                  <h2>Dataset ready for analysis.</h2>
                </div>

                <div className="success-status">
                  <span />
                  SUCCESS
                </div>
              </div>

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
                  <strong>{uploadResult.rows_skipped}</strong>
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

              <Link
                to="/dashboard"
                className="dashboard-button"
              >
                VIEW DASHBOARD
                <ArrowRight size={17} />
              </Link>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
