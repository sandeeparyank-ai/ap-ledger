"""Fetch listed documents (PDF or HTML) for SGX and other non-EDGAR companies.

Each company in companies.yaml with source: urls has a docs list of {url, kind, period}.
Files are converted to text under data/raw/<slug>/ and recorded in data/manifest.json.
Company investor-relations copies are preferred as the public link where one exists.
"""
import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from urllib.parse import urljoin

import requests
import yaml
from bs4 import BeautifulSoup

from fetch_edgar import html_to_text  # same text conversion for HTML pages

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "manifest.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; AP-Ledger research; +https://github.com)"}


def pdf_to_text(content):
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "doc.pdf"
        pdf.write_bytes(content)
        # -layout keeps table columns aligned, which matters for figures.
        out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                             capture_output=True, text=True, check=True)
        return out.stdout


def is_pdf(resp):
    return resp.content[:4] == b"%PDF" or "pdf" in resp.headers.get("content-type", "").lower()


def attachment_links(html, base_url):
    """PDF attachment links on an SGX announcement page, in page order, without duplicates."""
    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        if re.search(r"\.pdf($|\?)|FileOpen", href, re.I) and href not in seen:
            seen.add(href)
            out.append(href)
    return out


def main():
    cfg = yaml.safe_load((ROOT / "companies.yaml").read_text())
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}
    failures = []
    for c in cfg["companies"]:
        if c["source"] != "urls":
            continue
        for d in c.get("docs", []):
            url = d["url"]
            key = f"{c['slug']}/{hashlib.sha1(url.encode()).hexdigest()[:10]}"
            if key in manifest:
                continue
            try:
                r = requests.get(url, headers=UA, timeout=120)
                r.raise_for_status()
            except Exception as e:  # noqa: BLE001
                failures.append(f"{c['slug']}: {url} {e}")
                continue
            # An SGX announcement page is HTML that links to PDF attachments. Follow them.
            if not is_pdf(r):
                pdfs = attachment_links(r.text, url)
                if pdfs:
                    targets = pdfs[:6]
                else:
                    targets = [(url, r)]
            else:
                targets = [(url, r)]
            saved_any = False
            for item in targets:
                turl, resp = (item, None) if isinstance(item, str) else item
                try:
                    if resp is None:
                        time.sleep(1)
                        resp = requests.get(turl, headers=UA, timeout=120)
                        resp.raise_for_status()
                    text = pdf_to_text(resp.content) if is_pdf(resp) else html_to_text(resp.text)
                except Exception as e:  # noqa: BLE001
                    failures.append(f"{c['slug']}: {turl} {e}")
                    continue
                if len(text.strip()) < 500:
                    failures.append(f"{c['slug']}: {turl} gave almost no text (scanned PDF?)")
                    continue
                stem = re.sub(r"[^A-Za-z0-9]+", "_", Path(turl.split("?")[0]).stem)[:60]
                name = re.sub(r"[^A-Za-z0-9]+", "_", f"{d.get('period', '')}_{d.get('kind', 'doc')}").strip("_")
                out = RAW / c["slug"] / f"{name}_{stem}.txt"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(text)
                manifest[f"{key}/{stem}"] = {
                    "company": c["name"], "slug": c["slug"], "form": d.get("kind"), "period": d.get("period"),
                    "source_url": turl, "announcement_url": url, "public_link": d.get("public_link", turl),
                    "text_file": str(out.relative_to(ROOT)), "chars": len(text),
                }
                saved_any = True
                print(f"saved {out.relative_to(ROOT)} ({len(text):,} chars)")
            if saved_any:
                manifest[key] = {"announcement_url": url, "done": True}
            time.sleep(1)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    if failures:
        print("\nFAILURES:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
