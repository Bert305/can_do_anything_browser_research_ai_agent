import pandas as pd
from pathlib import Path
from datetime import datetime

# =============================================================================
# 🧹 JOB RESULTS CLEANER
# =============================================================================

# Part 3: Clean Job Results from LinkedIn Expiry Checker

# This script reads the output from check_linkedin_jobs.py and:
# 1. Removes rows where expired = False (active jobs - not needed)
# 2. Keeps rows where expired = True (expired jobs - for tracking)
# 3. Converts blank/None expired values to "Unknown"
# =============================================================================

# INPUT: Output from check_linkedin_jobs.py
INPUT_CSV = "linkedin_job_status_results6.csv"

# OUTPUT: Cleaned results (only expired and unknown jobs)
OUTPUT_CSV = "cleaned_job_results.csv"

# Columns to keep in output
OUTPUT_COLUMNS = ["company_name", "title", "application_url", "expired"]

def clean_job_results():
    """
    Clean the LinkedIn job check results to only show expired and unknown jobs.
    """
    
    input_path = Path(INPUT_CSV)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path.resolve()}")
    
    print(f"📂 Reading: {INPUT_CSV}")
    df = pd.read_csv(input_path)
    
    print(f"   Total rows before cleaning: {len(df)}")
    
    # Step 1: Replace blank/None/NaN values in 'expired' column with "Unknown"
    df['expired'] = df['expired'].fillna('Unknown')
    df['expired'] = df['expired'].replace('', 'Unknown')
    
    # Step 2: Remove rows where expired = False (active jobs)
    df_cleaned = df[df['expired'] != False].copy()
    
    # Alternative if expired column is string 'False' instead of boolean
    df_cleaned = df_cleaned[df_cleaned['expired'] != 'False'].copy()
    
    print(f"   Removed {len(df) - len(df_cleaned)} active jobs (expired = False)")
    print(f"   Remaining rows: {len(df_cleaned)}")
    
    # Step 3: Keep only the specified columns
    # Check which columns exist in the dataframe
    available_columns = [col for col in OUTPUT_COLUMNS if col in df_cleaned.columns]
    missing_columns = [col for col in OUTPUT_COLUMNS if col not in df_cleaned.columns]
    
    if missing_columns:
        print(f"   ⚠️  Warning: Missing columns: {missing_columns}")
        print(f"   Available columns: {list(df_cleaned.columns)}")
    
    df_output = df_cleaned[available_columns].copy()
    
    # Step 4: Save cleaned results
    output_path = Path(OUTPUT_CSV)
    df_output.to_csv(output_path, index=False, encoding='utf-8')
    
    print(f"\n✅ Cleaned results saved to: {OUTPUT_CSV}")
    
    # Summary statistics
    print("\n📊 Summary:")
    if 'expired' in df_output.columns:
        expired_counts = df_output['expired'].value_counts()
        print(f"   Expired (True): {expired_counts.get(True, expired_counts.get('True', 0))}")
        print(f"   Unknown: {expired_counts.get('Unknown', 0)}")
    print(f"   Total rows in output: {len(df_output)}")
    
    return df_output

if __name__ == "__main__":
    try:
        clean_job_results()
        print("\n🎉 Job cleaning complete!")
    except Exception as e:
        print(f"\n❌ Error: {e}")