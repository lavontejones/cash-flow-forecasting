"""Independent worked examples, invariants, and invalid-input boundaries."""

from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
import random
import unittest

from smb_forecast.model import ModelError, allocate, forecast, loads, run_model


def simple(**patch):
    # All cash is immediate unless a test explicitly changes collection/payment timing.
    assumptions = {"start_month": "2027-01", "months": 3, "monthly_revenue": 1000,
                   "gross_margin": .6, "fixed_opex": 100, "variable_opex_rate": .1,
                   "payroll": 200, "tax_rate": .2, "beginning_cash": 100}
    assumptions.update(patch)
    return assumptions


class CalculationTests(unittest.TestCase):
    def test_independent_immediate_cash_example(self):
        # 1000 revenue - 400 COGS - 100 variable - 100 fixed - 200 payroll = 200 operating profit.
        # Tax = 40; cash inflow 1000; outflow 840; ending cash 100 + 160 = 260.
        row = forecast(simple())["months"][0]
        expected = {"revenue": "1000.00", "cogs": "400.00", "gross_profit": "600.00",
                    "operating_expenses": "400.00", "operating_income": "200.00",
                    "tax_accrual": "40.00", "cash_inflows": "1000.00", "cash_outflows": "840.00",
                    "ending_cash": "260.00", "break_even_revenue": "600.00",
                    "ending_ar": "0", "ending_ap": "0", "ending_tax_liability": "0"}
        for key, value in expected.items():
            self.assertEqual(row[key], D(value), key)
        self.assertIsNone(row["cash_runway_months"])

    def test_delay_opening_balances_and_tax_lag(self):
        # Month 1 collects opening AR 150 only, pays opening AP 70 + OpEx 400.
        # Month 2 collects prior revenue 1000 + opening AR 50; pays prior COGS 400,
        # OpEx 400, opening tax 10, and prior accrued tax 40.
        rows = forecast(simple(collection_weights=[0, 1], payment_weights=[0, 1],
                               opening_ar=[150, 50], opening_ap=[70],
                               opening_tax_payments=[0, 10], tax_lag_months=1))["months"]
        self.assertEqual(rows[0]["ending_cash"], D("-220"))
        self.assertEqual(rows[0]["ending_ar"], D("1050"))
        self.assertEqual(rows[0]["ending_ap"], D("400"))
        self.assertEqual(rows[0]["ending_tax_liability"], D("50"))
        self.assertEqual(rows[1]["ending_cash"], D("-20"))
        self.assertEqual(rows[1]["tax_payments"], D("50"))
        self.assertEqual(rows[1]["ending_ar"], D("1000"))

    def test_growth_calendar_seasonality_and_override(self):
        factors = [1] * 12
        factors[11], factors[0], factors[1] = 2, 3, 4
        rows = forecast(simple(start_month="2027-12", monthly_growth_rate=.1, seasonality=factors,
                               revenue_overrides={"2028-01": 17}))["months"]
        self.assertEqual([r["revenue"] for r in rows], [D("2000"), D("17"), D("4840")])
        self.assertEqual([r["month"] for r in rows], ["2027-12", "2028-01", "2028-02"])

    def test_planned_hire_recurs_and_capex_is_cash_only(self):
        rows = forecast(simple(hires=[{"name": "Synthetic", "start_month": "2027-02", "monthly_cost": 100}],
                               capex={"2027-01": 500}))["months"]
        self.assertEqual([r["hire_payroll"] for r in rows], [D(0), D(100), D(100)])
        self.assertEqual(rows[0]["operating_income"], D(200))
        self.assertEqual(rows[0]["ending_cash"], D(-240))
        self.assertEqual(rows[1]["break_even_revenue"], D(800))

    def test_financing_interest_and_principal(self):
        row = forecast(simple(months=1, opening_debt=100, debt_draws={"2027-01": 200},
                              debt_principal={"2027-01": 50}, debt_interest={"2027-01": 20}))["months"][0]
        self.assertEqual(row["operating_income"], D(200))
        self.assertEqual(row["pretax_income"], D(180))
        self.assertEqual(row["tax_accrual"], D(36))
        self.assertEqual(row["ending_cash"], D(394))
        self.assertEqual(row["ending_debt"], D(250))

    def test_cash_runway_excludes_debt_draws_and_uses_available_trailing_months(self):
        result = forecast(simple(monthly_revenue=0, tax_rate=0, beginning_cash=1000,
                                 debt_draws={"2027-01": 600}, capex={"2027-01": 300}))
        rows = result["months"]
        self.assertEqual(rows[0]["cash_change_before_financing"], D(-600))
        self.assertEqual(rows[0]["ending_cash"], D(1000))
        self.assertEqual(rows[0]["cash_runway_months"], D("1.67"))
        self.assertEqual(rows[1]["cash_runway_months"], D("1.56"))
        self.assertEqual(rows[2]["cash_runway_months"], D("1.00"))

    def test_zero_contribution_and_cash_deficit(self):
        row = forecast(simple(months=1, gross_margin=.1, variable_opex_rate=.1, beginning_cash=0))["months"][0]
        self.assertIsNone(row["break_even_revenue"])
        self.assertEqual(row["tax_accrual"], D(0))
        self.assertEqual(row["cash_runway_months"], D(0))

    def test_cogs_and_margin_equivalence(self):
        a = simple()
        b = deepcopy(a)
        del b["gross_margin"]
        b["cogs_rate"] = .4
        self.assertEqual(forecast(a)["months"], forecast(b)["months"])

    def test_allocation_is_cent_exact_and_nonnegative(self):
        self.assertEqual(allocate(D("0.01"), [D(".5"), D(".5")]), [D(".01"), D("0")])
        self.assertEqual(allocate(D("0.02"), [D(".3"), D(".3"), D(".3"), D(".1")]),
                         [D(".01"), D(".01"), D("0"), D("0")])
        self.assertEqual(allocate(D(".07"), [D(".25"), D(".75"), D("0")]), [D(".02"), D(".05"), D("0")])

    def test_collections_beyond_horizon_remain_on_balance_sheet(self):
        row = forecast(simple(months=1, collection_weights=[0, 0, 1], payment_weights=[0, 1],
                              tax_lag_months=2))["months"][0]
        self.assertEqual(row["ending_ar"], D(1000))
        self.assertEqual(row["ending_ap"], D(400))
        self.assertEqual(row["ending_tax_liability"], D(40))

    def test_exact_half_up_rounding(self):
        row = forecast(simple(months=1, monthly_revenue=.05, gross_margin=.5,
                              fixed_opex=0, payroll=0, variable_opex_rate=0, tax_rate=0))["months"][0]
        self.assertEqual(row["cogs"], D(".03"))
        self.assertEqual(row["gross_profit"], D(".02"))

    def test_complete_revenue_loss_and_largest_supported_growth(self):
        rows = forecast(simple(monthly_growth_rate=-1))["months"]
        self.assertEqual([r["revenue"] for r in rows], [D(1000), D(0), D(0)])
        result = forecast(simple(months=60, monthly_revenue=10**12, monthly_growth_rate=1))
        self.assertEqual(len(result["months"]), 60)
        self.assertEqual(result["months"][-1]["cash_reconciliation_difference"], 0)

    def test_scenario_variance_and_top_level_schedule_replacement(self):
        model = run_model({"assumptions": simple(capex={"2027-01": 10}), "scenarios": {
            "downside": {"monthly_revenue": 800, "capex": {}}, "upside": {"monthly_revenue": 1200},
            "custom": {"cogs_rate": .4}}})
        down = model["scenarios"]["downside"]["months"][0]
        self.assertEqual(down["revenue_variance"], D(-200))
        self.assertEqual(down["operating_income_variance"], D(-100))
        self.assertEqual(down["ending_cash_variance"], D(-70))
        self.assertEqual(model["scenarios"]["custom"]["months"][0]["revenue_variance"], 0)
        self.assertEqual(model["scenarios"]["base"]["months"][0]["ending_cash_variance"], 0)

    def test_large_scenario_variances_preserve_cents(self):
        model = run_model({"assumptions": simple(months=60, monthly_revenue=10**12, monthly_growth_rate=1),
                           "scenarios": {"custom": {"fixed_opex": 100.01}}})
        row = model["scenarios"]["custom"]["months"][-1]
        self.assertEqual(row["operating_income_variance"], D("-.01"))
        self.assertEqual(row["ending_cash_variance"], D("-.60"))

    def test_seeded_randomized_cash_and_working_capital_invariants(self):
        rng = random.Random(1729)
        for _ in range(120):
            a = simple(months=rng.randint(1, 24), monthly_revenue=rng.randint(1, 200000),
                       monthly_growth_rate=D(rng.randint(-20, 20))/100,
                       gross_margin=D(rng.randint(0, 100))/100,
                       variable_opex_rate=D(rng.randint(0, 40))/100,
                       collection_weights=[D(".23"), D(".47"), D(".30")],
                       payment_weights=[D(".31"), D(".69")], tax_lag_months=rng.randint(0, 12),
                       opening_ar=[10, 20], opening_ap=[5], opening_tax_payments=[3])
            result = forecast(a)
            prior_ar, prior_ap, prior_tax, prior_cash = D(30), D(5), D(3), D(100)
            for r in result["months"]:
                self.assertEqual(r["ending_cash"], prior_cash+r["cash_inflows"]-r["cash_outflows"])
                self.assertEqual(r["ending_ar"], prior_ar+r["revenue"]-r["customer_receipts"])
                self.assertEqual(r["ending_ap"], prior_ap+r["cogs"]-r["supplier_payments"])
                self.assertEqual(r["ending_tax_liability"], prior_tax+r["tax_accrual"]-r["tax_payments"])
                self.assertEqual(r["cash_reconciliation_difference"], 0)
                prior_ar, prior_ap, prior_tax, prior_cash = r["ending_ar"], r["ending_ap"], r["ending_tax_liability"], r["ending_cash"]

    def test_shipped_sample_inputs_match(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual((root/"smb_forecast/sample.json").read_bytes(), (root/"examples/sample-business.json").read_bytes())
        sample = run_model(loads((root/"examples/sample-business.json").read_text()))
        self.assertEqual(set(sample["scenarios"]), {"base", "downside", "upside", "custom"})


class ValidationTests(unittest.TestCase):
    def test_invalid_scalar_boundaries(self):
        patches = [{"monthly_revenue": -1}, {"monthly_revenue": True}, {"monthly_revenue": "1000"},
                   {"monthly_revenue": float("nan")}, {"tax_rate": 1.1}, {"gross_margin": -.1},
                   {"months": 61}, {"months": 0}, {"months": 1.0}, {"monthly_growth_rate": -1.01},
                   {"tax_lag_months": 13}, {"unknown": 1}, {"start_month": "2027-13"},
                   {"start_month": "2099-12", "months": 2}, {"gross_margin": .6, "cogs_rate": .4}]
        for patch in patches:
            with self.subTest(patch=patch), self.assertRaises(ModelError):
                forecast(simple(**patch))

    def test_invalid_schedules(self):
        patches = [{"collection_weights": [.2, .2]}, {"payment_weights": []},
                   {"collection_weights": [1] * 14}, {"opening_ar": [-1]},
                   {"opening_ap": [0] * 14}, {"seasonality": [1] * 11},
                   {"seasonality": [6] * 12}, {"capex": {"2026-12": 1}},
                   {"debt_principal": {"2027-01": 1}}, {"debt_interest": {"2027-01": 1}},
                   {"hires": [{"name": "Role", "start_month": "2028-01", "monthly_cost": 100}]},
                   {"hires": [{"name": "Role", "start_month": "2027-01", "monthly_cost": 100, "other": 1}]}]
        for patch in patches:
            with self.subTest(patch=patch), self.assertRaises(ModelError):
                forecast(simple(**patch))

    def test_model_and_scenario_validation(self):
        docs = [[], {"unknown": 1}, {"schema_version": True}, {"assumptions": []},
                {"scenarios": {"base": {}}}, {"scenarios": {"../../escape": {}}},
                {"scenarios": {"downside": {"months": 2}}}, {"currency": "USD<script>"},
                {"model_name": ""}, {"scenarios": {"custom": {"gross_margin": .5, "cogs_rate": .5}}}]
        for doc in docs:
            with self.subTest(document=doc), self.assertRaises(ModelError):
                run_model(doc)

    def test_duplicate_nonfinite_and_invalid_json(self):
        for source in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{bad}', '['*2000):
            with self.subTest(source=source[:40]), self.assertRaises(ModelError):
                loads(source)


if __name__ == "__main__":
    unittest.main()
