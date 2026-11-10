"""Build the public page from checked ledger rows and the current issue.

Usage: python site/build.py
Writes site/public/index.html (full page for GitHub Pages) and site/preview.html (body-only, for previews).
Only rows that passed the checker (or are marked pending / not disclosed) are published.
"""
import json
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"


def main():
    rows = json.loads((ROOT / "extraction" / "checked_ledger.json").read_text())
    companies = {c["slug"]: c for c in yaml.safe_load((ROOT / "companies.yaml").read_text())["companies"]}
    config = yaml.safe_load((SITE / "config.yaml").read_text())
    issues = sorted((ROOT / "issues").glob("issue-*.json"))
    issue = json.loads(issues[-1].read_text())

    published = []
    for r in rows:
        if r["check"] not in ("PASS", "SKIPPED"):
            continue  # flagged rows never reach the page
        if r.get("confidence") == "excluded":
            continue
        c = companies.get(r["slug"], {})
        r["sector"] = c.get("sector", "")
        r["listing"] = "US" if c.get("source") == "edgar" else "SGX"
        published.append(r)

    data = {"rows": published, "issue": issue, "config": config, "built": date.today().strftime("%-d %B %Y")}
    tpl = (SITE / "template.html").read_text()
    head, body = tpl.split("<!--BODY-->")
    body = body.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))

    (SITE / "preview.html").write_text(head + body)
    out = SITE / "public"
    out.mkdir(exist_ok=True)
    (out / "index.html").write_text(
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + head + "</head>\n<body>\n" + body + "</body>\n</html>\n")
    (out / ".nojekyll").write_text("")
    print(f"Built {len(published)} rows, issue {issue['number']}")


if __name__ == "__main__":
    main()
