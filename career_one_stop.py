import os
import requests
import json
import csv
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
# --- YOUR CREDENTIALS ---
USER_ID = os.getenv("CAREERONESTOP_USER_ID") # USER ID from CareerOneStop API
API_TOKEN = os.getenv("CAREERONESTOP_API_TOKEN") # API token from CareerOneStop API

if not USER_ID or not API_TOKEN:
    raise EnvironmentError("CAREERONESTOP_USER_ID or CAREERONESTOP_API_TOKEN not found in .env")
print(f"USER_ID loaded: {USER_ID}")
print(f"API_TOKEN loaded: {'YES' if API_TOKEN else 'NO'} (length={len(API_TOKEN) if API_TOKEN else 0})")

# --- SEARCH SETTINGS ---
keyword = "engineer"     # example: "data analyst"
location = "Miami, FL"             # city/state, state, or zip
radius = "25"                      # miles
sort_columns = "0"                 # 0 = relevance, or use fields like acquisitiondate
sort_order = "0"                   # 0 = relevance, or ASC / DESC
start_record = "0"                  # starting record index for pagination
page_size = "25"                   # number of results per page
days = "30"                        # 0 = all jobs, per docs

# Optional query params
params = {
    "showFilters": "false",
    "enableJobDescriptionSnippet": "true",
    "enableMetaData": "true"
}

url = (
    f"https://api.careeronestop.org/v2/jobsearch/"
    f"{USER_ID}/{keyword}/{location}/{radius}/"
    f"{sort_columns}/{sort_order}/{start_record}/{page_size}/{days}"
)

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json"
}

response = requests.get(url, headers=headers, params=params, timeout=30)
response.raise_for_status()

data = response.json()

# Save raw JSON
json_path = Path("careeronestop_jobs_miami.json")
json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"Saved JSON to {json_path}")

# Try to flatten common job-list structures into CSV
# You may need to adjust this depending on the exact response structure returned
possible_keys = ["Jobs", "JobList", "JobSearchResult", "Items", "results", "Results"]
jobs = None

for key in possible_keys:
    if key in data and isinstance(data[key], list):
        jobs = data[key]
        break

# fallback: if top-level is already a list
if jobs is None and isinstance(data, list):
    jobs = data

if jobs and len(jobs) > 0 and isinstance(jobs[0], dict):
    csv_path = Path("careeronestop_jobs_miami.csv")
    fieldnames = sorted({k for row in jobs if isinstance(row, dict) for k in row.keys()})

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)

    print(f"Saved CSV to {csv_path}")
else:
    print("JSON saved, but CSV export needs a small adjustment after inspecting the response structure.")