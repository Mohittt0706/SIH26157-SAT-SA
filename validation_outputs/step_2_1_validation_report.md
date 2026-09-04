# Disha Step 2.1 — Dataset & Feature Validation Report

**Validation Type:** Independent read-only dataset validation
**Datasets Validated:** 5 external company CSVs
**Rule:** No data modified, no code changes, no model retraining

## 1. Dataset Availability

| Company | File | Exists | Readable | Status |
|---------|------|--------|----------|--------|
| Equifax | soc_alerts_equifax.csv | Yes | Yes | PASS |
| JPMorgan Chase | soc_alerts_jpmorgan_chase.csv | Yes | Yes | PASS |
| MGM Resorts | soc_alerts_mgm_resorts.csv | Yes | Yes | PASS |
| Microsoft | soc_alerts_microsoft.csv | Yes | Yes | PASS |
| T-Mobile | soc_alerts_t-mobile.csv | Yes | Yes | PASS |

## 2. Row Counts

| Company | Header Line | Data Rows | Total Lines | Expected Data Rows | Status |
|---------|-------------|-----------|-------------|-------------------|--------|
| Equifax | 1 | 100 | 101 | 100 | PASS |
| JPMorgan Chase | 1 | 100 | 101 | 100 | PASS |
| MGM Resorts | 1 | 100 | 101 | 100 | PASS |
| Microsoft | 1 | 100 | 101 | 100 | PASS |
| T-Mobile | 1 | 100 | 101 | 100 | PASS |

## 3. Schema Validation

| Company | Columns Found | Column Order Match | Missing Columns | Extra Columns | Status |
|---------|--------------|--------------------|-----------------|---------------|--------|
| Equifax | 11 | Yes | None | None | PASS |
| JPMorgan Chase | 11 | Yes | None | None | PASS |
| MGM Resorts | 11 | Yes | None | None | PASS |
| Microsoft | 11 | Yes | None | None | PASS |
| T-Mobile | 11 | Yes | None | None | PASS |

## 4. Duplicate Alert ID Validation

| Company | Total Rows | Unique Alert IDs | Duplicate Count | Duplicate IDs | Status |
|---------|-----------|-----------------|-----------------|---------------|--------|
| Equifax | 100 | 100 | 0 | None | PASS |
| JPMorgan Chase | 100 | 100 | 0 | None | PASS |
| MGM Resorts | 100 | 100 | 0 | None | PASS |
| Microsoft | 100 | 100 | 0 | None | PASS |
| T-Mobile | 100 | 100 | 0 | None | PASS |

## 5. Entity Consistency

| Company | Expected Entity | Distinct Entity Names | Status |
|---------|----------------|----------------------|--------|
| Equifax | Equifax | {'Equifax'} | PASS |
| JPMorgan Chase | JPMorgan Chase | {'JPMorgan Chase'} | PASS |
| MGM Resorts | MGM Resorts | {'MGM Resorts'} | PASS |
| Microsoft | Microsoft | {'Microsoft'} | PASS |
| T-Mobile | T-Mobile | {'T-Mobile'} | PASS |

## 6. Categorical Validation

### Field: `severity`

| Company | Distinct Values | Unexpected Values | Status |
|---------|----------------|-------------------|--------|
| Equifax | ['Critical', 'High', 'Low', 'Medium'] | None | PASS |
| JPMorgan Chase | ['Critical', 'High', 'Low', 'Medium'] | None | PASS |
| MGM Resorts | ['Critical', 'High', 'Low', 'Medium'] | None | PASS |
| Microsoft | ['Critical', 'High', 'Low', 'Medium'] | None | PASS |
| T-Mobile | ['Critical', 'High', 'Low', 'Medium'] | None | PASS |

### Field: `escalated`

| Company | Distinct Values | Unexpected Values | Status |
|---------|----------------|-------------------|--------|
| Equifax | ['No', 'Yes'] | None | PASS |
| JPMorgan Chase | ['No', 'Yes'] | None | PASS |
| MGM Resorts | ['No', 'Yes'] | None | PASS |
| Microsoft | ['No', 'Yes'] | None | PASS |
| T-Mobile | ['No', 'Yes'] | None | PASS |

### Field: `status`

| Company | Distinct Values | Unexpected Values | Status |
|---------|----------------|-------------------|--------|
| Equifax | ['Closed', 'In Progress', 'Open'] | None | PASS |
| JPMorgan Chase | ['Closed', 'In Progress', 'Open'] | None | PASS |
| MGM Resorts | ['Closed', 'In Progress', 'Open'] | None | PASS |
| Microsoft | ['Closed', 'In Progress', 'Open'] | None | PASS |
| T-Mobile | ['Closed', 'In Progress', 'Open'] | None | PASS |

### Field: `category`

| Company | Distinct Values | Unexpected Values | Status |
|---------|----------------|-------------------|--------|
| Equifax | ['Credential Stuffing', 'DDoS Attempt', 'Data Exfiltration Attempt', 'Insider Threat Indicator', 'Malware Detection', 'Misconfiguration Alert', 'Phishing Campaign', 'Privilege Escalation', 'Ransomware Indicator', 'Unauthorized Access'] | None | PASS |
| JPMorgan Chase | ['Credential Stuffing', 'DDoS Attempt', 'Data Exfiltration Attempt', 'Insider Threat Indicator', 'Malware Detection', 'Misconfiguration Alert', 'Phishing Campaign', 'Privilege Escalation', 'Ransomware Indicator', 'Unauthorized Access'] | None | PASS |
| MGM Resorts | ['Credential Stuffing', 'DDoS Attempt', 'Data Exfiltration Attempt', 'Insider Threat Indicator', 'Malware Detection', 'Misconfiguration Alert', 'Phishing Campaign', 'Privilege Escalation', 'Ransomware Indicator', 'Unauthorized Access'] | None | PASS |
| Microsoft | ['Credential Stuffing', 'DDoS Attempt', 'Data Exfiltration Attempt', 'Insider Threat Indicator', 'Malware Detection', 'Misconfiguration Alert', 'Phishing Campaign', 'Privilege Escalation', 'Ransomware Indicator', 'Unauthorized Access'] | None | PASS |
| T-Mobile | ['Credential Stuffing', 'DDoS Attempt', 'Data Exfiltration Attempt', 'Insider Threat Indicator', 'Malware Detection', 'Misconfiguration Alert', 'Phishing Campaign', 'Privilege Escalation', 'Ransomware Indicator', 'Unauthorized Access'] | None | PASS |

### Field: `asset_type`

| Company | Distinct Values | Unexpected Values | Status |
|---------|----------------|-------------------|--------|
| Equifax | ['Cloud Storage', 'Database', 'Endpoint', 'Network Device', 'Server', 'Web Application'] | None | PASS |
| JPMorgan Chase | ['Cloud Storage', 'Database', 'Endpoint', 'Network Device', 'Server', 'Web Application'] | None | PASS |
| MGM Resorts | ['Cloud Storage', 'Database', 'Endpoint', 'Network Device', 'Server', 'Web Application'] | None | PASS |
| Microsoft | ['Cloud Storage', 'Database', 'Endpoint', 'Network Device', 'Server', 'Web Application'] | None | PASS |
| T-Mobile | ['Cloud Storage', 'Database', 'Endpoint', 'Network Device', 'Server', 'Web Application'] | None | PASS |

## 7. Timestamp Validation

| Company | Field | Parsed OK | Invalid Count | Invalid IDs | Status |
|---------|-------|-----------|---------------|-------------|--------|
| Equifax | created_time | 100/100 | 0 | None | PASS |
| Equifax | closed_time | 79/79 | 0 | None | PASS |
| JPMorgan Chase | created_time | 100/100 | 0 | None | PASS |
| JPMorgan Chase | closed_time | 86/86 | 0 | None | PASS |
| MGM Resorts | created_time | 100/100 | 0 | None | PASS |
| MGM Resorts | closed_time | 89/89 | 0 | None | PASS |
| Microsoft | created_time | 100/100 | 0 | None | PASS |
| Microsoft | closed_time | 76/76 | 0 | None | PASS |
| T-Mobile | created_time | 100/100 | 0 | None | PASS |
| T-Mobile | closed_time | 78/78 | 0 | None | PASS |

### Reversed Timestamps (closed_time < created_time)

| Company | Reversed Count | Reversed Alert IDs | Status |
|---------|---------------|-------------------|--------|
| Equifax | 0 | None | PASS |
| JPMorgan Chase | 0 | None | PASS |
| MGM Resorts | 0 | None | PASS |
| Microsoft | 0 | None | PASS |
| T-Mobile | 0 | None | PASS |

## 8. Closure Duration Validation

| Company | Records with Both Timestamps | Duration Matches | Mismatches | Mismatch IDs | Status |
|---------|----------------------------|-----------------|------------|--------------|--------|
| Equifax | 79 | 79 | 0 | None | PASS |
| JPMorgan Chase | 86 | 86 | 0 | None | PASS |
| MGM Resorts | 89 | 89 | 0 | None | PASS |
| Microsoft | 76 | 76 | 0 | None | PASS |
| T-Mobile | 78 | 78 | 0 | None | PASS |

### Negative / Non-Numeric Duration Values

| Company | Negative Durations | Non-Numeric Durations | Status |
|---------|-------------------|----------------------|--------|
| Equifax | 0 | 0 | PASS |
| JPMorgan Chase | 0 | 0 | PASS |
| MGM Resorts | 0 | 0 | PASS |
| Microsoft | 0 | 0 | PASS |
| T-Mobile | 0 | 0 | PASS |

## 9. Missing / Null Validation

### Field: `closed_time`

| Company | Total Rows | Missing Count | Missing % | Sample Missing IDs | Classification |
|---------|-----------|--------------|-----------|-------------------|----------------|
| Equifax | 100 | 21 | 21.0% | ['ALT00025', 'ALT00048', 'ALT00005', 'ALT00029', 'ALT00039'] | ACCEPTABLE — open/in-progress alerts lack closure time |
| JPMorgan Chase | 100 | 14 | 14.0% | ['ALT00054', 'ALT00008', 'ALT00019', 'ALT00007', 'ALT00045'] | ACCEPTABLE — open/in-progress alerts lack closure time |
| MGM Resorts | 100 | 11 | 11.0% | ['ALT00015', 'ALT00095', 'ALT00090', 'ALT00014', 'ALT00067'] | ACCEPTABLE — open/in-progress alerts lack closure time |
| Microsoft | 100 | 24 | 24.0% | ['ALT00089', 'ALT00079', 'ALT00059', 'ALT00073', 'ALT00016'] | ACCEPTABLE — open/in-progress alerts lack closure time |
| T-Mobile | 100 | 22 | 22.0% | ['ALT00051', 'ALT00057', 'ALT00089', 'ALT00030', 'ALT00004'] | ACCEPTABLE — open/in-progress alerts lack closure time |

### Field: `closure_duration_minutes`

| Company | Total Rows | Missing Count | Missing % | Sample Missing IDs | Classification |
|---------|-----------|--------------|-----------|-------------------|----------------|
| Equifax | 100 | 21 | 21.0% | ['ALT00025', 'ALT00048', 'ALT00005', 'ALT00029', 'ALT00039'] | ACCEPTABLE — derived from timestamps; absent when closed_time missing |
| JPMorgan Chase | 100 | 14 | 14.0% | ['ALT00054', 'ALT00008', 'ALT00019', 'ALT00007', 'ALT00045'] | ACCEPTABLE — derived from timestamps; absent when closed_time missing |
| MGM Resorts | 100 | 11 | 11.0% | ['ALT00015', 'ALT00095', 'ALT00090', 'ALT00014', 'ALT00067'] | ACCEPTABLE — derived from timestamps; absent when closed_time missing |
| Microsoft | 100 | 24 | 24.0% | ['ALT00089', 'ALT00079', 'ALT00059', 'ALT00073', 'ALT00016'] | ACCEPTABLE — derived from timestamps; absent when closed_time missing |
| T-Mobile | 100 | 22 | 22.0% | ['ALT00051', 'ALT00057', 'ALT00089', 'ALT00030', 'ALT00004'] | ACCEPTABLE — derived from timestamps; absent when closed_time missing |

### Field: `investigation_notes`

| Company | Total Rows | Missing Count | Missing % | Sample Missing IDs | Classification |
|---------|-----------|--------------|-----------|-------------------|----------------|
| Equifax | 100 | 13 | 13.0% | ['ALT00090', 'ALT00006', 'ALT00045', 'ALT00054', 'ALT00065'] | POTENTIAL DATA QUALITY ISSUE — significant missing notes |
| JPMorgan Chase | 100 | 17 | 17.0% | ['ALT00095', 'ALT00084', 'ALT00091', 'ALT00080', 'ALT00055'] | POTENTIAL DATA QUALITY ISSUE — significant missing notes |
| MGM Resorts | 100 | 18 | 18.0% | ['ALT00093', 'ALT00015', 'ALT00073', 'ALT00023', 'ALT00035'] | POTENTIAL DATA QUALITY ISSUE — significant missing notes |
| Microsoft | 100 | 14 | 14.0% | ['ALT00059', 'ALT00067', 'ALT00005', 'ALT00097', 'ALT00042'] | POTENTIAL DATA QUALITY ISSUE — significant missing notes |
| T-Mobile | 100 | 10 | 10.0% | ['ALT00070', 'ALT00004', 'ALT00019', 'ALT00066', 'ALT00048'] | POTENTIAL DATA QUALITY ISSUE — significant missing notes |

## 10. Validation Summary

| Metric | Count |
|--------|-------|
| Total companies validated | 5 |
| Total checks performed | 20 |
| Passed | 20 |
| Warnings | 0 |
| Failed | 0 |

## Overall Status: PASS

---

*End of Disha Step 2.1 — Dataset & Feature Validation Report*