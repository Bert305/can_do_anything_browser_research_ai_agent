# can_do_anything_browser_research_ai_agent

## Overview

`can_do_anything_browser_research_ai_agent` is an AI-powered research agent designed to automate browser-based tasks and information gathering. It leverages browser automation to perform complex research workflows, making it ideal for users who need to collect, analyze, and summarize web data efficiently.

## Features

- Automated web browsing and data extraction
- Customizable research workflows
- Integration with AI models for summarization and analysis
- Easy setup and extensibility
- **LinkedIn Job Expiry Automation Bot** - Fast, accurate LinkedIn job status checker with CSV processing

## API Keys

OPENAI_API_KEY=
ANTHROPIC_API_KEY=

## Quickstart

To get started, follow the [Quickstart Guide](https://docs.browser-use.com/quickstart).

## Demo

Watch a demo of the agent in action on [YouTube](https://www.youtube.com/watch?v=zGkVKix_CRU).

## Installation

```bash
git clone https://github.com/yourusername/can_do_anything_browser_research_ai_agent.git
cd can_do_anything_browser_research_ai_agent
pip install -r requirements.txt
playwright install
```

## Activate .venv
Windows:
```bash
.venv\Scripts\activate
```
macOS/Linux:
```bash
source .venv/bin/activate
```

## Usage

After installation, run:

```bash
python main.py
```

Configure your research tasks in `config.yaml` or via the command line.

---

## 🤖 LinkedIn Job Expiry Automation Bot

A complete automation workflow to check LinkedIn job postings for expiry status using Playwright browser automation.

### **Overview**

This bot automatically:
1. Logs into LinkedIn and saves your session
2. Checks job URLs from a CSV file to detect if they're expired or active
3. Cleans the results to show only expired and unknown jobs

### **Quick Start - 3 Simple Steps**

#### **Step 1: Save Your LinkedIn Session** (One-time setup)

```bash
python login_helper.py
```

**What happens:**
- Browser window opens to LinkedIn login
- Log in with your credentials manually
- Complete any security checks (2FA, etc.)
- Press Enter in terminal once logged in
- Session saved to `linkedin_session.json` (don't push this file!)

---

#### **Step 2: Check Job Expiry Status**

**Prepare your CSV file:**
- File name: `jobs_dataset.csv` (or update `INPUT_CSV` in script)
- Required columns: `company_name`, `title`, `application_url`

**Example CSV:**
```csv
company_name,title,application_url
Google,Software Engineer,https://www.linkedin.com/jobs/view/1234567890
Meta,Product Manager,https://www.linkedin.com/jobs/view/0987654321
```

**Run the checker:**
```bash
python check_linkedin_jobs.py
```

**Performance:**
- ⚡ **3-4 minutes** for 20 jobs
- ✅ **~90% accuracy**
- 🎯 **Best batch size: 20 jobs** (to avoid rate limiting)

**Results saved to:** `linkedin_job_status_results.csv`

---

#### **Step 3: Clean Results** (Optional)

Remove active jobs and keep only expired/unknown:

```bash
python job_clean.py
```

**Output:** `cleaned_job_results.csv` with only:
- Expired jobs (expired = True)
- Unknown jobs (couldn't determine status)

---

### **Configuration**

**Optimize for your needs in `check_linkedin_jobs.py`:**

```python
# Speed vs Safety trade-off
MIN_DELAY_S = 1.0   # Faster: 1.0 | Safer: 3.0
MAX_DELAY_S = 2.5   # Faster: 2.5 | Safer: 7.0

# Batch size recommendation
# 20 jobs = 3-4 min, 90% success (RECOMMENDED)
# 50 jobs = 10-15 min, 80-85% success (may get rate limited)
```

---

### **Best Practices**

✅ **Process 20 jobs at a time** for best speed/accuracy balance  
✅ **Use saved LinkedIn session** to avoid login prompts  
✅ **Run during off-peak hours** for better success rates  
✅ **Don't commit** `linkedin_session.json` or CSV files (already in `.gitignore`)  

⚠️ **If you get "unknown" results:**
- LinkedIn may be rate limiting
- Reduce batch size to 15 jobs
- Increase delays to 3-7 seconds

---

### **Troubleshooting**

| Issue | Solution |
|-------|----------|
| "FileNotFoundError: jobs_dataset.csv" | Create CSV with required columns or update `INPUT_CSV` |
| Most results "unknown" after ~22 jobs | Reduce batch size to 20, increase delays |
| "blocked_or_login_wall" errors | Re-run `login_helper.py` to refresh session |
| Browser won't open | Install Playwright: `playwright install chromium` |

---

### **File Structure**

```
├── login_helper.py              # Step 1: Save LinkedIn session
├── check_linkedin_jobs.py       # Step 2: Check job expiry status
├── job_clean.py                 # Step 3: Clean results
├── linkedin_session.json        # Your session (DO NOT COMMIT)
├── jobs_dataset.csv             # Input: Job URLs
├── linkedin_job_status_results.csv  # Output: Full results
└── cleaned_job_results.csv      # Output: Expired/unknown only
```

---

---

## Documentation

See the [official documentation](https://docs.browser-use.com/quickstart) for detailed instructions and advanced usage.


## License

This project is licensed under the MIT License.