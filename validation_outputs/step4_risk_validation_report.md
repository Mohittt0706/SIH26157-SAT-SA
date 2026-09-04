======================================================================
STEP 2.4 — INDEPENDENT RISK SCORE VALIDATION
======================================================================

Model loaded: IsolationForest (n_estimators=100, contamination=0.2)
Scaler: StandardScaler
Feature order: ['alert_count', 'avg_closure_seconds', 'escalation_rate', 'critical_ratio', 'avg_note_length', 'unique_asset_types']
Weights: EG=0.4, NS=0.35, Anomaly=0.25 (sum=1.0)
Soft floor attenuation: 0.85
Bands: >= 70.0 critical, >= 45.0 high, >= 20.0 medium, < 20.0 low
Tolerance: 1e-06

Collecting production reference values...
  Equifax: prod_eg=0.514286 prod_ns=0.000000
  JPMorgan Chase: prod_eg=0.530769 prod_ns=0.000000
  MGM Resorts: prod_eg=0.490909 prod_ns=0.000000
  Microsoft: prod_eg=0.525000 prod_ns=0.000000
  T-Mobile: prod_eg=0.450000 prod_ns=0.000000

Running independent calculations...

======================================================================
A. VALIDATION OBJECTIVE
======================================================================
Independently verify production risk-score outputs for 5 external datasets.
No production risk function is imported. All risk math implemented here.

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
C. RISK FORMULA VERIFIED
======================================================================
weighted_score = 0.40 * EG + 0.35 * NS + 0.25 * A
highest_detector = max(EG, NS, A)
soft_floor = highest_detector * 0.85
final_score = max(weighted_score, soft_floor)
final_score = clamp(final_score, 0, 1)
risk_score = final_score * 100
Bands: >= 70.0 critical, >= 45.0 high, >= 20.0 medium, < 20.0 low

======================================================================
D. SOFT-FLOOR VERIFICATION
======================================================================
| Company | Weighted | Soft Floor | Final | Floor Active? | Diff |
|---------|----------|------------|-------|---------------|------|
| Equifax | 0.2111 | 0.4371 | 43.7 | YES | 22.6 |
| JPMorgan Chase | 0.2123 | 0.4512 | 45.1 | YES | 23.9 |
| MGM Resorts | 0.1983 | 0.4173 | 41.7 | YES | 21.9 |
| Microsoft | 0.4600 | 0.8500 | 85.0 | YES | 39.0 |
| T-Mobile | 0.1995 | 0.3825 | 38.2 | YES | 18.2 |

======================================================================
E. RISK BAND VERIFICATION
======================================================================
| Company | Final Score | Indep Band | Prod Band | Match |
|---------|-------------|------------|-----------|-------|
| Equifax | 43.7 | medium | medium | YES |
| JPMorgan Chase | 45.1 | high | high | YES |
| MGM Resorts | 41.7 | medium | medium | YES |
| Microsoft | 85.0 | critical | critical | YES |
| T-Mobile | 38.2 | medium | medium | YES |

======================================================================
F. PRIMARY DRIVER VERIFICATION
======================================================================
| Company | EG Contrib | NS Contrib | Anom Contrib | Indep Driver | Prod Driver | Match |
|---------|-----------|-----------|-------------|--------------|-------------|-------|
| Equifax | 0.2057 | 0.0000 | 0.0053 | execution_gap | execution_gap | YES |
| JPMorgan Chase | 0.2123 | 0.0000 | 0.0000 | execution_gap | execution_gap | YES |
| MGM Resorts | 0.1964 | 0.0000 | 0.0020 | execution_gap | execution_gap | YES |
| Microsoft | 0.2100 | 0.0000 | 0.2500 | anomaly | anomaly | YES |
| T-Mobile | 0.1800 | 0.0000 | 0.0195 | execution_gap | execution_gap | YES |

======================================================================
G. COMPANY-WISE VALIDATION RESULTS
======================================================================

### Equifax
| Field | Production | Independent | Diff | Status |
|-------|-----------|-------------|------|--------|
| EG score | 0.514286 | 0.514286 | 0.000000 | MATCH |
| NS score | 0.000000 | 0.000000 | 0.000000 | MATCH |
| Anomaly score | 0.021352 | 0.021352 | 0.000000 | MATCH |
| Weighted score | 0.211052 | 0.211052 | 0.000000 | MATCH |
| Soft floor | 0.437143 | 0.437143 | 0.000000 | MATCH |
| Final score | 43.7 | 43.7 | 0.0 | MATCH |
| Risk band | medium | medium | - | MATCH |
| Primary driver | execution_gap | execution_gap | - | MATCH |
| Soft floor active | True | True | - | MATCH |
| **Overall** | | | | **PASS** |

### JPMorgan Chase
| Field | Production | Independent | Diff | Status |
|-------|-----------|-------------|------|--------|
| EG score | 0.530769 | 0.530769 | 0.000000 | MATCH |
| NS score | 0.000000 | 0.000000 | 0.000000 | MATCH |
| Anomaly score | 0.000000 | 0.000000 | 0.000000 | MATCH |
| Weighted score | 0.212308 | 0.212308 | 0.000000 | MATCH |
| Soft floor | 0.451154 | 0.451154 | 0.000000 | MATCH |
| Final score | 45.1 | 45.1 | 0.0 | MATCH |
| Risk band | high | high | - | MATCH |
| Primary driver | execution_gap | execution_gap | - | MATCH |
| Soft floor active | True | True | - | MATCH |
| **Overall** | | | | **PASS** |

### MGM Resorts
| Field | Production | Independent | Diff | Status |
|-------|-----------|-------------|------|--------|
| EG score | 0.490909 | 0.490909 | 0.000000 | MATCH |
| NS score | 0.000000 | 0.000000 | 0.000000 | MATCH |
| Anomaly score | 0.007808 | 0.007808 | 0.000000 | MATCH |
| Weighted score | 0.198316 | 0.198316 | 0.000000 | MATCH |
| Soft floor | 0.417273 | 0.417273 | 0.000000 | MATCH |
| Final score | 41.7 | 41.7 | 0.0 | MATCH |
| Risk band | medium | medium | - | MATCH |
| Primary driver | execution_gap | execution_gap | - | MATCH |
| Soft floor active | True | True | - | MATCH |
| **Overall** | | | | **PASS** |

### Microsoft
| Field | Production | Independent | Diff | Status |
|-------|-----------|-------------|------|--------|
| EG score | 0.525000 | 0.525000 | 0.000000 | MATCH |
| NS score | 0.000000 | 0.000000 | 0.000000 | MATCH |
| Anomaly score | 1.000000 | 1.000000 | 0.000000 | MATCH |
| Weighted score | 0.460000 | 0.460000 | 0.000000 | MATCH |
| Soft floor | 0.850000 | 0.850000 | 0.000000 | MATCH |
| Final score | 85.0 | 85.0 | 0.0 | MATCH |
| Risk band | critical | critical | - | MATCH |
| Primary driver | anomaly | anomaly | - | MATCH |
| Soft floor active | True | True | - | MATCH |
| **Overall** | | | | **PASS** |

### T-Mobile
| Field | Production | Independent | Diff | Status |
|-------|-----------|-------------|------|--------|
| EG score | 0.450000 | 0.450000 | 0.000000 | MATCH |
| NS score | 0.000000 | 0.000000 | 0.000000 | MATCH |
| Anomaly score | 0.078023 | 0.078023 | 0.000000 | MATCH |
| Weighted score | 0.199506 | 0.199506 | 0.000000 | MATCH |
| Soft floor | 0.382500 | 0.382500 | 0.000000 | MATCH |
| Final score | 38.2 | 38.2 | 0.0 | MATCH |
| Risk band | medium | medium | - | MATCH |
| Primary driver | execution_gap | execution_gap | - | MATCH |
| Soft floor active | True | True | - | MATCH |
| **Overall** | | | | **PASS** |

======================================================================
H. MISMATCH ANALYSIS
======================================================================
No mismatches detected.

======================================================================
I. SANITY CHECKS
======================================================================
  Equifax: ALL PASS
  JPMorgan Chase: ALL PASS
  MGM Resorts: ALL PASS
  Microsoft: ALL PASS
  T-Mobile: ALL PASS

  Overall sanity: PASS

======================================================================
J. INDEPENDENCE / NON-MODIFICATION PROOF
======================================================================
- Production ML/analytics code: NOT modified
- Detector code: NOT modified
- anomaly_model.joblib: NOT modified (read-only load)
- Raw external CSVs: NOT modified
- Existing validation scripts: NOT modified
- No retraining performed
- No production risk function imported
- Risk formula independently implemented
- No commits created

======================================================================
K. OVERALL VERDICT
======================================================================

FINAL VERDICT: PASS