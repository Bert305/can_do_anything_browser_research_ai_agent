import pandas as pd
# PART 1: CLEAN DATA FOR BOT USAGE
# ---------- CONFIG ----------
INPUT_CSV = "part1_data_cleanup.csv"
OUTPUT_CSV = "data_ready_for_bot.csv"

KEEP_COLUMNS = [
    "company_name",
    "title",
    "application_url"
]

def main():
    df = pd.read_csv(INPUT_CSV)

    # Validate required columns
    missing = [c for c in KEEP_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Keep only the needed columns
    cleaned_df = df[KEEP_COLUMNS].copy()

    # Optional: drop rows with no application_url
    cleaned_df = cleaned_df.dropna(subset=["application_url"])
    cleaned_df = cleaned_df[cleaned_df["application_url"].str.strip() != ""]

    cleaned_df.to_csv(OUTPUT_CSV, index=False)

    print(f"Saved cleaned file to: {OUTPUT_CSV}")
    print(f"Row count: {len(cleaned_df)}")

if __name__ == "__main__":
    main()
