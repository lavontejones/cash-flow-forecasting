# Input dictionary

All monetary inputs use the same currency unit. `currency` is an uppercase three-letter display label; no exchange conversion occurs. JSON amounts/rates must be numbers, not quoted strings. Non-finite numbers and duplicate object keys are rejected. Amounts are rounded to cents on input, half up. Unknown fields are rejected to prevent unnoticed typos.

## Model wrapper

| Field | Default | Meaning / limits |
|---|---|---|
| `schema_version` | 1 | Only integer 1 is supported |
| `model_name` | SMB Cash Flow Forecast | 1–120 characters; output is escaped |
| `currency` | USD | Three uppercase letters; display label only |
| `assumptions` | Defaults below | Baseline assumption object |
| `scenarios` | None | Up to 10 named top-level patches; lowercase identifier, 1–32 characters; `base` reserved |

Base is always calculated from `assumptions`. Downside/upside/custom are provided by the sample; additional scenarios may use any permitted identifier. They have no automatically assigned probability or generated optimism/pessimism. A patch replaces each supplied top-level field completely. Scenarios cannot change `start_month` or `months`.

## Assumptions

| Field | Default | Units and treatment |
|---|---|---|
| `start_month` | 2027-01 | YYYY-MM; years 2000–2099; forecast must end before 2100 |
| `months` | 12 | Integer horizon, 1–60 months |
| `monthly_revenue` | 100000 | First-month revenue before seasonality |
| `monthly_growth_rate` | 0 | Decimal monthly growth, −1 to 1 inclusive; first month has no growth step |
| `seasonality` | Twelve 1s | Jan–Dec calendar factors, each 0–5; factors are not normalized automatically |
| `gross_margin` | 0.55 | Decimal share of revenue after COGS, 0–1 |
| `cogs_rate` | Absent | Alternative decimal COGS share, 0–1; supplying it removes default margin; never supply both cost fields |
| `fixed_opex` | 12000 | Monthly fixed cash expenses; excludes payroll, COGS, interest, and capex |
| `variable_opex_rate` | 0.05 | Decimal share of revenue, 0–1; separate from COGS |
| `payroll` | 30000 | Fully loaded existing monthly payroll; not planned hires |
| `hires` | [] | Up to 100 entries with exactly `name`, `start_month`, `monthly_cost`; starts inside horizon and continues to its end |
| `capex` | {} | YYYY-MM → capital cash expenditure, within horizon |
| `collection_weights` | [1] | Fractions collected in invoice month, month +1, month +2…; 1–13 fractions totaling exactly 1 |
| `payment_weights` | [1] | Same structure for COGS supplier invoices; 1–13 fractions totaling exactly 1 |
| `opening_ar` | [] | Cash to collect from pre-forecast invoices in month 1, 2…; up to 13 amounts; sum is opening AR |
| `opening_ap` | [] | Cash to pay for pre-forecast supplier invoices in month 1, 2…; up to 13 amounts; sum is opening AP |
| `tax_rate` | 0 | Decimal assumed rate, 0–1, applied to positive operating income less interest |
| `tax_lag_months` | 0 | Integer 0–12; tax paid this many months after accrual |
| `opening_tax_payments` | [] | Prior tax liability payments in month 1, 2…; up to 13 amounts; sum is opening tax liability |
| `beginning_cash` | 100000 | Nonnegative opening cash immediately before month 1 |
| `opening_debt` | 0 | Nonnegative opening debt principal |
| `debt_draws` | {} | YYYY-MM → borrowed cash / additional debt principal |
| `debt_principal` | {} | YYYY-MM → principal cash payment; cannot exceed opening monthly debt plus same-month draws |
| `debt_interest` | {} | YYYY-MM → assumed interest expense and payment; positive interest requires opening debt or same-month draw |
| `revenue_overrides` | {} | YYYY-MM → final revenue; replaces the growth/seasonality result for that month only |

Each entered amount is 0–1,000,000,000,000 inclusive. Balances and forecasts can become negative or grow beyond that input limit. Forecasting uses a 48-digit decimal context. Percent fields in the dashboard display percentages; JSON uses fractions. Seasonality can change total annual revenue: twelve factors averaging 1 preserves a flat, zero-growth year's unseasoned revenue total, but does not generally preserve a growing year's total.

Opening AR/AP/tax schedules describe balances already present before the forecast. They are not additional revenue/expense. Their future settlement is additive to new forecast cohorts. For short forecasts, opening schedules can extend beyond the forecast and remain on the ending balance.

Hires have no termination date or headcount ramp; enter separate models or adjust `payroll` for other patterns. Scheduled debt draws and repayments are arithmetic assumptions, not borrowing recommendations. Setting all financing schedules and `opening_debt` to zero removes the debt layer.

## Example schedules

```json
{
  "collection_weights": [0.4, 0.4, 0.2],
  "payment_weights": [0.25, 0.75],
  "opening_ar": [30000, 15000],
  "opening_ap": [25000],
  "hires": [{"name": "Synthetic role", "start_month": "2027-07", "monthly_cost": 6500}],
  "capex": {"2027-03": 18000}
}
```

Forty percent of each new revenue cohort is collected in its invoice month, 40% in the next month, and 20% two months later. Twenty-five percent of each new COGS cohort is paid immediately, with 75% next month. Opening AR provides an additional $30,000 collection in month 1 and $15,000 in month 2.
