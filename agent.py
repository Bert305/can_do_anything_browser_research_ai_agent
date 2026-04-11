import csv
import os
from playwright.sync_api import sync_playwright

BASE_URL = "https://dashboard.workforce.miami"
TARGET_URL = f"{BASE_URL}/?job_type=Apprenticeship#jobs-section"
OUTPUT_CSV = "apprenticeship_jobs.csv"
CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
USER_DATA_DIR = os.path.expanduser("~/.config/browseruse/profiles/default")


def click_load_more(page):
    """Keep clicking Load More until it disappears or is disabled."""
    while True:
        btn = page.locator("button", has_text="Load").first
        try:
            btn.wait_for(state="visible", timeout=4000)
        except Exception:
            print("No more 'Load More' button — all listings loaded.")
            break

        if btn.is_disabled():
            print("'Load More' is disabled — all listings loaded.")
            break

        count_before = page.locator("a[href^='/jobs/']").count()
        print(f"Clicking 'Load More' (currently {count_before} links)...")
        btn.scroll_into_view_if_needed()
        btn.click()

        # Wait until new cards actually appear in the DOM
        try:
            page.wait_for_function(
                f"document.querySelectorAll(\"a[href^='/jobs/']\").length > {count_before}",
                timeout=8000,
            )
        except Exception:
            break

        page.wait_for_timeout(800)


def extract_jobs(page):
    """
    For every Details link, walk up to the enclosing card and grab
    the h3 job title alongside the href. Returns [{name, detail_url}].
    """
    jobs = page.evaluate("""
        () => {
            const detailLinks = Array.from(
                document.querySelectorAll("a[href^='/jobs/']")
            ).filter(a => a.textContent.trim() === 'Details');

            return detailLinks.map(a => {
                let el = a.parentElement;
                while (el && !el.querySelector('h3')) {
                    el = el.parentElement;
                }
                const h3 = el ? el.querySelector('h3') : null;
                return {
                    name: h3 ? h3.textContent.trim() : '',
                    detail_url: a.getAttribute('href')
                };
            });
        }
    """)
    return jobs


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            executable_path=CHROME_PATH,
            headless=False,
            args=["--start-maximized"],
        )
        page = browser.new_page()

        print(f"Navigating to {TARGET_URL} ...")
        page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)

        print("Waiting for first job cards to appear...")
        page.wait_for_selector("a[href^='/jobs/']", timeout=20000)
        page.wait_for_timeout(1500)

        click_load_more(page)

        print("Extracting job names and detail links...")
        jobs = extract_jobs(page)

        # Deduplicate by href, preserving order
        seen = set()
        unique_jobs = []
        for job in jobs:
            if job["detail_url"] not in seen:
                seen.add(job["detail_url"])
                unique_jobs.append({
                    "name": job["name"],
                    "detail_url": BASE_URL + job["detail_url"],
                })

        print(f"Found {len(unique_jobs)} apprenticeship listing(s).")

        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "detail_url"])
            writer.writeheader()
            writer.writerows(unique_jobs)

        print(f"Saved to {OUTPUT_CSV}")
        browser.close()


main()
