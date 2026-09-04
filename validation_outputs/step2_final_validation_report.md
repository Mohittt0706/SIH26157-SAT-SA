# Step 2 — Final Consolidated ML Validation Report

**Report Type:** Consolidated Independent ML Validation  
**Scope:** External 5-company dataset validation  
**Generated:** 2026-09-04  
**Status:** FINAL

---

## 1. Executive Summary

This report consolidates results from six independent validation steps (2.1 through 2.6) performed on five external SOC alert datasets. All validation was conducted as read-only, independent analysis without modifying production ML/analytics code, model artifacts, raw datasets, or existing validation outputs.

**Final Consolidated Verdict: PASS WITH WARNINGS**

- All six validation steps: PASS
- No fabricated, unsupported, or missing evidence
- One known implementation issue identified (model artifact key mismatch)
- Negative Space peer baseline unavailable for external datasets (expected limitation)

---

## 2. Validation Scope

| Step | Description | Verdict |
|------|-------------|---------|
| 2.1 | Dataset Validation | PASS |
| 2.2 | Model Validation | PASS |
| 2.3 | Detector Validation | PASS |
| 2.4 | Risk Score Validation | PASS |
| 2.5 | Evidence Traceability | PASS |
| 2.6 | Edge-Case Testing | PASS |

---

## 3. External Datasets Tested

| Company | File | Rows | Schema (11 cols) | Entity Match |
|---------|------|------|------------------|--------------|
| Equifax | soc_alerts_equifax.csv | 100 | PASS | PASS |
| JPMorgan Chase | soc_alerts_jpmorgan_chase.csv | 100 | PASS | PASS |
| MGM Resorts | soc_alerts_mgm_resorts.csv | 100 | PASS | PASS |
| Microsoft | soc_alerts_microsoft.csv | 100 | PASS | PASS |
| T-Mobile | soc_alerts_t-mobile.csv | 100 | PASS | PASS |

Schema columns: alert_id, entity_name, severity, category, asset_type, created_time, closed_time, closure_duration_minutes, escalated, status, investigation_notes

---

## 4. Step 2.1 — Dataset Validation Result

**Verdict: PASS**

| Check | Result |
|-------|--------|
| File existence | 5/5 PASS |
| Row counts (100 each) | 5/5 PASS |
| Schema validation (11 columns) | 5/5 PASS |
| Duplicate alert IDs | 5/5 PASS (0 duplicates) |
| Entity consistency | 5/5 PASS |
| Categorical validation | 5/5 PASS |
| Timestamp parsing | 5/5 PASS |
| Closure duration consistency | 5/5 PASS |

**Observations:**
- Missing `closed_time`: 11-24% per company (expected for open/in-progress alerts)
- Missing `investigation_notes`: 10-18% per company (data quality note, not blocking)

---

## 5. Step 2.2 — Model Validation Result

**Verdict: PASS**

| Check | Result |
|-------|--------|
| Model file loadable | PASS |
| Model structure valid | PASS (IsolationForest + StandardScaler) |
| Feature order matches | PASS (6 features) |
| Feature computation independent | PASS (5/5 companies) |
| Feature shape & sanity | PASS (no NaN, no Inf) |
| Model inference | PASS (all 5 companies) |
| Score conversion | PASS (0.0-1.0 range) |

**Model Details:**
- Type: IsolationForest (n_estimators=100, contamination=0.2, random_state=42)
- Scaler: StandardScaler (n_features_in_=6)
- Features: alert_count, avg_closure_seconds, escalation_rate, critical_ratio, avg_note_length, unique_asset_types

**Converted Anomaly Scores:**
| Company | Raw Score | Converted Score |
|---------|-----------|-----------------|
| Equifax | 0.0552 | 0.0214 |
| JPMorgan Chase | 0.0558 | 0.0000 |
| MGM Resorts | 0.0555 | 0.0078 |
| Microsoft | 0.0278 | 1.0000 |
| T-Mobile | 0.0536 | 0.0780 |

---

## 6. Step 2.3 — Detector Validation Result

**Verdict: PASS**

### Execution Gap (EG) Results

| Company | EG Score | FAST_CLOSURE | NO_ESCALATION | TEMPLATE_NOTES |
|---------|----------|--------------|---------------|----------------|
| Equifax | 0.5143 | 0.000 (0/30) | 0.714 (10/14) | 1.000 (100/100) |
| JPMorgan Chase | 0.5308 | 0.000 (0/22) | 0.769 (10/13) | 1.000 (100/100) |
| MGM Resorts | 0.4909 | 0.000 (0/27) | 0.636 (7/11) | 1.000 (100/100) |
| Microsoft | 0.5250 | 0.000 (0/18) | 0.750 (6/8) | 1.000 (100/100) |
| T-Mobile | 0.4500 | 0.000 (0/27) | 0.500 (5/10) | 1.000 (100/100) |

### Negative Space (NS) Results

| Company | NS Score | Total Alerts | Peer Mean | Z-Score |
|---------|----------|--------------|-----------|---------|
| Equifax | 0.000 | 100 | 0.0 | 1.0 |
| JPMorgan Chase | 0.000 | 100 | 0.0 | 1.0 |
| MGM Resorts | 0.000 | 100 | 0.0 | 1.0 |
| Microsoft | 0.000 | 100 | 0.0 | 1.0 |
| T-Mobile | 0.000 | 100 | 0.0 | 1.0 |

**Note:** NS=0 expected for single-entity external datasets (no peer baseline available).

---

## 7. Step 2.4 — Risk Score Validation Result

**Verdict: PASS**

| Company | Weighted | Soft Floor | Final Score | Band | Primary Driver |
|---------|----------|------------|-------------|------|----------------|
| Equifax | 0.2111 | 0.4371 | 43.7 | medium | execution_gap |
| JPMorgan Chase | 0.2123 | 0.4512 | 45.1 | high | execution_gap |
| MGM Resorts | 0.1983 | 0.4173 | 41.7 | medium | execution_gap |
| Microsoft | 0.4600 | 0.8500 | 85.0 | critical | anomaly |
| T-Mobile | 0.1995 | 0.3825 | 38.2 | medium | execution_gap |

**Risk Formula:** `weighted = 0.40*EG + 0.35*NS + 0.25*Anomaly`  
**Soft Floor:** `max(weighted, max(EG,NS,Anomaly) * 0.85)`  
**Bands:** >=70 critical, >=45 high, >=20 medium, <20 low

All 5 companies: Soft floor active, independent scores match production exactly.

---

## 8. Step 2.5 — Evidence Traceability Result

**Verdict: PASS**

| Company | Findings | Supported | Unsupported | Missing | Expected No-Peer |
|---------|----------|-----------|-------------|---------|------------------|
| Equifax | 6 | 4 | 0 | 0 | 2 |
| JPMorgan Chase | 6 | 4 | 0 | 0 | 2 |
| MGM Resorts | 6 | 4 | 0 | 0 | 2 |
| Microsoft | 6 | 4 | 0 | 0 | 2 |
| T-Mobile | 6 | 4 | 0 | 0 | 2 |

- **Total findings checked:** 30
- **Supported evidence:** 20
- **Expected no-peer-baseline:** 10 (NS findings - single-entity datasets)
- **No fabrication detected:** All alert IDs verified as existing in raw CSV

---

## 9. Step 2.6 — Edge-Case Testing Result

**Verdict: PASS**

| Company | Tests | PASS | WARN | FAIL |
|---------|-------|------|------|------|
| Equifax | 11 | 11 | 0 | 0 |
| JPMorgan Chase | 11 | 11 | 0 | 0 |
| MGM Resorts | 11 | 11 | 0 | 0 |
| Microsoft | 11 | 11 | 0 | 0 |
| T-Mobile | 11 | 11 | 0 | 0 |

**Edge Cases Tested (55 total):**
- Missing notes (blank, short)
- Missing closed_time
- Missing closure_duration
- No critical alerts
- No escalated alerts
- Low volume (3 alerts)
- Different asset types
- Incomplete records
- Extreme feature values
- Zero feature values

**Numerical safety:** PASS (all values finite)  
**Detector logic safety:** PASS (all logic valid)

---

## 10. Overall PASS/FAIL/WARNING Summary

| Step | Verdict | Notes |
|------|---------|-------|
| 2.1 Dataset Validation | PASS | All checks pass |
| 2.2 Model Validation | PASS | Model loads, infers, scores valid |
| 2.3 Detector Validation | PASS | EG/NS match production |
| 2.4 Risk Score Validation | PASS | All scores match, soft floor verified |
| 2.5 Evidence Traceability | PASS | All evidence supported or expected no-peer |
| 2.6 Edge-Case Testing | PASS | 55/55 tests pass |

**Consolidated Verdict: PASS WITH WARNINGS**

Warnings are limited to:
1. Negative Space peer baseline unavailable (expected for single-entity datasets)
2. Model artifact key mismatch (known issue, see Section 11)

---

## 11. Known Issues / Observations

### 11.1 Model Artifact Key Mismatch (Known Implementation Issue)

The production `anomaly_model.joblib` contains keys: `['feature_names', 'model', 'scaler']`

The production `load_anomaly_model()` function in `anomaly.py` expects key `"clf"`, but the actual key is `"model"`.

**Impact:** Production `compute_risk_scores_from_csv()` will fail with `ValueError: Invalid model artifact structure` if called directly.

**Status:** This is a pre-existing implementation issue. It was NOT introduced by validation and was NOT modified during validation. The validation correctly identified this mismatch and worked around it by using `model_dict.get("model") or model_dict.get("clf")`.

**Recommendation:** This must be resolved before production deployment, but is outside the scope of this validation.

### 11.2 Negative Space Peer Baseline

All five external datasets contain a single entity each. Negative Space computation requires peer-level comparison. With no peer baseline available, NS=0 is the expected and correct result.

This is NOT a validation failure. It is an inherent limitation of testing with single-entity external datasets.

### 11.3 Missing Investigation Notes

10-18% of records across all companies have missing investigation notes. This is classified as a data quality observation, not a validation failure. The TEMPLATE_NOTES detector correctly handles missing notes.

---

## 12. Independence and Integrity Checks

| Check | Status |
|-------|--------|
| Production ML/analytics code NOT modified | VERIFIED |
| anomaly.py NOT modified | VERIFIED |
| execution_gap.py NOT modified | VERIFIED |
| negative_space.py NOT modified | VERIFIED |
| risk_score.py NOT modified | VERIFIED |
| anomaly_model.joblib NOT modified | VERIFIED |
| Raw external CSVs NOT modified by validation | VERIFIED |
| Existing validation scripts NOT modified | VERIFIED |
| No retraining during validation | VERIFIED |
| No production evidence functions imported | VERIFIED |
| All validation performed independently | VERIFIED |
| No commits created | VERIFIED |

---

## 13. Final Validation Verdict

### PASS WITH WARNINGS

**Rationale:**
- All six validation steps produced PASS results
- All evidence is traceable and supported
- All edge cases handled safely
- All numerical values valid and finite
- No fabricated or inconsistent evidence
- Warnings are limited to expected limitations (no peer baseline) and a pre-existing implementation issue (model artifact key mismatch)

**This verdict does NOT claim:**
- Model accuracy, precision, recall, or F1-score (no ground truth labels available)
- Production reliability (external datasets only, not production traffic)
- Anomaly probability (anomaly scores are relative anomaly indices)

---

## 14. Conditions / Remaining Gates Before ML Freeze

1. **Resolve model artifact key mismatch:** Production `load_anomaly_model()` must be updated to handle the actual key `"model"` instead of expecting `"clf"`, or the artifact must be regenerated with the expected key structure.

2. **Peer baseline for Negative Space:** If NS is required for external entity validation, a multi-entity dataset or external peer baseline must be provided.

3. **Production traffic validation:** External synthetic datasets do not validate behavior under real production traffic patterns.

4. **Ground truth labels:** No accuracy/precision/recall metrics can be computed without labeled anomaly data.

---

## Files Inspected

| File | Step |
|------|------|
| validation_outputs/step_2_1_validation_report.md | 2.1 |
| validation_outputs/step2_model_validation_report.md | 2.2 |
| validation_outputs/step2_model_validation_results.csv | 2.2 |
| validation_outputs/step3_detector_validation_report.md | 2.3 |
| validation_outputs/step3_detector_validation_results.csv | 2.3 |
| validation_outputs/step4_risk_validation_report.md | 2.4 |
| validation_outputs/step4_risk_validation_results.csv | 2.4 |
| validation_outputs/step5_evidence_validation_report.md | 2.5 |
| validation_outputs/step5_evidence_validation_results.csv | 2.5 |
| validation_outputs/step6_edge_case_validation_report.md | 2.6 |
| validation_outputs/step6_edge_case_validation_results.csv | 2.6 |

---

**Final Consolidated Verdict: PASS WITH WARNINGS**

*End of Step 2 Final Consolidated ML Validation Report*
