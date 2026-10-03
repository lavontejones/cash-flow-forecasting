# Worked examples and portfolio walkthrough

## Independently calculated monthly example

One month with immediate collections/payments, $1,000 revenue, 60% gross margin, $100 fixed expenses, variable expenses of 10% of revenue, $200 payroll, an assumed 20% tax rate, and $100 beginning cash:

| Calculation | Result |
|---|---:|
| COGS = 1,000 × 40% | $400 |
| Gross profit = 1,000 − 400 | $600 |
| Variable expenses = 1,000 × 10% | $100 |
| Operating expenses = 100 fixed + 100 variable + 200 payroll | $400 |
| Operating income = 600 − 400 | $200 |
| Assumed tax accrual and payment = 200 × 20% | $40 |
| Cash outflows = 400 COGS + 400 operating expenses + 40 taxes | $840 |
| Ending cash = 100 + 1,000 collected − 840 paid | $260 |
| Break-even revenue = (100 fixed + 200 payroll) ÷ (60% − 10%) | $600 |

The core test `test_independent_immediate_cash_example` verifies these results against the engine. No recent cash burn exists, so runway is null rather than an invented infinite value.

## Profit is not cash

Keep the above economics, collect all new revenue one month later, pay suppliers one month later, enter opening AR collections of $150 then $50, opening AP payments of $70, opening tax payments of $0 then $10, and pay new tax accruals one month later:

| Measure | Month 1 | Month 2 |
|---|---:|---:|
| Revenue | $1,000 | $1,000 |
| Operating income | $200 | $200 |
| Customer receipts | $150 | $1,050 |
| Supplier payments | $70 | $400 |
| Operating cash expenses | $400 | $400 |
| Tax payments | $0 | $50 |
| Ending cash | −$220 | −$20 |
| Ending AR | $1,050 | $1,000 |
| Ending AP | $400 | $400 |
| Ending tax liability | $50 | $40 |

The business reports profit in both months but has negative modeled cash because the timing of receipts and payments differs from expense recognition. Opening balances settle without creating new forecast revenue/expense.

## Five-minute demo sequence

1. Run the sample dashboard and start on base. Show the $89,576.87 ending cash and $53,272.09 lowest month-end balance.
2. Select downside. Revenue declines, gross margin narrows, and collections slow. The first negative cash month is March 2027.
3. Select custom. The model removes the hire, reduces equipment purchases, and collects faster. Ending cash is $197,689.38, or $108,112.51 above base.
4. Change a custom assumption and recalculate. Show the signed monthly cash variances against base and the resolved assumptions in an exported report.
5. Export the CSV and identify `ending_ar`, `ending_ap`, `ending_tax_liability`, and the zero cash reconciliation difference. Explain the formulas and limitations before interpreting any modeled outcome.

This sequence demonstrates assumption gathering, FP&A modeling, working-capital analysis, scenario reporting, and a clear handoff. All outcomes are synthetic examples; no client results or advice are implied.
