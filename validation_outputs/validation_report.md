# Disha ML Validation Report

**Final Verdict: PASS WITH WARNINGS**

## 1. Dataset Validation
- **Required columns: PASS** — all present
- **Row count: PASS** — 639 rows; expected 639
- **Entity count: PASS** — 10 entities; expected 10
- **Duplicate alert_id: PASS** — 0 duplicates
- **Blank entity_name: PASS** — 0 blank rows
- **Missing severity: PASS** — 0 missing
- **Missing closure_duration_minutes: PASS** — 0 missing
- **Missing escalated: PASS** — 0 missing
- **Missing investigation_notes: PASS** — 0 missing
- **Negative closure duration: PASS** — 0 negative values
- **Invalid closure duration: PASS** — 0 non-numeric values
- **Invalid created_time: PASS** — 0 invalid timestamps
- **Invalid closed_time: PASS** — 0 invalid timestamps
- **closed_time before created_time: PASS** — 0 rows
- **Unexpected severity values: PASS** — none
- **Unexpected escalated values: PASS** — none
- **Entity case/spelling variants: PASS** — 0 case-insensitive groups have variants

## 2. Independent Features

Generated `disha_independent_features.csv` independently from raw CSV.

## 3. Feature Comparison
- WARNING: No Kriza feature-output CSV found; independent feature calculation generated but not compared.

## 4. Isolation Forest Ranking Stability
- **PASS WITH WARNING** — Top-3 ranking is stable; lower ranks shifted
- A: Delta Rail Systems > Indus Financial Services > Continental Banking Corp > Fortis Defense Systems > Ganga Oil & Gas > Bharat Telecom Networks > Himalayan Healthcare Network > Eastern Water Utility > Jupiter Aviation Control > Apex Power Grid Ltd
- B: Delta Rail Systems > Indus Financial Services > Continental Banking Corp > Fortis Defense Systems > Ganga Oil & Gas > Bharat Telecom Networks > Himalayan Healthcare Network > Eastern Water Utility > Jupiter Aviation Control > Apex Power Grid Ltd
- C: Delta Rail Systems > Indus Financial Services > Continental Banking Corp > Fortis Defense Systems > Ganga Oil & Gas > Bharat Telecom Networks > Himalayan Healthcare Network > Eastern Water Utility > Jupiter Aviation Control > Apex Power Grid Ltd
- D: Delta Rail Systems > Indus Financial Services > Continental Banking Corp > Fortis Defense Systems > Ganga Oil & Gas > Bharat Telecom Networks > Himalayan Healthcare Network > Eastern Water Utility > Apex Power Grid Ltd > Jupiter Aviation Control
- E: Delta Rail Systems > Indus Financial Services > Continental Banking Corp > Fortis Defense Systems > Ganga Oil & Gas > Bharat Telecom Networks > Himalayan Healthcare Network > Eastern Water Utility > Apex Power Grid Ltd > Jupiter Aviation Control

## 5. Execution Gap Evidence
- {'status': 'WARNING', 'message': 'No saved Execution Gap evidence file found; evidence trace skipped.'}

## 6. Negative Space
- Apex Power Grid Ltd: count=65, peer_mean=63.78, peer_std=42.82, z=0.029, low_volume=False, missing=[]
- Bharat Telecom Networks: count=50, peer_mean=65.44, peer_std=42.51, z=-0.363, low_volume=False, missing=[]
- Continental Banking Corp: count=65, peer_mean=63.78, peer_std=42.82, z=0.029, low_volume=False, missing=[]
- Delta Rail Systems: count=3, peer_mean=70.67, peer_std=36.31, z=-1.864, low_volume=True, missing=['critical', 'high']
- Eastern Water Utility: count=57, peer_mean=64.67, peer_std=42.74, z=-0.179, low_volume=False, missing=[]
- Fortis Defense Systems: count=166, peer_mean=52.56, peer_std=19.64, z=5.776, low_volume=False, missing=[]
- Ganga Oil & Gas: count=53, peer_mean=65.11, peer_std=42.63, z=-0.284, low_volume=False, missing=[]
- Himalayan Healthcare Network: count=68, peer_mean=63.44, peer_std=42.79, z=0.106, low_volume=False, missing=[]
- Indus Financial Services: count=60, peer_mean=64.33, peer_std=42.8, z=-0.101, low_volume=False, missing=[]
- Jupiter Aviation Control: count=52, peer_mean=65.22, peer_std=42.59, z=-0.31, low_volume=False, missing=[]

## 7. Data Quality
- Covered by dataset validation checks above.

## 8. Risk Score Verification
- {'status': 'WARNING', 'message': 'No saved risk_scores.csv found; risk arithmetic could not be compared automatically.'}

## 9. End-to-End Validation
- Independent feature generation completed.
- A-E Isolation Forest experiments completed.
- Saved production outputs were compared when available.

## 10. Final Verdict
**PASS WITH WARNINGS**

## 11. Issues For Kriza
- Review every FAIL/WARNING above; this validator reports issues and does not modify analytics code.