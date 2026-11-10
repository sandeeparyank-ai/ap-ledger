# The A&P Ledger

Who in Southeast Asia is raising or cutting marketing spend, by how much, and the reason they give. Built from public company filings.

## How it works

1. **Fetch.** A scheduled GitHub Action (`.github/workflows/fetch.yml`) downloads recent results and annual reports for the companies in `companies.yaml` and saves them as plain text in `data/raw/`. US-listed companies come from SEC EDGAR. SGX-listed companies come from their announcements and investor sites.
2. **Extract.** Claude reads the text and records each marketing line to the rules in `extraction/spec.md`, with a verbatim quote and source for every figure.
3. **Check.** Every figure is matched back to the source text before anything is published.
4. **Publish.** A static page and a fortnightly email. Summaries and links only.

## Setup

Set one repository variable: Settings, Secrets and variables, Actions, Variables, `SEC_CONTACT` = your name and a contact email. The SEC requires a declared contact for scripted access.
