# Audit record

Audit date: 2026-10-03 UTC. Scope: this cash-flow model, its interfaces, sample exports, documentation, and validation workflow.

## Completed local audit

| Area | Evidence / result |
|---|---|
| Core calculations | 20 model test methods passed, including independently calculated examples and 120 fixed-seed forecast cases |
| Export behavior | 5 export/CLI test methods passed; all committed CSV/JSON/HTML outputs regenerate exactly |
| HTTP parsing and restrictions | 4 in-memory HTTP test methods passed using the actual request parser and handlers |
| JavaScript syntax | `node --check smb_forecast/web/app.js` passed |
| Formula transparency | All input fields, cash timing conventions, balance roll-forwards, runway, and break-even are documented |
| Data provenance | Only authored synthetic figures and role labels; no client data imported |
| Public-content review | Bounded credential/path scan and local-link checks implemented; no runtime credential requirement |
| Rendering safety | Dashboard uses text nodes for model labels; report escaping is tested; export paths use constrained scenario names |
| Dependency surface | Python runtime is standard-library only; Playwright is development-only; Actions are pinned to verified commit SHAs |

Boundary testing found a Decimal `0^0` error at a monthly growth rate of −100%; the first-month growth factor is now explicitly 1. Rounding allocation was checked for tiny invoices so rounded collection buckets cannot exceed the invoice amount. Large supported horizons/inputs are tested with 48-digit precision, including scenario comparison arithmetic.

## GitHub Actions verification

[Workflow run #4](https://github.com/lavontejones/cash-flow-forecasting/actions/runs/37096241821) completed successfully on 2026-10-03 UTC for commit `35a2cf54e33281d70853dd3509c5302fea741342`.

| Check | Verified result |
|---|---|
| Python 3.9 and 3.12 | All 33 tests passed on each version, including four real loopback HTTP integration tests |
| Sample reproducibility and content checks | Committed exports regenerate exactly; all assumptions are documented; no flagged public-content issues |
| Installed package | Installation and bundled sample/web resource checks passed |
| Browser acceptance | Scenario selection, assumption edits, invalid-input handling, CSV/input/report downloads, duplicate-key rejection, text escaping, minimal-input editing, and mobile overflow checks passed |
| Dashboard previews | Desktop and 390-pixel mobile screenshots were saved as workflow artifacts |

The active workflow is `.github/workflows/validate.yml` at the repository root; commands run inside `smb-cash-flow-forecast/`. Initial browser runs exposed test-harness issues: an input's timing panel needed opening before editing, and a polling helper conflicted with the application's Content Security Policy. The acceptance script now opens the panel through the UI and waits for enabled controls. The application's security policy remains in place.

## Release judgment

The audited source and synthetic examples are suitable for public portfolio review. Calculation, integration, package, and browser acceptance checks have passed in GitHub Actions. This is not a production-hosting, client-delivery, tax-treatment, or accounting certification. Material limitations are disclosed in the [README](../README.md) and [formula reference](formulas.md).

The repository scanner is a bounded set of patterns, not a guarantee of complete secret detection. Runtime behavior is validated through tests and source review; no claims of client outcomes or predictive accuracy are made.
