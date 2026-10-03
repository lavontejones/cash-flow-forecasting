"""Validated assumptions, explicit Decimal formulas, and cash reconciliation."""

from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import json
import re

ZERO = Decimal("0")
ONE = Decimal("1")
CENT = Decimal("0.01")
MAX_MONEY = Decimal("1000000000000")


class ModelError(ValueError):
    """An input is invalid or a forecast cannot reconcile."""


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def number(value, path, minimum=ZERO, maximum=MAX_MONEY):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ModelError(f"{path}: expected a number, not a string or boolean")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ModelError(f"{path}: invalid number") from exc
    if not result.is_finite() or not minimum <= result <= maximum:
        raise ModelError(f"{path}: must be finite and between {minimum} and {maximum}")
    return result


def integer(value, path, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ModelError(f"{path}: expected an integer from {minimum} to {maximum}")
    return value


def month_index(value, path="month"):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
        raise ModelError(f"{path}: use YYYY-MM")
    try:
        parsed = datetime.strptime(value, "%Y-%m")
    except ValueError as exc:
        raise ModelError(f"{path}: invalid calendar month") from exc
    if not 2000 <= parsed.year <= 2099:
        raise ModelError(f"{path}: year must be between 2000 and 2099")
    return parsed.year * 12 + parsed.month - 1


def month_label(index):
    year, offset = divmod(index, 12)
    return f"{year:04d}-{offset + 1:02d}"


DEFAULTS = {
    "start_month": "2027-01", "months": 12, "monthly_revenue": 100000,
    "monthly_growth_rate": 0, "seasonality": [1] * 12, "gross_margin": 0.55,
    "fixed_opex": 12000, "variable_opex_rate": 0.05, "payroll": 30000,
    "hires": [], "capex": {}, "collection_weights": [1], "payment_weights": [1],
    "opening_ar": [], "opening_ap": [], "tax_rate": 0,
    "tax_lag_months": 0, "opening_tax_payments": [], "beginning_cash": 100000,
    "opening_debt": 0, "debt_draws": {}, "debt_principal": {}, "debt_interest": {},
    "revenue_overrides": {},
}


def validate_assumptions(raw):
    if not isinstance(raw, dict):
        raise ModelError("assumptions: expected an object")
    unknown = set(raw) - set(DEFAULTS) - {"cogs_rate"}
    if unknown:
        raise ModelError(f"Unknown assumptions: {', '.join(sorted(unknown))}")
    if "gross_margin" in raw and "cogs_rate" in raw:
        raise ModelError("Use either gross_margin or cogs_rate, never both")
    a = deepcopy(DEFAULTS)
    a.update(deepcopy(raw))
    if "cogs_rate" in a:
        del a["gross_margin"]
    start = month_index(a["start_month"], "start_month")
    n = integer(a["months"], "months", 1, 60)
    if start + n - 1 > 2099 * 12 + 11:
        raise ModelError("Forecast must end before 2100")
    for key in ("monthly_revenue", "fixed_opex", "payroll", "beginning_cash", "opening_debt"):
        a[key] = money(number(a[key], key))
    for key in ("gross_margin", "cogs_rate", "variable_opex_rate", "tax_rate"):
        if key in a:
            a[key] = number(a[key], key, ZERO, ONE)
    a["monthly_growth_rate"] = number(a["monthly_growth_rate"], "monthly_growth_rate", -ONE, ONE)
    integer(a["tax_lag_months"], "tax_lag_months", 0, 12)
    if not isinstance(a["seasonality"], list) or len(a["seasonality"]) != 12:
        raise ModelError("seasonality: provide 12 calendar-month factors, January through December")
    a["seasonality"] = [number(x, f"seasonality[{i}]", ZERO, Decimal(5))
                         for i, x in enumerate(a["seasonality"])]
    for key in ("collection_weights", "payment_weights"):
        weights = a[key]
        if not isinstance(weights, list) or not 1 <= len(weights) <= 13:
            raise ModelError(f"{key}: provide 1 to 13 monthly fractions")
        a[key] = [number(x, f"{key}[{i}]", ZERO, ONE) for i, x in enumerate(weights)]
        if sum(a[key]) != ONE:
            raise ModelError(f"{key}: fractions must sum to exactly 1")
    for key in ("opening_ar", "opening_ap", "opening_tax_payments"):
        if not isinstance(a[key], list) or len(a[key]) > 13:
            raise ModelError(f"{key}: provide up to 13 scheduled monthly amounts")
        a[key] = [money(number(x, f"{key}[{i}]")) for i, x in enumerate(a[key])]
    for key in ("capex", "debt_draws", "debt_principal", "debt_interest", "revenue_overrides"):
        if not isinstance(a[key], dict):
            raise ModelError(f"{key}: expected a YYYY-MM to amount object")
        for label, amount in a[key].items():
            index = month_index(label, key)
            if not start <= index < start + n:
                raise ModelError(f"{key}.{label}: outside forecast horizon")
            a[key][label] = money(number(amount, f"{key}.{label}"))
    if not isinstance(a["hires"], list) or len(a["hires"]) > 100:
        raise ModelError("hires: expected a list of up to 100 planned hires")
    for i, hire in enumerate(a["hires"]):
        if not isinstance(hire, dict) or set(hire) != {"name", "start_month", "monthly_cost"}:
            raise ModelError(f"hires[{i}]: requires name, start_month, monthly_cost only")
        if not isinstance(hire["name"], str) or not 1 <= len(hire["name"]) <= 100:
            raise ModelError(f"hires[{i}].name: requires 1 to 100 characters")
        index = month_index(hire["start_month"], f"hires[{i}].start_month")
        if not start <= index < start + n:
            raise ModelError(f"hires[{i}].start_month: outside forecast horizon")
        hire["monthly_cost"] = money(number(hire["monthly_cost"], f"hires[{i}].monthly_cost"))
    return a


def allocate(amount, weights):
    """Allocate each invoice exactly; final nonzero bucket absorbs cent residual."""
    buckets = [ZERO] * len(weights)
    final = max(i for i, weight in enumerate(weights) if weight > ZERO)
    for i in range(final):
        buckets[i] = money(amount * weights[i])
    # Extremely small invoices can otherwise overallocate through repeated rounding.
    remaining = amount
    for i in range(final):
        buckets[i] = min(buckets[i], remaining)
        remaining -= buckets[i]
    buckets[final] = remaining
    return buckets


def add_cohort(schedule, t, amount, weights):
    for lag, portion in enumerate(allocate(amount, weights)):
        schedule[t + lag] += portion


def forecast(raw):
    with localcontext() as context:
        context.prec = 48
        return _forecast(validate_assumptions(raw))


def _forecast(a):
    n = a["months"]
    start = month_index(a["start_month"])
    receipts = [ZERO] * (n + 13)
    supplier_payments = [ZERO] * (n + 13)
    tax_payments = [ZERO] * (n + 13)
    for values, schedule in ((a["opening_ar"], receipts), (a["opening_ap"], supplier_payments),
                             (a["opening_tax_payments"], tax_payments)):
        for i, amount in enumerate(values):
            schedule[i] += amount
    cash = a["beginning_cash"]
    ar, ap, tax_liability = (sum(a[key], ZERO) for key in
                            ("opening_ar", "opening_ap", "opening_tax_payments"))
    debt = a["opening_debt"]
    margin = a.get("gross_margin", ONE - a.get("cogs_rate", ZERO))
    contribution = margin - a["variable_opex_rate"]
    rows = []
    for t in range(n):
        label = month_label(start + t)
        factor = a["seasonality"][(start + t) % 12]
        revenue = a["revenue_overrides"].get(label)
        if revenue is None:
            growth = ONE if t == 0 else (ONE + a["monthly_growth_rate"]) ** t
            revenue = money(a["monthly_revenue"] * growth * factor)
        cogs = money(revenue * (ONE - margin))
        gross_profit = revenue - cogs
        variable = money(revenue * a["variable_opex_rate"])
        hire_cost = sum((h["monthly_cost"] for h in a["hires"]
                         if month_index(h["start_month"]) <= start + t), ZERO)
        payroll = a["payroll"] + hire_cost
        opex = a["fixed_opex"] + variable + payroll
        operating_income = gross_profit - opex
        interest = a["debt_interest"].get(label, ZERO)
        pretax_income = operating_income - interest
        tax_accrual = money(max(pretax_income, ZERO) * a["tax_rate"])
        net_income = pretax_income - tax_accrual
        add_cohort(receipts, t, revenue, a["collection_weights"])
        add_cohort(supplier_payments, t, cogs, a["payment_weights"])
        tax_payments[t + a["tax_lag_months"]] += tax_accrual
        draws = a["debt_draws"].get(label, ZERO)
        principal = a["debt_principal"].get(label, ZERO)
        if principal > debt + draws:
            raise ModelError(f"debt_principal.{label}: payment exceeds outstanding debt plus draws")
        if interest > ZERO and debt + draws == ZERO:
            raise ModelError(f"debt_interest.{label}: interest entered without an outstanding debt balance")
        capex = a["capex"].get(label, ZERO)
        inflows = receipts[t] + draws
        outflows = supplier_payments[t] + opex + tax_payments[t] + capex + interest + principal
        delta = inflows - outflows
        previous_ar, previous_ap, previous_tax = ar, ap, tax_liability
        ar += revenue - receipts[t]
        ap += cogs - supplier_payments[t]
        tax_liability += tax_accrual - tax_payments[t]
        indirect = (net_income - (ar - previous_ar) + (ap - previous_ap)
                    + (tax_liability - previous_tax) - capex + draws - principal)
        if indirect != delta or min(ar, ap, tax_liability) < ZERO:
            raise ModelError(f"{label}: cash or working-capital reconciliation failed")
        beginning = cash
        cash += delta
        debt += draws - principal
        recent_changes = [r["cash_change_before_financing"] for r in rows[-2:]] + [delta - draws]
        burn = max(-sum(recent_changes, ZERO) / len(recent_changes), ZERO)
        runway = ZERO if cash <= ZERO else (money(cash / burn) if burn > ZERO else None)
        break_even = money((a["fixed_opex"] + payroll) / contribution) if contribution > ZERO else None
        rows.append({
            "month": label, "revenue": revenue, "cogs": cogs, "gross_profit": gross_profit,
            "fixed_opex": a["fixed_opex"], "variable_opex": variable, "base_payroll": a["payroll"],
            "hire_payroll": hire_cost, "payroll": payroll, "operating_expenses": opex,
            "operating_income": operating_income, "interest_expense": interest,
            "pretax_income": pretax_income, "tax_accrual": tax_accrual, "net_income": net_income,
            "customer_receipts": receipts[t], "debt_draws": draws, "cash_inflows": inflows,
            "supplier_payments": supplier_payments[t], "tax_payments": tax_payments[t],
            "capex": capex, "debt_principal": principal, "cash_outflows": outflows,
            "beginning_cash": beginning, "cash_change": delta,
            "cash_change_before_financing": delta - draws, "ending_cash": cash,
            "ending_ar": ar, "ending_ap": ap, "ending_tax_liability": tax_liability,
            "ending_debt": debt, "trailing_average_burn": money(burn),
            "cash_runway_months": runway, "break_even_revenue": break_even,
            "cash_reconciliation_difference": indirect - delta,
        })
    summary = {"total_revenue": sum((r["revenue"] for r in rows), ZERO),
               "total_operating_income": sum((r["operating_income"] for r in rows), ZERO),
               "total_cash_inflows": sum((r["cash_inflows"] for r in rows), ZERO),
               "total_cash_outflows": sum((r["cash_outflows"] for r in rows), ZERO),
               "ending_cash": cash, "minimum_ending_cash": min(r["ending_cash"] for r in rows),
               "first_negative_cash_month": next((r["month"] for r in rows if r["ending_cash"] < ZERO), None),
               "cash_runway_months": rows[-1]["cash_runway_months"],
               "ending_ar": ar, "ending_ap": ap, "ending_tax_liability": tax_liability, "ending_debt": debt}
    return {"assumptions": a, "months": rows, "summary": summary}


def run_model(document):
    with localcontext() as context:
        context.prec = 48
        return _run_model(document)


def _run_model(document):
    if not isinstance(document, dict):
        raise ModelError("Model must be a JSON object")
    unknown = set(document) - {"schema_version", "model_name", "currency", "assumptions", "scenarios"}
    if unknown:
        raise ModelError(f"Unknown model fields: {', '.join(sorted(unknown))}")
    integer(document.get("schema_version", 1), "schema_version", 1, 1)
    name = document.get("model_name", "SMB Cash Flow Forecast")
    if not isinstance(name, str) or not 1 <= len(name) <= 120:
        raise ModelError("model_name: provide 1 to 120 characters")
    currency = document.get("currency", "USD")
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
        raise ModelError("currency: provide a three-letter uppercase display label")
    assumptions = document.get("assumptions", {})
    base = forecast(assumptions)
    scenarios = document.get("scenarios", {})
    if not isinstance(scenarios, dict) or len(scenarios) > 10:
        raise ModelError("scenarios: provide an object with at most 10 named assumption patches")
    results = {"base": base}
    for scenario_name, patch in scenarios.items():
        if not isinstance(scenario_name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", scenario_name):
            raise ModelError("Scenario names must be lowercase identifiers, up to 32 characters")
        if scenario_name == "base" or not isinstance(patch, dict):
            raise ModelError("Scenario base is reserved; each scenario must be an assumption object")
        if "months" in patch or "start_month" in patch:
            raise ModelError("Scenarios must share the baseline horizon for variance comparisons")
        merged = deepcopy(assumptions)
        if "cogs_rate" in patch:
            merged.pop("gross_margin", None)
        if "gross_margin" in patch:
            merged.pop("cogs_rate", None)
        merged.update(deepcopy(patch))
        results[scenario_name] = forecast(merged)
    for result in results.values():
        for row, baseline in zip(result["months"], base["months"]):
            for metric in ("revenue", "operating_income", "ending_cash", "cash_change"):
                row[f"{metric}_variance"] = row[metric] - baseline[metric]
    return {"schema_version": 1, "model_name": name, "currency": currency, "scenarios": results}


def dumps(value, **kwargs):
    """Money/rates stay decimal strings in outputs; no binary float arithmetic."""
    return json.dumps(value, default=lambda x: str(x) if isinstance(x, Decimal) else x, **kwargs)


def loads(value):
    def object_pairs(pairs):
        obj = {}
        for key, item in pairs:
            if key in obj:
                raise ModelError(f"Duplicate JSON key: {key}")
            obj[key] = item
        return obj
    def reject_constant(value):
        raise ModelError(f"Non-finite JSON number: {value}")
    try:
        return json.loads(value, parse_float=Decimal, object_pairs_hook=object_pairs,
                          parse_constant=reject_constant)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ModelError(f"Invalid JSON: {exc}") from exc
