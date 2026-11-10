"""Fetch recent SEC filings (6-K earnings releases and 20-F annual reports) for US-listed SEA companies.

Reads companies.yaml, resolves tickers to CIKs, downloads the relevant documents,
converts them to plain text under data/raw/<slug>/, and records each file in data/manifest.json.

SEC fair-access rules: declared User-Agent with contact, max 10 requests per second.
"""
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "manifest.json"

UA = {}

LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "400"))
EARNINGS_HINTS = re.compile(r"earning|result|press|ex99|ex-99|exhibit99", re.I)

_last = 0.0


def get(url, **kw):
    """Polite GET, about 5 requests per second, with simple retry."""
    global _last
    for attempt in range(3):
        wait = 0.2 - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        r = requests.get(url, headers=UA, timeout=60, **kw)
        if r.status_code == 200:
            return r
        if r.status_code in (429, 503):
            time.sleep(5 * (attempt + 1))
            continue
        r.raise_for_status()
    r.raise_for_status()


def html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style"]):
        t.decompose()
    # Keep table rows on one line so figures stay next to their labels.
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        tr.replace_with(" | ".join(c for c in cells if c) + "\n")
    text = soup.get_text("\n")
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def load_manifest():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {}


def main():
    contact = os.environ.get("SEC_CONTACT", "").strip()
    if not contact:
        sys.exit("Set SEC_CONTACT (name and email) as a repository variable. SEC requires it.")
    UA["User-Agent"] = f"AP-Ledger research {contact}"
    cfg = yaml.safe_load((ROOT / "companies.yaml").read_text())
    us = [c for c in cfg["companies"] if c["source"] == "edgar"]
    tickers = get("https://www.sec.gov/files/company_tickers.json").json()
    cik_by_ticker = {v["ticker"].upper(): int(v["cik_str"]) for v in tickers.values()}
    manifest = load_manifest()
    since = date.today() - timedelta(days=LOOKBACK_DAYS)
    failures = []

    for c in us:
        slug, ticker = c["slug"], c["ticker"].upper()
        cik = c.get("cik") or cik_by_ticker.get(ticker)
        if not cik:
            failures.append(f"{slug}: ticker {ticker} not found on EDGAR")
            continue
        sub = get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json").json()
        rec = sub["filings"]["recent"]
        rows = zip(rec["form"], rec["accessionNumber"], rec["filingDate"], rec["primaryDocument"])
        annual_done = False
        for form, acc, fdate, primary in rows:
            if date.fromisoformat(fdate) < since:
                break
            want_annual = form in ("20-F", "10-K") and not annual_done
            if form not in ("6-K", "8-K", "10-Q") and not want_annual:
                continue
            acc_path = acc.replace("-", "")
            base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_path}"
            try:
                index = get(f"{base}/index.json").json()["directory"]["item"]
            except Exception as e:  # noqa: BLE001
                failures.append(f"{slug}: index {acc} {e}")
                continue
            docs = [i["name"] for i in index if i["name"].lower().endswith((".htm", ".html"))]
            if want_annual or form == "10-Q":
                docs = [primary]
                annual_done = True
            else:
                docs = [d for d in docs if EARNINGS_HINTS.search(d)] or [primary]
            for d in docs:
                url = f"{base}/{d}"
                key = f"{slug}/{acc_path}_{d}"
                if key in manifest:
                    continue
                try:
                    text = html_to_text(get(url).text)
                except Exception as e:  # noqa: BLE001
                    failures.append(f"{slug}: {url} {e}")
                    continue
                # Skip short cover-page 6-Ks that are not results.
                if form in ("6-K", "8-K", "10-Q") and not re.search(r"marketing|advertis|promotion", text, re.I):
                    continue
                out = RAW / slug / f"{fdate}_{form}_{acc_path}_{Path(d).stem}.txt"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text)
                manifest[key] = {
                    "company": c["name"], "slug": slug, "form": form, "filed": fdate,
                    "source_url": url, "text_file": str(out.relative_to(ROOT)), "chars": len(text),
                }
                print(f"saved {out.relative_to(ROOT)} ({len(text):,} chars)")

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    if failures:
        print("\nFAILURES:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
