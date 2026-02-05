import pandas as pd

# File paths
EXPIRED_FILE = "expired_jobs_bot2.csv" # running doc of non-active jobs
SOURCE_FILE = "source_jobs_bot2.csv" # full raw data set
OUTPUT_FILE = "source_jobs_bot_active_only2.csv" # filtered active jobs

# Load CSVs
expired_df = pd.read_csv(EXPIRED_FILE)
source_df = pd.read_csv(SOURCE_FILE)

# Ensure application_url exists
if "application_url" not in expired_df.columns:
    raise ValueError("expired_jobs_bot.csv is missing 'application_url' column")

if "application_url" not in source_df.columns:
    raise ValueError("source_jobs_bot.csv is missing 'application_url' column")

# Convert URLs to sets for fast lookup
expired_urls = set(expired_df["application_url"].dropna().unique())

# Filter source jobs (keep only non-expired)
filtered_source_df = source_df[
    ~source_df["application_url"].isin(expired_urls)
]

# Save output
filtered_source_df.to_csv(OUTPUT_FILE, index=False)

print("✅ Filtering complete!")
print(f"Original source rows: {len(source_df)}")
print(f"Expired URLs removed: {len(source_df) - len(filtered_source_df)}")
print(f"Remaining active jobs: {len(filtered_source_df)}")
print(f"📄 Output saved as: {OUTPUT_FILE}")
