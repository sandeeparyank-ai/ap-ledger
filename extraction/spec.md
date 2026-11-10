# Extraction spec

One row per company per reporting period. Every figure must be traceable to a quote.

| Field | Rule |
|---|---|
| company, slug | From companies.yaml |
| period | As the filing states it, e.g. Q3 2026, 1H FY2026, FY2025 |
| period_end | ISO date |
| line_label | The exact label used in the filing, e.g. "Sales and marketing", "Advertising and promotion expenses" |
| line_type | ap (advertising and promotion only) or sm (sales and marketing, wider) or sd (selling and distribution, widest). Never compare across types without saying so |
| currency, unit | As stated, e.g. USD millions, SGD thousands |
| current, prior | Numbers exactly as printed, before any rounding |
| change_pct | Computed in code from current and prior, never typed by hand |
| revenue_current, revenue_prior | Same period, same unit, for the spend-to-revenue ratio |
| reason_quote | Management's stated reason, verbatim, 40 words max. null if none given. Never paraphrase into this field |
| quote_location | Page number or section heading |
| source_url | The document read |
| public_link | The link we publish (company investor site where one exists) |
| confidence | high (line item in a table) or medium (figure in narrative text) or none (no figure disclosed) |
| notes | Restatements, reclassifications, one-offs |

## Rules

1. If the company does not disclose a marketing figure, record confidence none and say what it does disclose. "Does not disclose" is a valid, publishable finding.
2. Search the whole document. Annual-report notes ("profit before tax is arrived at after charging", "expenses by nature") often hold the A&P line when the results announcement does not.
3. Prefer the line closest to advertising and promotion. Record wider lines only when nothing narrower exists.
4. Never infer a prior-year figure from a percentage. If only a percentage is given, store it in notes and leave prior empty.
5. Each run ends with a check pass in which every figure is re-found in the source text by string match. Rows that fail are flagged, not published.
