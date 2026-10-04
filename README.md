```mermaid
flowchart LR
    A[Business assumptions] --> B[Forecast Engine]
    B --> C[Base]
    B --> D[Downside]
    B --> E[Upside]
    C --> F[Cash Forecast]
    D --> F
    E --> F
    F --> G[Dashboard + CSV + HTML Report]
```

## At a glance

| Capability | Included |
| --- | --- |
| 12-month forecasting | Yes |
| Scenario modeling | Base / Downside / Upside / Custom |
| Cash runway | Yes |
| Break-even analysis | Yes |
| CSV export | Yes |
| HTML management report | Yes |
| Live accounting integration | No |
