# Saksham Engine — Model Report (v1-lgbm-20261002)

> ⚠️ **Trained on synthetic data.** Production would start in shadow mode on real repayment outcomes.

## Headline metrics (held-out test set)

| Metric | Value |
|---|---|
| AUC | 0.813 |
| KS | 0.492 |
| Brier (calibrated) | 0.0768 |
| Brier (uncalibrated) | 0.0764 |
| Test default rate | 10.0% |
| Rows (train / val / test) | 12710 / 2724 / 2724 |
| Boosting rounds (early stopping) | 192 |
| Approval rate at cutoff 650 | 60.6% |

## AUC per segment

| Segment | n | default rate | AUC |
|---|---|---|---|
| farmer | 871 | 12.6% | 0.834 |
| gig | 739 | 9.2% | 0.804 |
| merchant | 906 | 8.5% | 0.798 |
| salaried | 208 | 8.7% | 0.777 |

## AUC on partial-data slices

| Slice | n | AUC |
|---|---|---|
| AA missing | 195 | 0.893 |
| Telecom missing | 133 | 0.835 |
| No business records | 1167 | 0.802 |
| All 3 sources | 1229 | 0.812 |

## Calibration (deciles of predicted PD)

| Predicted PD | Observed default rate | n |
|---|---|---|
| 0.008 | 0.011 | 273 |
| 0.012 | 0.007 | 272 |
| 0.017 | 0.018 | 272 |
| 0.025 | 0.040 | 273 |
| 0.036 | 0.048 | 272 |
| 0.055 | 0.048 | 272 |
| 0.085 | 0.106 | 273 |
| 0.133 | 0.143 | 272 |
| 0.221 | 0.191 | 272 |
| 0.448 | 0.388 | 273 |

## Score ↔ PD lookup

`Score = Offset + Factor · ln((1−PD)/PD)`, PDO = 60, Factor = 86.562, Offset = 426.092 (anchored so score 650 ↔ PD 7%); clamped to [300, 900].

| Score | PD |
|---|---|
| 300 | 81.10% |
| 350 | 70.66% |
| 400 | 57.48% |
| 450 | 43.14% |
| 500 | 29.86% |
| 550 | 19.29% |
| 600 | 11.83% |
| 650 | 7.00% |
| 700 | 4.05% |
| 750 | 2.32% |
| 800 | 1.31% |
| 850 | 0.74% |
| 900 | 0.42% |

Check: score 650 → PD 7.00%; PD 7% → score 650.0.

## Top features (gain)

| Feature | Gain |
|---|---|
| buffer_ratio | 10,544 |
| sim_tenure_months | 4,488 |
| min_balance_days | 2,050 |
| avg_recharge_value | 1,893 |
| emi_to_income_ratio | 1,588 |
| max_recharge_gap_days | 1,298 |
| recharge_frequency_regularity | 1,138 |
| max_monthly_outflow | 1,138 |
| distinct_upi_counterparties | 970 |
| upi_txn_frequency | 907 |
| balance_volatility | 785 |
| recharge_count_12m | 663 |
| cash_vs_digital_ratio | 550 |
| mandi_avg_settlement_delay | 545 |
| mandi_avg_monthly_settlement | 536 |
