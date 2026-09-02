# Disha Independent Validation Report

**Overall status:** FAIL

- PASS — dataset rows: 639 (expected 639)
- PASS — unique entities: 10 (expected 10)
- PASS — entity_name missing/blank: 0
- PASS — alert_id missing/blank: 0
- PASS — severity missing/blank: 0
- PASS — closure_duration_minutes missing/blank: 0
- PASS — escalated missing/blank: 0
- PASS — investigation_notes missing/blank: 0
- PASS — asset_type missing/blank: 0
- PASS — duplicate alert_id values: 0
- PASS — invalid/negative closure durations: 0
- PASS — blank entity_name rows: 0
- PASS — independent 6-feature calculation completed for 10 entities
- PASS — independent Negative Space low-volume baseline computed; flagged: Delta Rail Systems
- PASS — independent missing-severity baseline computed; flags: 2
- PASS — API entity count: 10
- FAIL — independent risk-score arithmetic (10 mismatches)
-   - Delta Rail Systems: expected 0.0, API 85.0
-   - Indus Financial Services: expected 0.0, API 61.8
-   - Continental Banking Corp: expected 0.0, API 58.2
-   - Fortis Defense Systems: expected 0.0, API 42.3
-   - Ganga Oil & Gas: expected 0.0, API 22.9
-   - Bharat Telecom Networks: expected 0.0, API 18.8
-   - Jupiter Aviation Control: expected 0.0, API 11.2
-   - Eastern Water Utility: expected 0.0, API 9.5
-   - Apex Power Grid Ltd: expected 0.0, API 8.5
-   - Himalayan Healthcare Network: expected 0.0, API 6.1
- PASS — Execution Gap evidence trace: 0/0 valid alert IDs

## Independence rule
This validator calculates the six entity-level features directly from the raw CSV and does not import detector internals. It reports mismatches; it does not modify analytics code.
