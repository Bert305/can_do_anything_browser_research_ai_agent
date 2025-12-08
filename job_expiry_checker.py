from browser_use.llm import ChatOpenAI
from browser_use import Agent, BrowserSession
from dotenv import load_dotenv
import os
import asyncio
import pandas as pd
from datetime import datetime
from pathlib import Path

load_dotenv()

# =============================================================================
# 🚀 JOB EXPIRY CHECKER BOT
# =============================================================================
# Input CSV file path (must have columns: company_name, title, application_url)
INPUT_CSV = "bot_jobs2.csv"

# Output will be saved as: job_expiry_check_TIMESTAMP.csv
OUTPUT_FOLDER = "output"
# =============================================================================

# Browser session setup
user_data_dir = os.path.expanduser('~/.config/browseruse/profiles/default')
browser_session = BrowserSession(
    executable_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    user_data_dir=user_data_dir,
)
llm = ChatOpenAI(model="gpt-4.1")

async def check_job_expired(job_url, company_name, job_title):
    """
    Check if a LinkedIn job posting has expired - IMPROVED ACCURACY
    Returns: 'Yes' if expired, 'No' if still accepting applications, 'Error' if can't determine
    """
    
    task = f"""
    Go to this LinkedIn job URL: {job_url}
    
    Your ONLY task is to determine if this specific job posting has EXPIRED or is still ACTIVE.
    
    CRITICAL INSTRUCTIONS:
    1. Look at the job posting page carefully
    2. Ignore login prompts, sign-up messages, or "Join to apply" buttons
    3. Focus ONLY on the job status
    
    EXPIRED indicators (respond "Yes"):
    - Explicitly states "No longer accepting applications"
    - Says "This job posting has closed"
    - Shows "Applications are closed"
    - Has a red/gray badge saying "Closed" or "Expired"
    
    ACTIVE indicators (respond "No"):
    - Shows "Easy Apply" button
    - Shows "Apply" button
    - Shows number of applicants (e.g., "50 applicants")
    - Shows "Be an early applicant"
    - Shows posted date (e.g., "Posted 2 days ago") WITHOUT expired message
    - Shows company info and job details normally
    
    IMPORTANT: If you see an "Apply" or "Easy Apply" button, the job is ACTIVE (respond "No").
    Do NOT confuse LinkedIn login prompts with job expiry messages.
    
    Respond with ONLY ONE WORD:
    - "No" = Job is ACTIVE (still accepting applications)
    - "Yes" = Job is EXPIRED (no longer accepting applications)
    
    Job: {job_title} at {company_name}
    """
    
    try:
        agent = Agent(
            task=task,
            llm=llm,
            browser_session=browser_session,
        )
        
        print(f"   Checking: {job_title[:40]}... at {company_name}")
        result = await agent.run()
        response = result.final_result().strip()
        
        # More robust parsing with explicit checks
        response_upper = response.upper()
        response_lower = response.lower()
        
        # First check: Direct Yes/No in response
        if response_upper.startswith("YES") or response_upper == "YES":
            return "Yes"
        elif response_upper.startswith("NO") or response_upper == "NO":
            return "No"
        
        # Second check: Look for key phrases in full response
        # Strong ACTIVE indicators (job is NOT expired)
        active_indicators = [
            "easy apply", "apply button", "still accepting", 
            "is active", "is open", "applicants", "early applicant",
            "apply now", "job is available"
        ]
        
        # Strong EXPIRED indicators
        expired_indicators = [
            "no longer accepting", "applications are closed",
            "posting has closed", "job has closed", "is expired",
            "is closed", "closed to applications"
        ]
        
        # Check for active indicators first (higher priority to avoid false positives)
        if any(indicator in response_lower for indicator in active_indicators):
            return "No"
        
        # Then check for expired indicators
        if any(indicator in response_lower for indicator in expired_indicators):
            return "Yes"
        
        # If unclear, default to "Unknown" rather than guessing
        print(f"   ⚠️  Unclear response: {response[:100]}")
        return "Unknown"
                
    except Exception as e:
        print(f"   ❌ Error checking job: {e}")
        return "Error"

async def process_jobs_csv(input_csv_path):
    """
    Process the input CSV and check each job for expiry
    """
    
    print("🚀 Starting LinkedIn Job Expiry Checker Bot...")
    print(f"📋 Reading jobs from: {input_csv_path}")
    print("-" * 60)
    
    # Read input CSV
    try:
        df = pd.read_csv(input_csv_path)
        print(f"✅ Found {len(df)} jobs to check\n")
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        return
    
    # Validate required columns
    required_columns = ['company_name', 'title', 'application_url']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"❌ Missing required columns: {missing_columns}")
        print(f"   Required columns: {required_columns}")
        return
    
    # Add expired column
    df['expired'] = ""
    
    # Check each job
    for index, row in df.iterrows():
        job_num = index + 1
        print(f"\n[{job_num}/{len(df)}] Checking job...")
        
        expired_status = await check_job_expired(
            row['application_url'],
            row['company_name'],
            row['title']
        )
        
        df.at[index, 'expired'] = expired_status
        
        status_icon = "❌" if expired_status == "Yes" else "✅" if expired_status == "No" else "⚠️"
        print(f"   {status_icon} Result: Expired = {expired_status}")
        
        # Small delay to avoid rate limiting
        await asyncio.sleep(2)
    
    # Save results
    output_dir = Path(__file__).parent / OUTPUT_FOLDER # Output directory
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_csv = output_dir / f"job_expiry_check_{timestamp}.csv" # Name Output file with timestamp
    
    # Reorder columns for better readability
    output_df = df[['company_name', 'title', 'application_url', 'expired']]
    output_df.to_csv(output_csv, index=False, encoding='utf-8')
    
    print("\n" + "="*60)
    print("🎉 Job expiry check completed!")
    print(f"📊 Results saved to: {output_csv}")
    print("\nSummary:")
    print(f"   Total jobs checked: {len(df)}")
    print(f"   Expired jobs: {len(df[df['expired'] == 'Yes'])}")
    print(f"   Active jobs: {len(df[df['expired'] == 'No'])}")
    print(f"   Unknown/Error: {len(df[~df['expired'].isin(['Yes', 'No'])])}")
    print("="*60)

async def main():
    """
    Main function to run the job expiry checker
    """
    
    input_path = Path(__file__).parent / INPUT_CSV
    
    if not input_path.exists():
        print(f"❌ Error: Input file not found: {input_path}")
        print(f"   Please make sure '{INPUT_CSV}' exists in the same folder as this script.")
        return
    
    try:
        await process_jobs_csv(input_path)
    finally:
        await browser_session.close()
        print("\n✅ Browser session closed")

if __name__ == "__main__":
    asyncio.run(main())
