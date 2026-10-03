# Security and data handling

The application is intended for local, single-user operation. It binds only to `127.0.0.1`, checks the exact Host header, blocks supplied cross-origin POST requests, accepts only bounded JSON request bodies, and exposes a fixed route map rather than a filesystem browser. It does not transmit assumptions to external services or log request payloads.

The browser uses DOM text nodes for user-supplied labels; the report escapes model names and assumption values. CSV fields contain generated months, numbers, or blanks. Scenario identifiers are constrained and cannot become export paths. Unknown fields, duplicate JSON keys, invalid schedules, out-of-range values, and non-finite inputs are rejected.

This is not an authenticated multiuser web service. Do not expose the dashboard through a public tunnel or deploy the development server as a production application. Local malware or another process running as the same user is outside the trust boundary. Client adaptation requires a separate review of data access, retention, source integrity, and deployment controls.

Keep private inputs in ignored `local-data/` and generated reports in ignored `output/`. An ignore file does not remove previously committed information. The sample repository contains no client data or credentials; the bounded repository scanner supplements human review and cannot guarantee detection of every possible secret.

For a vulnerability report, use the hosting repository's private security reporting channel when enabled. Do not include client data, secrets, or live exploit payloads in public issues.
