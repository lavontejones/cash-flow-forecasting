# Audit record

Audit date: 2026-10-03 UTC. Scope: this cash-flow model, its interfaces, sample exports, documentation, and validation workflow. The parent repository's older variance tool is outside this model audit.

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

## Remote verification

The local execution environment disallows opening listener sockets, and browser access is unavailable. Real loopback integration tests, installed-package checks, and dashboard browser acceptance are included in GitHub Actions for execution after upload. They have not run in this session. The browser check exercises scenario selection, edits, invalid inputs, CSV/input/report downloads, duplicate-key rejection, escaping, and mobile overflow.

GitHub account identity and existing repository metadata were verified through the connector. Creation of a review branch was rejected by automatic approval review because the session's approval policy is `never`; no branch, commit, pull request, or repository was created or changed. The delivered archive is standalone repository source and includes a working validation workflow. Remote verification remains pending.

## Release judgment

The audited source and synthetic examples are suitable for public portfolio review. Full acceptance of the local dashboard remains contingent on passing remote integration and browser checks. This is not a production-hosting, client-delivery, tax-treatment, or accounting certification. Material limitations are disclosed in the [README](../README.md) and [formula reference](formulas.md).

The repository scanner is a bounded set of patterns, not a guarantee of complete secret detection. Runtime behavior is validated through tests and source review; no claims of client outcomes or predictive accuracy are made.
