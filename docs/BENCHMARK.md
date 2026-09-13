# Pipeline Performance Benchmark

Measured on this machine, using synthetic data generated with the same schema and per-field value distributions as `dataset/soc_alerts_synthetic_dataset.csv` (see `backend/benchmark.py` for the exact generation code). Each size ran 3 times against a fresh scratch SQLite database (never `backend/data/satsa.db`); figures below are the **median** of the completed runs. All numbers are measured directly — none are extrapolated or estimated.

`risk_score aggregation` is the `_combine_entity` + sort step alone — it does **not** include a second run of the three detectors, even though `compute_risk_scores()` normally reruns them internally. `total` is one continuous timed run covering ingestion through aggregation, so it is not simply the sum of the columns rounded differently, but it should be close to their sum.

| Alerts | Entities | Runs completed | Ingestion (s) | Execution Gap (s) | Negative Space (s) | Anomaly (s) | Risk Aggregation (s) | Total (s) | Peak RSS (MB) |
|---|---|---|---|---|---|---|---|---|---|
| 639 | 10 | 3/3 | 0.287 | 0.028 | 0.017 | 0.537 | 0.0004 | 0.833 | 189.0 |
| 5,000 | 50 | 3/3 | 1.770 | 0.287 | 0.104 | 0.646 | 0.0015 | 2.903 | 202.1 |
| 25,000 | 100 | 3/3 | 3.609 | 0.733 | 0.653 | 1.254 | 0.0028 | 6.207 | 258.7 |
| 100,000 | 250 | 3/3 | 15.289 | 3.349 | 2.526 | 4.334 | 0.0062 | 25.388 | 471.4 |

## Notes

- Peak RSS is whole-process resident memory sampled every 20ms via `psutil` during ingestion + all three detectors + aggregation for that run; it includes the Python interpreter and every loaded library, not just the data itself.
- A ⚠️ row completed fewer than the requested number of runs, or one run exceeded the per-run time budget; its median is computed only from the runs that did complete, and the reason is given verbatim.
- Raw per-run figures (not just the medians here) are in `docs/benchmark_raw.csv`.

