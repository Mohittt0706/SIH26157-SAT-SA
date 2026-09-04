======================================================================
STEP 2.6 - INDEPENDENT EDGE-CASE TESTING
======================================================================
Model: IsolationForest, features: ['alert_count', 'avg_closure_seconds', 'escalation_rate', 'critical_ratio', 'avg_note_length', 'unique_asset_types']

======================================================================
COMPANY: Equifax
======================================================================
Loaded 100 rows
  [PASS] MISSING_NOTES: blank investigation_notes
  [PASS] MISSING_NOTES: very short notes (<20 chars)
  [PASS] MISSING_CLOSED_TIME: some alerts with no closed_time
  [PASS] MISSING_CLOSURE_DURATION: closure_duration_minutes blank
  [PASS] NO_CRITICAL_ALERTS: in-memory scenario with zero critical alerts
  [PASS] NO_ESCALATED: zero escalated alerts
  [PASS] LOW_VOLUME: only 3 alerts in dataset
  [PASS] ASSET_TYPES: verify different asset_type values handled
  [PASS] INCOMPLETE_RECORDS: missing optional fields + open alerts
  [PASS] EXTREME_ANOMALY: extreme feature values fed to model
  [PASS] ZERO_FEATURES: all-zero feature vector

======================================================================
COMPANY: JPMorgan Chase
======================================================================
Loaded 100 rows
  [PASS] MISSING_NOTES: blank investigation_notes
  [PASS] MISSING_NOTES: very short notes (<20 chars)
  [PASS] MISSING_CLOSED_TIME: some alerts with no closed_time
  [PASS] MISSING_CLOSURE_DURATION: closure_duration_minutes blank
  [PASS] NO_CRITICAL_ALERTS: in-memory scenario with zero critical alerts
  [PASS] NO_ESCALATED: zero escalated alerts
  [PASS] LOW_VOLUME: only 3 alerts in dataset
  [PASS] ASSET_TYPES: verify different asset_type values handled
  [PASS] INCOMPLETE_RECORDS: missing optional fields + open alerts
  [PASS] EXTREME_ANOMALY: extreme feature values fed to model
  [PASS] ZERO_FEATURES: all-zero feature vector

======================================================================
COMPANY: MGM Resorts
======================================================================
Loaded 100 rows
  [PASS] MISSING_NOTES: blank investigation_notes
  [PASS] MISSING_NOTES: very short notes (<20 chars)
  [PASS] MISSING_CLOSED_TIME: some alerts with no closed_time
  [PASS] MISSING_CLOSURE_DURATION: closure_duration_minutes blank
  [PASS] NO_CRITICAL_ALERTS: in-memory scenario with zero critical alerts
  [PASS] NO_ESCALATED: zero escalated alerts
  [PASS] LOW_VOLUME: only 3 alerts in dataset
  [PASS] ASSET_TYPES: verify different asset_type values handled
  [PASS] INCOMPLETE_RECORDS: missing optional fields + open alerts
  [PASS] EXTREME_ANOMALY: extreme feature values fed to model
  [PASS] ZERO_FEATURES: all-zero feature vector

======================================================================
COMPANY: Microsoft
======================================================================
Loaded 100 rows
  [PASS] MISSING_NOTES: blank investigation_notes
  [PASS] MISSING_NOTES: very short notes (<20 chars)
  [PASS] MISSING_CLOSED_TIME: some alerts with no closed_time
  [PASS] MISSING_CLOSURE_DURATION: closure_duration_minutes blank
  [PASS] NO_CRITICAL_ALERTS: in-memory scenario with zero critical alerts
  [PASS] NO_ESCALATED: zero escalated alerts
  [PASS] LOW_VOLUME: only 3 alerts in dataset
  [PASS] ASSET_TYPES: verify different asset_type values handled
  [PASS] INCOMPLETE_RECORDS: missing optional fields + open alerts
  [PASS] EXTREME_ANOMALY: extreme feature values fed to model
  [PASS] ZERO_FEATURES: all-zero feature vector

======================================================================
COMPANY: T-Mobile
======================================================================
Loaded 100 rows
  [PASS] MISSING_NOTES: blank investigation_notes
  [PASS] MISSING_NOTES: very short notes (<20 chars)
  [PASS] MISSING_CLOSED_TIME: some alerts with no closed_time
  [PASS] MISSING_CLOSURE_DURATION: closure_duration_minutes blank
  [PASS] NO_CRITICAL_ALERTS: in-memory scenario with zero critical alerts
  [PASS] NO_ESCALATED: zero escalated alerts
  [PASS] LOW_VOLUME: only 3 alerts in dataset
  [PASS] ASSET_TYPES: verify different asset_type values handled
  [PASS] INCOMPLETE_RECORDS: missing optional fields + open alerts
  [PASS] EXTREME_ANOMALY: extreme feature values fed to model
  [PASS] ZERO_FEATURES: all-zero feature vector

======================================================================
COMPANY-WISE SUMMARY
======================================================================
  Equifax: 11 tests, 11 PASS, 0 FAIL
  JPMorgan Chase: 11 tests, 11 PASS, 0 FAIL
  MGM Resorts: 11 tests, 11 PASS, 0 FAIL
  Microsoft: 11 tests, 11 PASS, 0 FAIL
  T-Mobile: 11 tests, 11 PASS, 0 FAIL

======================================================================
NUMERICAL SAFETY CHECKS
======================================================================
  All values finite: PASS
  All logic valid: PASS

======================================================================
INDEPENDENCE AND NON-MODIFICATION PROOF
======================================================================
- Production code: NOT modified
- anomaly_model.joblib: NOT modified
- Raw CSVs: NOT modified
- No retraining performed
- All tests use in-memory copies

======================================================================
OVERALL VERDICT
======================================================================

Step 2.6 Edge-Case Testing
Datasets tested: 5
Edge cases tested: 55
PASS: 55
WARN: 0
FAIL: 0
Numerical safety: PASS
Detector logic safety: PASS
Raw datasets modified: NO
Production code modified: NO
Overall verdict: PASS