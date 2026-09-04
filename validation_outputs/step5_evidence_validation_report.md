======================================================================
STEP 2.5 — INDEPENDENT EVIDENCE TRACEABILITY VALIDATION
======================================================================

Collecting production reference values...
  Equifax: prod_eg=0.514286 prod_ns=0.000000
  JPMorgan Chase: prod_eg=0.530769 prod_ns=0.000000
  MGM Resorts: prod_eg=0.490909 prod_ns=0.000000
  Microsoft: prod_eg=0.525000 prod_ns=0.000000
  T-Mobile: prod_eg=0.450000 prod_ns=0.000000

Production primary drivers loaded:
  Equifax: execution_gap
  JPMorgan Chase: execution_gap
  MGM Resorts: execution_gap
  Microsoft: anomaly
  T-Mobile: execution_gap

======================================================================
VALIDATING: Equifax
======================================================================
  Loaded 100 rows from soc_alerts_equifax.csv

  EG Evidence:
    FAST_CLOSURE: rate=0.0000, refs=0, verified=0, status=SUPPORTED
    NO_ESCALATION: rate=0.7143, refs=10, verified=10, status=SUPPORTED
    TEMPLATE_NOTES: rate=1.0000, refs=100, verified=100, status=SUPPORTED

  NS Evidence:
    LOW_ALERT_VOLUME: status=EXPECTED_NO_PEER_BASELINE
    MISSING_EXPECTED_SEVERITY: status=EXPECTED_NO_PEER_BASELINE

  Risk Evidence:
    PRIMARY_DRIVER_EG: status=SUPPORTED

  No fabrication issues detected

  Company Summary:
    Findings checked: 6
    Supported: 4
    Unsupported: 0
    Missing: 0
    Inconsistent: 0
    Expected no-peer-baseline: 2
    Status: PASS

======================================================================
VALIDATING: JPMorgan Chase
======================================================================
  Loaded 100 rows from soc_alerts_jpmorgan_chase.csv

  EG Evidence:
    FAST_CLOSURE: rate=0.0000, refs=0, verified=0, status=SUPPORTED
    NO_ESCALATION: rate=0.7692, refs=10, verified=10, status=SUPPORTED
    TEMPLATE_NOTES: rate=1.0000, refs=100, verified=100, status=SUPPORTED

  NS Evidence:
    LOW_ALERT_VOLUME: status=EXPECTED_NO_PEER_BASELINE
    MISSING_EXPECTED_SEVERITY: status=EXPECTED_NO_PEER_BASELINE

  Risk Evidence:
    PRIMARY_DRIVER_EG: status=SUPPORTED

  No fabrication issues detected

  Company Summary:
    Findings checked: 6
    Supported: 4
    Unsupported: 0
    Missing: 0
    Inconsistent: 0
    Expected no-peer-baseline: 2
    Status: PASS

======================================================================
VALIDATING: MGM Resorts
======================================================================
  Loaded 100 rows from soc_alerts_mgm_resorts.csv

  EG Evidence:
    FAST_CLOSURE: rate=0.0000, refs=0, verified=0, status=SUPPORTED
    NO_ESCALATION: rate=0.6364, refs=7, verified=7, status=SUPPORTED
    TEMPLATE_NOTES: rate=1.0000, refs=100, verified=100, status=SUPPORTED

  NS Evidence:
    LOW_ALERT_VOLUME: status=EXPECTED_NO_PEER_BASELINE
    MISSING_EXPECTED_SEVERITY: status=EXPECTED_NO_PEER_BASELINE

  Risk Evidence:
    PRIMARY_DRIVER_EG: status=SUPPORTED

  No fabrication issues detected

  Company Summary:
    Findings checked: 6
    Supported: 4
    Unsupported: 0
    Missing: 0
    Inconsistent: 0
    Expected no-peer-baseline: 2
    Status: PASS

======================================================================
VALIDATING: Microsoft
======================================================================
  Loaded 100 rows from soc_alerts_microsoft.csv

  EG Evidence:
    FAST_CLOSURE: rate=0.0000, refs=0, verified=0, status=SUPPORTED
    NO_ESCALATION: rate=0.7500, refs=6, verified=6, status=SUPPORTED
    TEMPLATE_NOTES: rate=1.0000, refs=100, verified=100, status=SUPPORTED

  NS Evidence:
    LOW_ALERT_VOLUME: status=EXPECTED_NO_PEER_BASELINE
    MISSING_EXPECTED_SEVERITY: status=EXPECTED_NO_PEER_BASELINE

  Risk Evidence:
    PRIMARY_DRIVER_ANOMALY: status=SUPPORTED

  No fabrication issues detected

  Company Summary:
    Findings checked: 6
    Supported: 4
    Unsupported: 0
    Missing: 0
    Inconsistent: 0
    Expected no-peer-baseline: 2
    Status: PASS

======================================================================
VALIDATING: T-Mobile
======================================================================
  Loaded 100 rows from soc_alerts_t-mobile.csv

  EG Evidence:
    FAST_CLOSURE: rate=0.0000, refs=0, verified=0, status=SUPPORTED
    NO_ESCALATION: rate=0.5000, refs=5, verified=5, status=SUPPORTED
    TEMPLATE_NOTES: rate=1.0000, refs=100, verified=100, status=SUPPORTED

  NS Evidence:
    LOW_ALERT_VOLUME: status=EXPECTED_NO_PEER_BASELINE
    MISSING_EXPECTED_SEVERITY: status=EXPECTED_NO_PEER_BASELINE

  Risk Evidence:
    PRIMARY_DRIVER_EG: status=SUPPORTED

  No fabrication issues detected

  Company Summary:
    Findings checked: 6
    Supported: 4
    Unsupported: 0
    Missing: 0
    Inconsistent: 0
    Expected no-peer-baseline: 2
    Status: PASS

======================================================================
A. VALIDATION OBJECTIVE
======================================================================
Independently verify that every reported finding/reason has valid
supporting evidence that actually exists in the raw external dataset
or is legitimately derived from peer-level evidence.

======================================================================
B. DATASETS TESTED
======================================================================
| Company | File | Rows |
|---------|------|------|
| Equifax | soc_alerts_equifax.csv | 100 |
| JPMorgan Chase | soc_alerts_jpmorgan_chase.csv | 100 |
| MGM Resorts | soc_alerts_mgm_resorts.csv | 100 |
| Microsoft | soc_alerts_microsoft.csv | 100 |
| T-Mobile | soc_alerts_t-mobile.csv | 100 |

======================================================================
C. EVIDENCE VALIDATION RULES
======================================================================
- SUPPORTED: evidence can be directly traced to valid raw data
- UNSUPPORTED: evidence claims something unverifiable from available data
- MISSING: finding exists but supporting evidence is absent
- INCONSISTENT: evidence exists but does not support the claimed reason
- EXPECTED_NO_PEER_BASELINE: NS cannot be established (single-entity dataset)

======================================================================
D. EXECUTION GAP EVIDENCE VALIDATION
======================================================================

### Equifax
  FAST_CLOSURE:
    Reason: Fast closure rate: 0.0000 (0 hits / 30 candidates)
    Evidence refs: 0
    Verified count: 0
    Status: SUPPORTED
    Notes: No fast-closure hits found (expected for zero-rate finding)
  NO_ESCALATION:
    Reason: No-escalation rate: 0.7143 (10 hits / 14 candidates)
    Evidence refs: 10
    Verified count: 10
    Status: SUPPORTED
  TEMPLATE_NOTES:
    Reason: Template-notes rate: 1.0000 (100 hits / 100 total)
    Evidence refs: 100
    Verified count: 100
    Status: SUPPORTED

### JPMorgan Chase
  FAST_CLOSURE:
    Reason: Fast closure rate: 0.0000 (0 hits / 22 candidates)
    Evidence refs: 0
    Verified count: 0
    Status: SUPPORTED
    Notes: No fast-closure hits found (expected for zero-rate finding)
  NO_ESCALATION:
    Reason: No-escalation rate: 0.7692 (10 hits / 13 candidates)
    Evidence refs: 10
    Verified count: 10
    Status: SUPPORTED
  TEMPLATE_NOTES:
    Reason: Template-notes rate: 1.0000 (100 hits / 100 total)
    Evidence refs: 100
    Verified count: 100
    Status: SUPPORTED

### MGM Resorts
  FAST_CLOSURE:
    Reason: Fast closure rate: 0.0000 (0 hits / 27 candidates)
    Evidence refs: 0
    Verified count: 0
    Status: SUPPORTED
    Notes: No fast-closure hits found (expected for zero-rate finding)
  NO_ESCALATION:
    Reason: No-escalation rate: 0.6364 (7 hits / 11 candidates)
    Evidence refs: 7
    Verified count: 7
    Status: SUPPORTED
  TEMPLATE_NOTES:
    Reason: Template-notes rate: 1.0000 (100 hits / 100 total)
    Evidence refs: 100
    Verified count: 100
    Status: SUPPORTED

### Microsoft
  FAST_CLOSURE:
    Reason: Fast closure rate: 0.0000 (0 hits / 18 candidates)
    Evidence refs: 0
    Verified count: 0
    Status: SUPPORTED
    Notes: No fast-closure hits found (expected for zero-rate finding)
  NO_ESCALATION:
    Reason: No-escalation rate: 0.7500 (6 hits / 8 candidates)
    Evidence refs: 6
    Verified count: 6
    Status: SUPPORTED
  TEMPLATE_NOTES:
    Reason: Template-notes rate: 1.0000 (100 hits / 100 total)
    Evidence refs: 100
    Verified count: 100
    Status: SUPPORTED

### T-Mobile
  FAST_CLOSURE:
    Reason: Fast closure rate: 0.0000 (0 hits / 27 candidates)
    Evidence refs: 0
    Verified count: 0
    Status: SUPPORTED
    Notes: No fast-closure hits found (expected for zero-rate finding)
  NO_ESCALATION:
    Reason: No-escalation rate: 0.5000 (5 hits / 10 candidates)
    Evidence refs: 5
    Verified count: 5
    Status: SUPPORTED
  TEMPLATE_NOTES:
    Reason: Template-notes rate: 1.0000 (100 hits / 100 total)
    Evidence refs: 100
    Verified count: 100
    Status: SUPPORTED

======================================================================
E. NEGATIVE SPACE EVIDENCE VALIDATION
======================================================================

### Equifax
  LOW_ALERT_VOLUME:
    Reason: Single-entity dataset: no peer baseline available
    Status: EXPECTED_NO_PEER_BASELINE
    Notes: External dataset contains only one entity; peer comparison not applicable
  MISSING_EXPECTED_SEVERITY:
    Reason: Single-entity dataset: no peer baseline available
    Status: EXPECTED_NO_PEER_BASELINE
    Notes: External dataset contains only one entity; peer comparison not applicable

### JPMorgan Chase
  LOW_ALERT_VOLUME:
    Reason: Single-entity dataset: no peer baseline available
    Status: EXPECTED_NO_PEER_BASELINE
    Notes: External dataset contains only one entity; peer comparison not applicable
  MISSING_EXPECTED_SEVERITY:
    Reason: Single-entity dataset: no peer baseline available
    Status: EXPECTED_NO_PEER_BASELINE
    Notes: External dataset contains only one entity; peer comparison not applicable

### MGM Resorts
  LOW_ALERT_VOLUME:
    Reason: Single-entity dataset: no peer baseline available
    Status: EXPECTED_NO_PEER_BASELINE
    Notes: External dataset contains only one entity; peer comparison not applicable
  MISSING_EXPECTED_SEVERITY:
    Reason: Single-entity dataset: no peer baseline available
    Status: EXPECTED_NO_PEER_BASELINE
    Notes: External dataset contains only one entity; peer comparison not applicable

### Microsoft
  LOW_ALERT_VOLUME:
    Reason: Single-entity dataset: no peer baseline available
    Status: EXPECTED_NO_PEER_BASELINE
    Notes: External dataset contains only one entity; peer comparison not applicable
  MISSING_EXPECTED_SEVERITY:
    Reason: Single-entity dataset: no peer baseline available
    Status: EXPECTED_NO_PEER_BASELINE
    Notes: External dataset contains only one entity; peer comparison not applicable

### T-Mobile
  LOW_ALERT_VOLUME:
    Reason: Single-entity dataset: no peer baseline available
    Status: EXPECTED_NO_PEER_BASELINE
    Notes: External dataset contains only one entity; peer comparison not applicable
  MISSING_EXPECTED_SEVERITY:
    Reason: Single-entity dataset: no peer baseline available
    Status: EXPECTED_NO_PEER_BASELINE
    Notes: External dataset contains only one entity; peer comparison not applicable

======================================================================
F. RISK / PRIMARY DRIVER EVIDENCE VALIDATION
======================================================================

### Equifax
  Primary driver: execution_gap
  PRIMARY_DRIVER_EG:
    Reason: Primary driver is execution_gap; EG findings exist: True
    Status: SUPPORTED

### JPMorgan Chase
  Primary driver: execution_gap
  PRIMARY_DRIVER_EG:
    Reason: Primary driver is execution_gap; EG findings exist: True
    Status: SUPPORTED

### MGM Resorts
  Primary driver: execution_gap
  PRIMARY_DRIVER_EG:
    Reason: Primary driver is execution_gap; EG findings exist: True
    Status: SUPPORTED

### Microsoft
  Primary driver: anomaly
  PRIMARY_DRIVER_ANOMALY:
    Reason: Primary driver is anomaly; raw_score=0.027829, valid=True
    Status: SUPPORTED

### T-Mobile
  Primary driver: execution_gap
  PRIMARY_DRIVER_EG:
    Reason: Primary driver is execution_gap; EG findings exist: True
    Status: SUPPORTED

======================================================================
G. COMPANY-WISE RESULTS
======================================================================
| Company | Findings | Supported | Unsupported | Missing | Inconsistent | Expected No-Peer | Status |
|---------|----------|-----------|-------------|---------|--------------|------------------|--------|
| Equifax | 6 | 4 | 0 | 0 | 0 | 2 | PASS |
| JPMorgan Chase | 6 | 4 | 0 | 0 | 0 | 2 | PASS |
| MGM Resorts | 6 | 4 | 0 | 0 | 0 | 2 | PASS |
| Microsoft | 6 | 4 | 0 | 0 | 0 | 2 | PASS |
| T-Mobile | 6 | 4 | 0 | 0 | 0 | 2 | PASS |

======================================================================
H. UNSUPPORTED / MISSING / INCONSISTENT EVIDENCE
======================================================================
No unsupported, missing, or inconsistent evidence found.

======================================================================
I. NO-FABRICATION CHECKS
======================================================================
No fabrication issues detected.
- All alert IDs verified as existing in raw CSV
- All entity names verified as matching company
- All severity values verified as present
- All closure durations verified as traceable
- No evidence referencing another company
- No evidence contradicting raw CSV
- No evidence count exceeding actual records

======================================================================
J. INDEPENDENCE / NON-MODIFICATION PROOF
======================================================================
- Production ML/analytics code: NOT modified
- Detector code: NOT modified
- anomaly_model.joblib: NOT modified (read-only load)
- Raw external CSVs: NOT modified
- Existing validation scripts: NOT modified
- No retraining performed
- No production evidence function imported/reused
- Evidence verification performed independently
- No commits created

======================================================================
K. OVERALL VERDICT
======================================================================

Datasets tested: 5
Findings checked: 30
Supported evidence: 20
Unsupported evidence: 0
Missing evidence: 0
Inconsistent evidence: 0
Expected no-peer-baseline: 10
No-fabrication checks: PASS

FINAL VERDICT: PASS