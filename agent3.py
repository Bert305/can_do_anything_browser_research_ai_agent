"""
Reads dir_awardees.csv, visits each detail_url, and extracts
Contact phone / e-mail and Website.

Output: dir_awardees_full.csv
  (trade, committee, type, detail_url, contact, website)
"""

import csv
import re
import time
import requests
from bs4 import BeautifulSoup

INPUT_CSV  = "dir_awardees_full.csv"
OUTPUT_CSV = "dir_awardees_complete.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}")


def scrape_detail(url: str) -> dict:
    phone   = ""
    email   = ""
    website = "NA"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Email: mailto link is most reliable
        mailto = soup.find("a", href=re.compile(r"^mailto:", re.I))
        if mailto:
            email = mailto["href"].replace("mailto:", "").strip()

        # Website: first external link (not dir.ca.gov)
        for a in soup.find_all("a", href=re.compile(r"^https?://", re.I)):
            if "dir.ca.gov" not in a["href"]:
                website = a["href"].strip()
                break

        # Phone: find the "Contact phone / e-mail" table row and scan value cell
        for tr in soup.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                if "phone" in label or "contact" in label:
                    value = cells[-1].get_text(" ", strip=True)
                    m = PHONE_RE.search(value)
                    if m:
                        phone = m.group().strip()
                    break

        # Fallback: scan full page text for a phone pattern
        if not phone:
            m = PHONE_RE.search(soup.get_text())
            if m:
                phone = m.group().strip()

        # Website fallback: scan text for a URL after "website" label
        if website == "NA":
            lines = [l.strip() for l in soup.get_text(separator="\n").splitlines() if l.strip()]
            for i, line in enumerate(lines):
                if "website" in line.lower():
                    candidate = re.sub(r"(?i)website\s*[:/\-]?\s*", "", line).strip()
                    nxt = lines[i + 1] if i + 1 < len(lines) else ""
                    website = candidate or nxt or "NA"
                    break

    except Exception as exc:
        print(f"  [warn] {url}: {exc}")

    parts = [p for p in [phone, email] if p]
    return {
        "contact": " / ".join(parts) if parts else "NA",
        "website": website,
    }


def main():
    # Read input CSV
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} rows from {INPUT_CSV}\n")

    results = []
    for i, row in enumerate(rows, 1):
        url = row.get("detail_url", "").strip()
        print(f"[{i}/{len(rows)}] {row.get('trade', '')} — {url}")

        if url:
            detail = scrape_detail(url)
        else:
            detail = {"contact": "NA", "website": "NA"}

        results.append({
            "trade":      row.get("trade", ""),
            "committee":  row.get("committee", ""),
            "type":       row.get("type", ""),
            "detail_url": url,
            "contact":    detail["contact"],
            "website":    detail["website"],
        })
        time.sleep(0.25)

    # Write output CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["trade", "committee", "type", "detail_url", "contact", "website"]
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"\nDone. {len(results)} rows saved to {OUTPUT_CSV}")


main()
