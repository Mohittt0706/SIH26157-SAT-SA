"""
STEP 1: DATASET VALIDATION — DISHA
Independent validation of 5 external company CSV datasets.
Read-only: no data is modified.
"""
import csv
import os
import sys
from datetime import datetime
from collections import Counter, defaultdict

EXPECTED_COLUMNS = [
    "alert_id", "entity_name", "severity", "category", "asset_type",
    "created_time", "closed_time", "closure_duration_minutes",
    "escalated", "status", "investigation_notes"
]

EXPECTED_SEVERITIES = {"low", "medium", "high", "critical"}

COMPANIES = [
    ("Equifax", "soc_alerts_equifax.csv"),
    ("JPMorgan Chase", "soc_alerts_jpmorgan_chase.csv"),
    ("MGM Resorts", "soc_alerts_mgm_resorts.csv"),
    ("Microsoft", "soc_alerts_microsoft.csv"),
    ("T-Mobile", "soc_alerts_t-mobile.csv"),
]

DATASET_DIR = os.path.join(os.path.dirname(__file__), "..", "dataset", "external")

all_issues = []


def add_issue(company, check, column, count, example, severity, explanation):
    all_issues.append({
        "company": company,
        "check": check,
        "column": column,
        "count": count,
        "example": example,
        "severity": severity,
        "explanation": explanation,
    })


def parse_timestamp(ts_str):
    """Try common timestamp formats."""
    if not ts_str or ts_str.strip() == "":
        return None
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(ts_str.strip(), fmt)
        except ValueError:
            continue
    return None


def validate_company(company_name, filename):
    filepath = os.path.join(DATASET_DIR, filename)
    result = {}

    # A. FILE EXISTENCE
    if not os.path.isfile(filepath):
        result["file_existence"] = "FAIL"
        add_issue(company_name, "File Existence", "N/A", 1, filepath,
                  "FAIL", f"File not found: {filepath}")
        return result
    result["file_existence"] = "PASS"

    # Read CSV
    with open(filepath, "r", encoding="utf-8-sig") as f:
        raw_lines = f.readlines()

    # B. ROW COUNT (data rows = total lines - header)
    row_count = len(raw_lines) - 1
    result["row_count"] = row_count

    # Parse CSV
    reader = csv.DictReader(raw_lines)
    rows = list(reader)

    # C. SCHEMA VALIDATION
    actual_columns = list(csv.DictReader(raw_lines).fieldnames or [])
    missing_cols = [c for c in EXPECTED_COLUMNS if c not in actual_columns]
    extra_cols = [c for c in actual_columns if c not in EXPECTED_COLUMNS]
    order_match = actual_columns == EXPECTED_COLUMNS

    schema_pass = len(missing_cols) == 0 and len(extra_cols) == 0
    result["schema"] = "PASS" if schema_pass else "FAIL"
    if missing_cols:
        add_issue(company_name, "Schema", "columns", len(missing_cols),
                  missing_cols, "FAIL",
                  f"Missing expected columns: {missing_cols}")
    if extra_cols:
        add_issue(company_name, "Schema", "columns", len(extra_cols),
                  extra_cols, "WARNING",
                  f"Unexpected extra columns: {extra_cols}")
    if not order_match and schema_pass:
        add_issue(company_name, "Schema", "column_order", 1,
                  f"Expected: {EXPECTED_COLUMNS}\nActual: {actual_columns}",
                  "WARNING", "Column order differs from expected schema")

    result["actual_columns"] = actual_columns
    result["missing_columns"] = missing_cols
    result["extra_columns"] = extra_cols

    # D. DUPLICATE ALERT IDs
    alert_ids = [r.get("alert_id", "") for r in rows]
    id_counts = Counter(alert_ids)
    dupes = {k: v for k, v in id_counts.items() if v > 1}
    dup_count = sum(v - 1 for v in dupes.values())
    if dupes:
        result["duplicates"] = "FAIL"
        add_issue(company_name, "Duplicate Alert IDs", "alert_id", dup_count,
                  dict(list(dupes.items())[:5]), "FAIL",
                  f"{dup_count} duplicate alert_id values found across {len(dupes)} IDs")
    else:
        result["duplicates"] = "PASS"
    result["duplicate_ids"] = dupes

    # E. REQUIRED / BLANK VALUES
    blank_counts = {}
    for col in EXPECTED_COLUMNS:
        blanks = sum(1 for r in rows if not r.get(col, "").strip())
        blank_counts[col] = blanks

    required_cols = ["alert_id", "entity_name", "severity", "category",
                     "asset_type", "created_time", "status"]
    has_required_blanks = any(blank_counts[c] > 0 for c in required_cols)
    has_optional_blanks = any(blank_counts[c] > 0 for c in
                              ["closed_time", "closure_duration_minutes", "investigation_notes"])

    if has_required_blanks:
        result["missing_values"] = "FAIL"
        for c in required_cols:
            if blank_counts[c] > 0:
                examples = [r.get("alert_id", "?") for r in rows
                            if not r.get(c, "").strip()][:5]
                add_issue(company_name, "Missing Required Values", c,
                          blank_counts[c], examples, "FAIL",
                          f"{blank_counts[c]} rows have blank/missing {c}")
    elif has_optional_blanks:
        result["missing_values"] = "WARN"
        for c in ["closed_time", "closure_duration_minutes", "investigation_notes"]:
            if blank_counts[c] > 0:
                examples = [r.get("alert_id", "?") for r in rows
                            if not r.get(c, "").strip()][:5]
                add_issue(company_name, "Missing Optional Values", c,
                          blank_counts[c], examples, "WARNING",
                          f"{blank_counts[c]} rows have blank/missing {c} (data-quality finding)")
    else:
        result["missing_values"] = "PASS"
    result["blank_counts"] = blank_counts

    # F. CATEGORICAL VALUE VALIDATION
    cat_fields = {
        "severity": EXPECTED_SEVERITIES,
        "category": set(),
        "asset_type": set(),
        "escalated": {"Yes", "No"},
        "status": {"Closed", "Open", "In Progress"},
    }
    cat_values = {}
    cat_issues = []
    for field, expected in cat_fields.items():
        unique_vals = Counter(r.get(field, "") for r in rows)
        cat_values[field] = dict(unique_vals)
        for val, cnt in unique_vals.items():
            val_clean = val.strip()
            if val_clean == "":
                cat_issues.append((field, "(blank)", cnt))
            elif expected and val_clean.lower() not in {e.lower() for e in expected}:
                cat_issues.append((field, val_clean, cnt))

    if cat_issues:
        result["categorical"] = "WARN"
        for field, val, cnt in cat_issues:
            examples = [r.get("alert_id", "?") for r in rows
                        if r.get(field, "").strip().lower() == val.lower() or
                        (val == "(blank)" and not r.get(field, "").strip())][:3]
            sev = "WARNING" if val != "(blank)" else "FAIL"
            explanation = (f"Unexpected value '{val}' in {field}" if val != "(blank)"
                          else f"Blank values in {field}")
            add_issue(company_name, "Categorical Values", field, cnt,
                      examples, sev, explanation)
    else:
        result["categorical"] = "PASS"
    result["categorical_values"] = cat_values

    # G. TIMESTAMP VALIDATION
    ts_issues_created = 0
    ts_issues_closed = 0
    ts_created_before_closed = 0
    invalid_created_examples = []
    invalid_closed_examples = []
    before_closed_examples = []

    for r in rows:
        aid = r.get("alert_id", "?")
        ct = parse_timestamp(r.get("created_time", ""))
        clt = parse_timestamp(r.get("closed_time", ""))

        if r.get("created_time", "").strip() and ct is None:
            ts_issues_created += 1
            if len(invalid_created_examples) < 5:
                invalid_created_examples.append(
                    (aid, r.get("created_time", "")))

        if r.get("closed_time", "").strip() and clt is None:
            ts_issues_closed += 1
            if len(invalid_closed_examples) < 5:
                invalid_closed_examples.append(
                    (aid, r.get("closed_time", "")))

        if ct and clt and clt < ct:
            ts_created_before_closed += 1
            if len(before_closed_examples) < 5:
                before_closed_examples.append(
                    (aid, r.get("created_time", ""), r.get("closed_time", "")))

    if ts_issues_created > 0 or ts_issues_closed > 0:
        result["timestamp_validity"] = "FAIL"
        if ts_issues_created > 0:
            add_issue(company_name, "Timestamp Validity", "created_time",
                      ts_issues_created, invalid_created_examples, "FAIL",
                      f"{ts_issues_created} rows have unparseable created_time")
        if ts_issues_closed > 0:
            add_issue(company_name, "Timestamp Validity", "closed_time",
                      ts_issues_closed, invalid_closed_examples, "FAIL",
                      f"{ts_issues_closed} rows have unparseable closed_time")
    elif ts_created_before_closed > 0:
        result["timestamp_validity"] = "WARN"
        add_issue(company_name, "Timestamp Validity", "closed_time < created_time",
                  ts_created_before_closed, before_closed_examples, "WARNING",
                  f"{ts_created_before_closed} rows have closed_time earlier than created_time")
    else:
        result["timestamp_validity"] = "PASS"

    # H. CLOSURE DURATION CONSISTENCY
    mismatch_count = 0
    mismatch_examples = []
    extreme_duration_count = 0
    extreme_duration_examples = []

    for r in rows:
        aid = r.get("alert_id", "?")
        ct = parse_timestamp(r.get("created_time", ""))
        clt = parse_timestamp(r.get("closed_time", ""))
        dur_str = r.get("closure_duration_minutes", "").strip()

        if ct and clt and dur_str:
            try:
                reported_dur = float(dur_str)
                calc_dur = (clt - ct).total_seconds() / 60.0
                diff = abs(reported_dur - calc_dur)
                if diff > 2:  # tolerance of 2 minutes
                    mismatch_count += 1
                    if len(mismatch_examples) < 5:
                        mismatch_examples.append({
                            "alert_id": aid,
                            "reported": reported_dur,
                            "calculated": round(calc_dur, 1),
                            "diff": round(diff, 1),
                        })
            except (ValueError, TypeError):
                pass

        if dur_str:
            try:
                d = float(dur_str)
                if d < 0:
                    extreme_duration_count += 1
                    if len(extreme_duration_examples) < 5:
                        extreme_duration_examples.append((aid, dur_str))
                elif d > 1440:  # > 24 hours
                    extreme_duration_count += 1
                    if len(extreme_duration_examples) < 5:
                        extreme_duration_examples.append((aid, dur_str))
            except (ValueError, TypeError):
                pass

    if mismatch_count > 0:
        result["closure_duration"] = "WARN"
        add_issue(company_name, "Closure Duration Consistency",
                  "closure_duration_minutes", mismatch_count,
                  mismatch_examples, "WARNING",
                  f"{mismatch_count} rows where reported closure_duration_minutes "
                  f"differs from calculated (closed_time - created_time) by >2 min")
    else:
        result["closure_duration"] = "PASS"

    # I. NEGATIVE / IMPOSSIBLE VALUES
    neg_count = 0
    non_numeric_count = 0
    neg_examples = []
    non_numeric_examples = []

    for r in rows:
        aid = r.get("alert_id", "?")
        dur_str = r.get("closure_duration_minutes", "").strip()
        if dur_str == "":
            continue
        try:
            d = float(dur_str)
            if d < 0:
                neg_count += 1
                if len(neg_examples) < 5:
                    neg_examples.append((aid, dur_str))
        except (ValueError, TypeError):
            non_numeric_count += 1
            if len(non_numeric_examples) < 5:
                non_numeric_examples.append((aid, dur_str))

    if neg_count > 0:
        result["negative_values"] = "FAIL"
        add_issue(company_name, "Negative/Impossible Values",
                  "closure_duration_minutes", neg_count,
                  neg_examples, "FAIL",
                  f"{neg_count} rows have negative closure_duration_minutes")
    elif non_numeric_count > 0:
        result["negative_values"] = "FAIL"
        add_issue(company_name, "Negative/Impossible Values",
                  "closure_duration_minutes", non_numeric_count,
                  non_numeric_examples, "FAIL",
                  f"{non_numeric_count} rows have non-numeric closure_duration_minutes")
    else:
        result["negative_values"] = "PASS"

    # J. ENTITY CONSISTENCY
    entity_names = [r.get("entity_name", "") for r in rows]
    unique_entities = set(e.strip() for e in entity_names if e.strip())
    blank_entities = sum(1 for e in entity_names if not e.strip())
    entity_case_groups = defaultdict(set)
    for e in entity_names:
        if e.strip():
            entity_case_groups[e.strip().lower()].add(e.strip())

    inconsistent_entities = {k: v for k, v in entity_case_groups.items() if len(v) > 1}

    if blank_entities > 0:
        result["entity_consistency"] = "FAIL"
        add_issue(company_name, "Entity Consistency", "entity_name",
                  blank_entities,
                  [r.get("alert_id", "?") for r in rows
                   if not r.get("entity_name", "").strip()][:5],
                  "FAIL", f"{blank_entities} rows have blank entity_name")
    elif inconsistent_entities:
        result["entity_consistency"] = "WARN"
        for canonical, variants in inconsistent_entities.items():
            add_issue(company_name, "Entity Consistency", "entity_name",
                      len(variants), list(variants), "WARNING",
                      f"Inconsistent casing/spelling: {variants}")
    else:
        result["entity_consistency"] = "PASS"
    result["entity_names"] = list(unique_entities)

    return result


def main():
    results = {}
    for company_name, filename in COMPANIES:
        print(f"Validating {company_name} ({filename})...")
        results[company_name] = validate_company(company_name, filename)

    # Print detailed report
    print("\n" + "=" * 80)
    print("DATASET VALIDATION — DISHA (Step 1)")
    print("=" * 80)

    overall_status = "PASS"

    for company_name, filename in COMPANIES:
        r = results[company_name]
        print(f"\nCompany: {company_name}")
        print("-" * 60)

        checks = [
            ("File Existence", r.get("file_existence", "N/A")),
            ("Row Count", r.get("row_count", "N/A")),
            ("Schema", r.get("schema", "N/A")),
            ("Duplicate Alert IDs", r.get("duplicates", "N/A")),
            ("Missing Values", r.get("missing_values", "N/A")),
            ("Categorical Values", r.get("categorical", "N/A")),
            ("Timestamp Validity", r.get("timestamp_validity", "N/A")),
            ("Closure Duration Consistency", r.get("closure_duration", "N/A")),
            ("Negative/Impossible Values", r.get("negative_values", "N/A")),
            ("Entity Consistency", r.get("entity_consistency", "N/A")),
        ]

        for label, status in checks:
            icon = {"PASS": "PASS", "WARN": "WARN", "FAIL": "FAIL",
                     "WARNING": "WARN"}.get(str(status), str(status))
            print(f"  {label}: {icon}")

        # Print schema details
        if r.get("missing_columns"):
            print(f"    Missing columns: {r['missing_columns']}")
        if r.get("extra_columns"):
            print(f"    Extra columns: {r['extra_columns']}")
        if r.get("actual_columns") and r.get("schema") == "PASS":
            print(f"    Columns ({len(r['actual_columns'])}): {r['actual_columns']}")

        # Print blank counts
        bc = r.get("blank_counts", {})
        if bc:
            blanks_reported = {k: v for k, v in bc.items() if v > 0}
            if blanks_reported:
                print(f"    Blank values: {blanks_reported}")

        # Print categorical values
        cv = r.get("categorical_values", {})
        if cv:
            for field, vals in cv.items():
                print(f"    {field} unique values: {vals}")

        # Print entity names
        en = r.get("entity_names", [])
        if en:
            print(f"    Entity names: {en}")

        # Print duplicate IDs
        dupes = r.get("duplicate_ids", {})
        if dupes:
            print(f"    Duplicate IDs: {dupes}")

        # Determine overall
        statuses = [str(v) for v in r.values() if v in ("FAIL", "WARNING", "WARN")]
        if "FAIL" in statuses:
            overall_status = "FAIL"
        elif overall_status != "FAIL" and ("WARN" in statuses or "WARNING" in statuses):
            if overall_status == "PASS":
                overall_status = "PASS WITH WARNINGS"

    # Print issue table
    print("\n" + "=" * 80)
    print("DETECTED ISSUES")
    print("=" * 80)

    if all_issues:
        print(f"\n{'Company':<20} {'Check':<30} {'Column':<30} {'Count':<8} {'Severity':<10} {'Example/Details'}")
        print("-" * 160)
        for issue in all_issues:
            ex = str(issue['example'])[:80]
            print(f"{issue['company']:<20} {issue['check']:<30} {issue['column']:<30} "
                  f"{issue['count']:<8} {issue['severity']:<10} {ex}")
    else:
        print("\nNo issues detected.")

    # Print summary
    print("\n" + "=" * 80)
    print("OVERALL STEP 1 RESULT")
    print("=" * 80)

    fail_count = sum(1 for i in all_issues if i["severity"] == "FAIL")
    warn_count = sum(1 for i in all_issues if i["severity"] == "WARNING")

    if fail_count > 0:
        overall_status = "FAIL"
    elif warn_count > 0:
        overall_status = "PASS WITH WARNINGS"
    else:
        overall_status = "PASS"

    print(f"\n  Overall Status: {overall_status}")
    print(f"  Total Issues: {len(all_issues)} ({fail_count} FAIL, {warn_count} WARNING)")

    # Print per-company summary
    print("\n  Per-Company Breakdown:")
    for company_name, filename in COMPANIES:
        r = results[company_name]
        company_issues = [i for i in all_issues if i["company"] == company_name]
        c_fail = sum(1 for i in company_issues if i["severity"] == "FAIL")
        c_warn = sum(1 for i in company_issues if i["severity"] == "WARNING")
        if c_fail > 0:
            status = "FAIL"
        elif c_warn > 0:
            status = "PASS WITH WARNINGS"
        else:
            status = "PASS"
        print(f"    {company_name}: {status} ({c_fail} FAIL, {c_warn} WARNING)")

    # Print what passed / warned / failed
    print("\n  What Passed:")
    for company_name, _ in COMPANIES:
        r = results[company_name]
        passed = [k for k, v in r.items()
                  if v == "PASS" and k not in ("actual_columns", "duplicate_ids",
                                                "blank_counts", "categorical_values",
                                                "entity_names")]
        if passed:
            print(f"    {company_name}: {', '.join(passed)}")

    print("\n  What Produced Warnings:")
    warn_issues = [i for i in all_issues if i["severity"] == "WARNING"]
    if warn_issues:
        for i in warn_issues:
            print(f"    {i['company']} | {i['check']} | {i['column']} | "
                  f"count={i['count']} | {i['explanation']}")
    else:
        print("    None")

    print("\n  What Produced Failures:")
    fail_issues = [i for i in all_issues if i["severity"] == "FAIL"]
    if fail_issues:
        for i in fail_issues:
            print(f"    {i['company']} | {i['check']} | {i['column']} | "
                  f"count={i['count']} | {i['explanation']}")
    else:
        print("    None")

    print("\n" + "=" * 80)
    print("STEP 1 READINESS")
    print("=" * 80)
    if overall_status == "PASS":
        print("\n  Step 1 is READY to be marked complete.")
    elif overall_status == "PASS WITH WARNINGS":
        print("\n  Step 1 is READY to be marked complete with noted warnings.")
    else:
        print("\n  Step 1 has FAILURES that need review before marking complete.")
    print("=" * 80)


if __name__ == "__main__":
    main()
