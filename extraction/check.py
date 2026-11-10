"""Check every extracted figure and quote against its source text, then build the spot-check sheet.

Usage: python extraction/check.py extraction/rows_test_set.json
Writes extraction/checked_<name>.csv and extraction/spotcheck_<name>.md
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def norm(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def num(s):
    return float(s.replace(",", "")) if s else None


def find_number(text, n):
    """Find a printed figure as a whole token (not inside a longer number)."""
    m = re.search(rf"(?<![\d,.]){re.escape(n)}(?![\d,]|\.\d)", text)
    return m.start() if m else -1


def find_row(text, label, cur, pri):
    """Character offset of the first line holding both figures with the label on it or the line above."""
    key = norm(" ".join(label.split()[:3]))
    offset, prev = 0, ""
    for line in text.split("\n"):
        if find_number(line, cur) >= 0 and find_number(line, pri) >= 0 and key in norm(prev + " " + line):
            return offset
        offset += len(line) + 1
        prev = line
    return None


def page_of(text, pos):
    return text.count("\f", 0, pos) + 1 if "\f" in text and pos >= 0 else None


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1 if pos >= 0 else None


def main(path):
    rows = json.loads(Path(path).read_text())
    manifest = json.loads((ROOT / "data" / "manifest.json").read_text())
    by_file = {v.get("text_file"): v for v in manifest.values() if isinstance(v, dict) and v.get("text_file")}
    out = []
    for r in rows:
        text = (ROOT / r["file"]).read_text()
        flat = norm(text)
        problems = []
        locs = {}
        for f in ("current", "prior", "revenue_current", "revenue_prior"):
            if r.get(f):
                pos = find_number(text, r[f])
                locs[f] = pos
                if pos < 0:
                    problems.append(f"{f} {r[f]} not found")
        if r.get("current") and r.get("prior"):
            # Strong check: one table row carries the label (allowing it to wrap onto the
            # previous line) plus both figures.
            row = find_row(text, r.get("line_label") or "", r["current"], r["prior"])
            if row is None:
                problems.append("no single row holds the label with both figures")
            else:
                locs["current"] = row
        if r.get("reason_quote") and norm(r["reason_quote"]) not in flat:
            problems.append("reason quote not found verbatim")
        c, p = num(r.get("current")), num(r.get("prior"))
        rc, rp = num(r.get("revenue_current")), num(r.get("revenue_prior"))
        change = round((c - p) / p * 100, 1) if c is not None and p else None
        ratio_c = round(c / rc * 100, 1) if c is not None and rc else None
        ratio_p = round(p / rp * 100, 1) if p is not None and rp else None
        pos = locs.get("current", -1)
        src = by_file.get(r["file"], {})
        out.append({
            **r,
            "change_pct": change,
            "spend_to_revenue_current_pct": ratio_c,
            "spend_to_revenue_prior_pct": ratio_p,
            "page": page_of(text, pos),
            "text_line": line_of(text, pos),
            "source_url": src.get("source_url"),
            "public_link": src.get("public_link", src.get("source_url")),
            "check": "PASS" if not problems else "FLAG: " + "; ".join(problems),
        })

    stem = Path(path).stem.replace("rows_", "")
    csv_path = ROOT / "extraction" / f"checked_{stem}.csv"
    with csv_path.open("w", newline="") as fh:
        fields = list(dict.fromkeys(k for o in out for k in o))
        w = csv.DictWriter(fh, fieldnames=fields, restval="")
        w.writeheader()
        w.writerows(out)

    md = ["# Spot-check sheet", "",
          "For each row, open the link, find the figure (page or line given), and tick if it matches.", "",
          "| # | Company | Period | Line | Current | Prior | Change | Where | Link | Auto-check | Your tick |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, o in enumerate(out, 1):
        where = f"p.{o['page']}" if o["page"] else (f"text line {o['text_line']}" if o["text_line"] else "-")
        chg = f"{o['change_pct']:+.1f}%" if o["change_pct"] is not None else "-"
        md.append(f"| {i} | {o['company']} | {o['period']} | {o['line_label'] or 'not disclosed'} | "
                  f"{o['current'] or '-'} | {o['prior'] or '-'} | {chg} | {where} | "
                  f"[open]({o['public_link']}) | {o['check']} | |")
    md_path = ROOT / "extraction" / f"spotcheck_{stem}.md"
    md_path.write_text("\n".join(md) + "\n")

    flags = [o for o in out if o["check"] != "PASS"]
    print(f"{len(out)} rows, {len(out) - len(flags)} pass, {len(flags)} flagged")
    for o in flags:
        print(f"  {o['company']}: {o['check']}")
    for o in out:
        print(f"  {o['company']:<18} {o['period']:<10} {str(o['change_pct']):>7}%  ratio {o['spend_to_revenue_prior_pct']} -> {o['spend_to_revenue_current_pct']}  {o['check'][:4]}")


if __name__ == "__main__":
    main(sys.argv[1])
