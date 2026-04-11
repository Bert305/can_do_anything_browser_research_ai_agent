"""
Scrapes the CA DIR apprenticeship results table and saves to CSV.

Fetches Trade or Occupation, Committee, Type, and detail href
from every page of results at the given URL.

Output: dir_awardees.csv
"""

import csv
import re
import time
import requests
from bs4 import BeautifulSoup

START_URL = (
    "https://www.dir.ca.gov/databases/das/aigstart.asp"
    "?VarType=Central+Valley+Motherlode+Plumbers%2C+Pipe+%26+Refrigeration+Fitters+JATC"
    "&Submit=Search&VarCounty=All"
)
BASE_URL   = "https://www.dir.ca.gov"
OUTPUT_CSV = "dir_awardees.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def scrape_all_pages() -> list[dict]:
    rows = []
    url = START_URL
    page_num = 1

    while url:
        print(f"  Page {page_num}: {url}")
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            print(f"  [stop] HTTP {resp.status_code} — no more pages")
            break
        soup = BeautifulSoup(resp.text, "html.parser")

        for tr in soup.select("table tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            link = cells[0].find("a", href=re.compile(r"results_aigdetail", re.I))
            if not link:
                continue

            trade = link.get_text(strip=True)
            href  = link.get("href", "")
            if href and not href.startswith("http"):
                prefix = "" if href.startswith("/") else "/databases/das/"
                href = BASE_URL + prefix + href

            committee = cells[1].get_text(strip=True)
            type_     = cells[2].get_text(strip=True) if len(cells) > 2 else ""

            rows.append({
                "trade":      trade,
                "committee":  committee,
                "type":       type_,
                "detail_url": href,
            })

        # Follow "Next" pagination link if present — must point back to aigstart/aigresult
        next_a = soup.find("a", string=re.compile(r"next|>>", re.I))
        if next_a and next_a.get("href"):
            next_href = next_a["href"]
            if not next_href.startswith("http"):
                prefix = "" if next_href.startswith("/") else "/databases/das/"
                next_href = BASE_URL + prefix + next_href
            # Only follow if it looks like a search results page
            if re.search(r"aig(start|result)", next_href, re.I):
                url = next_href
                page_num += 1
                time.sleep(0.3)
            else:
                break
        else:
            break

    return rows


def main():
    print(f"Scraping: {START_URL}\n")
    rows = scrape_all_pages()
    print(f"\nFound {len(rows)} rows. Writing {OUTPUT_CSV} ...")

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["trade", "committee", "type", "detail_url"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. {len(rows)} rows saved to {OUTPUT_CSV}")


main()
