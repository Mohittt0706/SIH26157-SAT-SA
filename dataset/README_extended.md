# Extended Validation Dataset

`soc_alerts_extended.csv` — 4,667 alerts across 21 entities, Jan–Jun 2026.
Deterministic (seed 26157). Same 8-column ingestion schema as the primary dataset.

This is a **second** dataset, not a replacement. The primary 639-alert dataset
remains the canonical demo; this one exercises the detectors at larger scale and
across more entities, and includes pattern types the primary dataset does not.

## Why it exists

The primary dataset has 10 entities. Peer median and MAD estimated from 9 peers
are noisy, and Isolation Forest is statistically weak at that size. 21 entities
gives a materially firmer peer baseline. It also fixes a known weakness: in the
primary dataset the investigation-note template pool was small enough that
baseline entities showed 80–100% note duplication, which made the TEMPLATE_NOTES
rule fire on everyone and discriminate nothing. Here, baseline entities draw from
a 25-action × 8-followup note pool with substituted IPs, usernames, hostnames and
ticket numbers, so genuine notes are effectively unique.

## Seeded patterns — answer key

`answer_key_extended_INTERNAL_ONLY.csv` — gitignored, never submitted.

| Entity | Pattern | Expected detector |
|---|---|---|
| Meridian Trust Bank | Execution gap, blatant | execution_gap |
| Kaveri Power Holdings | Execution gap, subtle | execution_gap |
| Saraswati Rail Network | Negative space, volume collapse | negative_space |
| Nilgiri Water Authority | Negative space, missing severities | negative_space |
| Arcadia Defence Systems | Anomaly, volume spike | anomaly |
| Konkan Maritime Ltd | Anomaly, multi-feature drift | anomaly |
| Deccan Health Network | Borderline, mild weakness | execution_gap (mid band) |
| Remaining 14 | Baseline | — |

## What each seeded entity looks like

**Meridian Trust Bank** — 285 alerts. 94.7% of critical/high closed under 300s
(mean closure 162s vs peer ~14,000s). 90.3% of criticals never escalated. 100%
of notes drawn from a two-string template pool, mean note length 5.1 chars vs
peer ~104. Every execution-gap rule fires hard.

**Kaveri Power Holdings** — 240 alerts. 58.2% fast closure, 68.0% no escalation,
39% duplicated notes, mean note length 66.8. Elevated on every rule but none
extreme — tests whether the detector ranks degree, not just presence.

**Saraswati Rail Network** — 11 alerts against a peer median near 200. Only low
and medium severity; no critical or high at all. The volume collapse and the
missing severities both fire.

**Nilgiri Water Authority** — 175 alerts, an entirely normal volume, so the
volume rule stays silent. But no critical or high severity records exist at all.
This entity only becomes visible through MISSING_EXPECTED_SEVERITY, which is the
point: it is invisible to a volume-only check.

**Arcadia Defence Systems** — 760 alerts against a peer median near 200. Every
other feature sits in the normal band, so it is a single-feature outlier.

**Konkan Maritime Ltd** — 190 alerts, a normal volume, but four features drift
together: mean closure 34,815s vs peer ~14,000, escalation rate 0.59 vs ~0.22,
critical ratio 0.20 vs ~0.06, and only three asset types monitored vs eight.
No single rule catches it; the feature vector as a whole is what stands out.

**Deccan Health Network** — deliberately ambiguous. 26.7% fast closure and 43%
duplicated notes, enough to be elevated but not enough to be obviously seeded.
It exists so the ranking has a genuine middle, not just a clean/guilty split.

## Known caveat

Baseline entities show NO_ESCALATION rates ranging roughly 0.08–0.56. This is
sampling noise, not a generation flaw: each baseline entity has only ~10 critical
alerts, so the rate sits on a small denominator. Real SOC data has the same
property. It keeps baseline execution-gap scores non-zero but well below the
seeded entities.

## Regenerating

`python generate_extended.py` — deterministic, produces byte-identical output.
