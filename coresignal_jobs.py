import os
import requests
import json
import csv
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =========================
# CONFIG
# =========================
API_KEY = jobs_api_key = os.getenv("CORESIGNAL_API_KEY")

BASE_URL = "https://api.coresignal.com/cdapi"
SEARCH_URL = f"{BASE_URL}/v2/job_base/search/filter"
COLLECT_URL_TEMPLATE = f"{BASE_URL}/v2/job_base/collect/{{job_id}}"
PREVIEW_URL = f"{BASE_URL}/v2/job_base/search/filter/preview"

OUTPUT_DIR = Path("coresignal_output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Your requested filters
CITY = "Miami"
CREATED_FROM = "2026-02-01 00:00:00"
CREATED_TO = datetime.now().strftime("%Y-%m-%d 23:59:59")
KEYWORD_DESCRIPTION = "Tech OR Engineering"

# Optional filters
APPLICATION_ACTIVE = True
DELETED = False

# Safety / performance
MAX_IDS_TO_COLLECT = 1200      # change as needed
REQUEST_DELAY_SECONDS = 0.15  # small pause to be polite with rate limits

HEADERS = {
    "accept": "application/json",
    "apikey": API_KEY,
    "Content-Type": "application/json",
}

SEARCH_PAYLOAD = {
    "location": CITY,
    "created_at_gte": CREATED_FROM,
    "created_at_lte": CREATED_TO,
    "keyword_description": KEYWORD_DESCRIPTION,
    "application_active": APPLICATION_ACTIVE,
    "deleted": DELETED,
}


# =========================
# HELPERS
# =========================
def safe_request(method, url, **kwargs):
    """
    Wrapper for requests with basic error reporting.
    """
    try:
        response = requests.request(method, url, timeout=60, **kwargs)
        response.raise_for_status()
        return response
    except requests.HTTPError as e:
        print(f"HTTP error for {url}: {e}")
        if e.response is not None:
            print("Status:", e.response.status_code)
            print("Response:", e.response.text[:2000])
        raise
    except requests.RequestException as e:
        print(f"Request failed for {url}: {e}")
        raise


def test_preview():
    """
    Optional: check whether the query returns plausible matches.
    """
    print("\n=== Testing preview endpoint ===")
    resp = safe_request("POST", PREVIEW_URL, headers=HEADERS, json=SEARCH_PAYLOAD)
    try:
        data = resp.json()
    except Exception:
        print("Preview response was not valid JSON.")
        print(resp.text[:2000])
        return

    print("Preview response sample:")
    print(json.dumps(data, indent=2)[:3000])


def search_all_job_ids():
    """
    Search all matching job IDs using pagination cursor from x-next-page-after.
    Docs indicate pagination uses ?after={x-next-page-after}.
    """
    print("\n=== Searching for matching job IDs ===")
    all_ids = []
    after = None
    page_num = 1

    while True:
        url = SEARCH_URL
        if after:
            url = f"{SEARCH_URL}?after={after}"

        print(f"Fetching page {page_num}...")
        resp = safe_request("POST", url, headers=HEADERS, json=SEARCH_PAYLOAD)

        # Search endpoint returns IDs
        try:
            page_data = resp.json()
        except Exception:
            print("Search response was not valid JSON.")
            print(resp.text[:2000])
            raise

        # Handle possible response shapes robustly
        page_ids = []
        if isinstance(page_data, list):
            for item in page_data:
                if isinstance(item, int):
                    page_ids.append(item)
                elif isinstance(item, dict) and "id" in item:
                    page_ids.append(item["id"])
        elif isinstance(page_data, dict):
            for key in ("data", "results", "items", "ids"):
                if key in page_data and isinstance(page_data[key], list):
                    for item in page_data[key]:
                        if isinstance(item, int):
                            page_ids.append(item)
                        elif isinstance(item, dict) and "id" in item:
                            page_ids.append(item["id"])

        print(f"Found {len(page_ids)} IDs on this page.")
        all_ids.extend(page_ids)

        next_after = resp.headers.get("x-next-page-after")
        total_pages = resp.headers.get("x-total-pages")
        total_results = resp.headers.get("x-total-results")

        if total_pages or total_results:
            print(f"x-total-pages={total_pages}, x-total-results={total_results}")

        if not next_after or next_after.lower() in ("none", "null", ""):
            break

        after = next_after
        page_num += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    # Deduplicate while preserving order
    deduped_ids = list(dict.fromkeys(all_ids))
    print(f"\nTotal unique IDs found: {len(deduped_ids)}")
    return deduped_ids


def collect_job(job_id):
    """
    Collect full job record for one ID.
    """
    url = COLLECT_URL_TEMPLATE.format(job_id=job_id)
    resp = safe_request("GET", url, headers=HEADERS)
    return resp.json()


def collect_jobs(job_ids, max_collect=None):
    """
    Collect full records for job IDs.
    """
    print("\n=== Collecting full job records ===")
    records = []
    target_ids = job_ids[:max_collect] if max_collect else job_ids

    for idx, job_id in enumerate(target_ids, start=1):
        try:
            record = collect_job(job_id)
            records.append(record)
            print(f"[{idx}/{len(target_ids)}] Collected job ID {job_id}")
        except Exception as e:
            print(f"[{idx}/{len(target_ids)}] Failed job ID {job_id}: {e}")

        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nCollected {len(records)} full records.")
    return records


def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved JSON: {filepath}")


def save_csv(records, filepath):
    """
    Flatten selected top-level fields for CSV export.
    """
    if not records:
        print("No records to save to CSV.")
        return

    fieldnames = [
        "id",
        "created",
        "last_updated",
        "time_posted",
        "title",
        "company_id",
        "company_name",
        "location",
        "country",
        "employment_type",
        "seniority",
        "salary",
        "url",
        "external_url",
        "linkedin_job_id",
        "application_active",
        "deleted",
        "description",
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = {key: record.get(key) for key in fieldnames}
            writer.writerow(row)

    print(f"Saved CSV: {filepath}")


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    print("Starting Coresignal job search...")
    print("Filters:")
    print(json.dumps(SEARCH_PAYLOAD, indent=2))

    # Step 1: optional preview
    test_preview()

    # Step 2: search matching IDs
    job_ids = search_all_job_ids()
    save_json(job_ids, OUTPUT_DIR / "job_ids.json")

    # Step 3: collect full records
    full_records = collect_jobs(job_ids, max_collect=MAX_IDS_TO_COLLECT)

    # Step 4: save outputs
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_json(full_records, OUTPUT_DIR / f"miami_jobs_full_{timestamp}.json")
    save_csv(full_records, OUTPUT_DIR / f"miami_jobs_full_{timestamp}.csv")

    print("\nDone.")