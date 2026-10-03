# SMB Cash Flow & Forecasting Model

A functional FP&A portfolio project by **Lavonte Jones**. Build a monthly operating plan, compare base/downside/upside/custom scenarios, and trace revenue through customer collections to ending cash.

The tool includes an editable local dashboard, transparent calculations, cash runway and operating break-even estimates, monthly scenario variances, CSV exports, and an HTML management report. All included business data is synthetic.

**[Read the full project documentation](smb-cash-flow-forecast/README.md)** for the case study, sample findings, architecture, limitations, and detailed usage.

## Run locally

Python 3.9 or newer; no runtime dependencies or credentials are required.

```sh
cd smb-cash-flow-forecast
python3 -m smb_forecast forecast examples/sample-business.json --out output
python3 -m smb_forecast serve
```

Open `output/report.html` for the report or visit `http://127.0.0.1:8765` for the dashboard.

## Explore the model

- [Assumptions and validation rules](smb-cash-flow-forecast/docs/assumptions.md)
- [Calculation formulas](smb-cash-flow-forecast/docs/formulas.md)
- [Independent worked example](smb-cash-flow-forecast/docs/worked-example.md)
- [Sample inputs](smb-cash-flow-forecast/examples/sample-business.json) and [base forecast CSV](smb-cash-flow-forecast/examples/outputs/base.csv)
- [Audit record](smb-cash-flow-forecast/docs/audit.md) and [automated validation](https://github.com/lavontejones/cash-flow-forecasting/actions/workflows/validate.yml)

GitHub Actions checks calculations on Python 3.9 and 3.12, HTTP interfaces, reproducible exports, package resources, and browser behavior. The local application is designed for a single user.

This tool provides calculations only, without financial, tax, legal, or investment advice. [MIT licensed](smb-cash-flow-forecast/LICENSE).
