# Formula and timing reference

`t` is zero-based: the first forecast month is `t = 0`. All major money calculations round to cents using Decimal `ROUND_HALF_UP`. The engine uses 48-digit decimal precision. It does not round rates to cents. The calculation source is [model.py](../smb_forecast/model.py).

## Revenue and operating performance

| Output | Calculation |
|---|---|
| Revenue | `round(monthly_revenue × (1 + monthly_growth_rate)^t × seasonality[calendar_month])`; month zero uses growth factor 1; a revenue override replaces this result |
| COGS | `round(revenue × cogs_rate)` or `round(revenue × (1 − gross_margin))` |
| Gross profit | `revenue − COGS` |
| Variable operating expenses | `round(revenue × variable_opex_rate)` |
| Hire payroll | Sum of monthly costs for hires with `start_month <= current_month` |
| Payroll | Existing payroll + hire payroll |
| Operating expenses | Fixed operating expenses + variable operating expenses + payroll |
| Operating income | Gross profit − operating expenses; before depreciation, interest, and tax |
| Pretax income | Operating income − assumed interest expense |
| Tax accrual | `round(max(pretax_income, 0) × tax_rate)` |
| Net income | Pretax income − tax accrual; simplified and without depreciation |

Capex and principal repayments affect cash, not operating income. Debt draws do not count as revenue or profit. Interest reduces pretax income and is paid in its entered month. No losses are carried forward to reduce a future tax accrual.

## Invoice cohorts and cash timing

For a revenue cohort in month `i`, collection weight `w[j]` places its collection in month `i + j`. Supplier payments apply the equivalent rule to COGS. Each invoice is allocated separately: nonfinal nonzero buckets round half up, bounded by its remaining amount; the final nonzero bucket receives the residual. This preserves exact cents and nonnegative buckets, even on very small invoices. For example, a $0.01 invoice split 50/50 yields $0.01 now and $0.00 later.

Tax accrual in month `i` is paid at month `i + tax_lag_months`. Opening schedules add the settlement of pre-forecast balances. Collections or payments beyond the forecast are not discarded; they remain in ending balances.

| Output | Calculation |
|---|---|
| Customer receipts | New revenue cohort collections due this month + opening AR collections due this month |
| Supplier payments | New COGS cohort payments due this month + opening AP payments due this month |
| Tax payments | New tax accruals due this month + opening tax liability payments due this month |
| Cash inflows | Customer receipts + debt draws |
| Cash outflows | Supplier payments + operating expenses + tax payments + capex + interest + principal repayments |
| Cash change | Cash inflows − cash outflows |
| Ending cash | Beginning monthly cash + cash change; next month's beginning cash equals this ending cash |
| Ending AR | Prior AR + revenue − customer receipts |
| Ending AP | Prior AP + COGS − supplier payments |
| Ending tax liability | Prior tax liability + tax accrual − tax payments |
| Ending debt | Prior debt + draws − principal repayments |

All non-COGS operating expenses are paid immediately. There is no inventory balance or purchase lead time.

## Reconciliation

The independent indirect cash bridge is:

```text
cash change = net income
            − change in AR
            + change in AP
            + change in tax liability
            − capex
            + debt draws
            − principal repayments
```

`cash_reconciliation_difference = indirect cash change − direct cash change`. It must equal **exactly zero** for each month. The engine rejects a forecast with a nonzero difference or negative AR/AP/tax balances. Interest is already deducted in net income and must not be subtracted twice in this bridge.

## Decision-support estimates

| Metric | Definition and boundary |
|---|---|
| Contribution margin | Gross margin − variable operating expense rate |
| Monthly operating break-even revenue | `(fixed_opex + payroll) ÷ contribution_margin`, rounded to cents. Null if contribution margin ≤ 0. It excludes interest, taxes, capex, and timing; it is an estimate, not an exact cent-level solver |
| Cash change before financing | Cash change − debt draws; principal repayments remain included |
| Trailing average burn | `max(−average(cash_change_before_financing over last up to 3 available months), 0)`; displayed rounded to cents |
| Cash runway in months | Positive ending cash ÷ **unrounded** trailing average burn, rounded to 2 decimals. Zero if ending cash ≤ 0. Null if positive cash and no recent burn |
| First negative cash month | First month with ending cash < 0; a zero balance is not counted as negative |
| Minimum ending cash | Minimum of forecast month-end balances; excludes the pre-forecast starting balance |
| Scenario variance | Scenario result − baseline result for revenue, operating income, ending cash, and cash change; baseline variance is zero |

The runway heuristic is distinct from the first negative forecast month. Future hiring or capex can create a deficit even when there is no recent burn. The model shows both measures explicitly. Scenario variances are arithmetic signs, not automatic favorable/unfavorable judgments, and are not actual-versus-budget variances.
