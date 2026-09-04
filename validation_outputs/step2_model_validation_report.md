======================================================================
STEP 2.2 — MODEL VALIDATION
======================================================================

## 1. Model File
  Path: C:\Users\dell\SIH26157-SAT-SA\backend\anomaly_model.joblib
  Exists: True

## 2. Load Model
  Loaded: OK

## 3. Model Structure
  Type: dict
  Keys: ['clf', 'feature_names', 'scaler']
    clf: IsolationForest
      n_estimators=100
      contamination=0.2
      random_state=42
      n_features_in_=6
    feature_names: list
    scaler: StandardScaler
      n_features_in_=6
  Scaler type: StandardScaler
    n_features_in_: 6
    mean_: [6.39000000e+01 1.05540993e+04 3.77445148e-01 1.12079357e-01
 6.23745535e+01 5.70000000e+00]
    scale_: [3.83000000e+01 5.20811133e+03 1.69874436e-01 4.80655244e-02
 1.96653355e+01 9.00000000e-01]
  Estimator type: IsolationForest
  Feature order: ['alert_count', 'avg_closure_seconds', 'escalation_rate', 'critical_ratio', 'avg_note_length', 'unique_asset_types']

## 4. Feature Computation (independent)
  Equifax: OK  {'alert_count': 100.0, 'avg_closure_seconds': 13120.2532, 'escalation_rate': 0.25, 'critical_ratio': 0.14, 'avg_note_length': 49.41, 'unique_asset_types': 6.0}
  JPMorgan Chase: OK  {'alert_count': 100.0, 'avg_closure_seconds': 12050.2326, 'escalation_rate': 0.38, 'critical_ratio': 0.13, 'avg_note_length': 46.96, 'unique_asset_types': 6.0}
  MGM Resorts: OK  {'alert_count': 100.0, 'avg_closure_seconds': 13026.7416, 'escalation_rate': 0.28, 'critical_ratio': 0.11, 'avg_note_length': 45.07, 'unique_asset_types': 6.0}
  Microsoft: OK  {'alert_count': 100.0, 'avg_closure_seconds': 11510.5263, 'escalation_rate': 0.3, 'critical_ratio': 0.08, 'avg_note_length': 50.6, 'unique_asset_types': 6.0}
  T-Mobile: OK  {'alert_count': 100.0, 'avg_closure_seconds': 11756.9231, 'escalation_rate': 0.32, 'critical_ratio': 0.1, 'avg_note_length': 48.26, 'unique_asset_types': 6.0}

## 5. Feature Shape & Sanity
  Equifax: len=6 numeric=True nan=False inf=False vec=[100.0, 13120.2532, 0.25, 0.14, 49.41, 6.0]
  JPMorgan Chase: len=6 numeric=True nan=False inf=False vec=[100.0, 12050.2326, 0.38, 0.13, 46.96, 6.0]
  MGM Resorts: len=6 numeric=True nan=False inf=False vec=[100.0, 13026.7416, 0.28, 0.11, 45.07, 6.0]
  Microsoft: len=6 numeric=True nan=False inf=False vec=[100.0, 11510.5263, 0.3, 0.08, 50.6, 6.0]
  T-Mobile: len=6 numeric=True nan=False inf=False vec=[100.0, 11756.9231, 0.32, 0.1, 48.26, 6.0]

## 6. Model Inference
  Scaler.transform: OK
  decision_function output shape: (5,)
  decision_function output type: <class 'numpy.ndarray'>
  raw scores: {'Equifax': 0.055162, 'JPMorgan Chase': 0.055758, 'MGM Resorts': 0.05554, 'Microsoft': 0.027829, 'T-Mobile': 0.053579}
  Score conversion: min_raw=-0.055758 max_raw=-0.027829 spread=0.027929
  converted scores: {'Equifax': 0.0214, 'JPMorgan Chase': 0.0, 'MGM Resorts': 0.0078, 'Microsoft': 1.0, 'T-Mobile': 0.078}

## 7. Score Sanity
  Equifax: raw=0.055162  converted=0.0214
  JPMorgan Chase: raw=0.055758  converted=0.0000
  MGM Resorts: raw=0.055540  converted=0.0078
  Microsoft: raw=0.027829  converted=1.0000
  T-Mobile: raw=0.053579  converted=0.0780

## 8. Pipeline Consistency
  Scaler present: True
  Scaler type: StandardScaler
  Estimator type: IsolationForest
  Feature names in artifact: ['alert_count', 'avg_closure_seconds', 'escalation_rate', 'critical_ratio', 'avg_note_length', 'unique_asset_types']
  Features used for inference: ['alert_count', 'avg_closure_seconds', 'escalation_rate', 'critical_ratio', 'avg_note_length', 'unique_asset_types']

======================================================================
VERDICT
======================================================================

  Final Verdict: PASS
  Model loading: PASS
  Model structure: PASS
  Feature input: PASS
  Inference: PASS
  Score sanity: PASS

======================================================================
PROOF OF INDEPENDENCE
======================================================================
  - Production ML/analytics code NOT modified
  - anomaly_model.joblib NOT modified (read-only load)
  - Raw CSVs NOT modified
  - No production feature function imported for computing validation features
  - No model retraining performed
  - No commits created