import asyncio
import random
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError

# ---------- CONFIG ----------
# Part 2: Check LinkedIn Job Expiry Status
INPUT_CSV = "jobs_dataset4.csv"
OUTPUT_CSV = "linkedin_job_status_results6.csv"

URL_COLUMN = "application_url"

# If LinkedIn forces login, you can optionally use a saved browser session:
# - Run login_helper.py first to save your session
# - Then set STORAGE_STATE to "linkedin_session.json"
STORAGE_STATE = "linkedin_session.json"  # Using saved LinkedIn session

# Gentler browsing (helps avoid blocks)
# Optimized for speed while maintaining accuracy for batches of 20 jobs
MIN_DELAY_S = 1.0  # Faster - reduced from 3.0
MAX_DELAY_S = 2.5  # Faster - reduced from 7.0

NAV_TIMEOUT_MS = 45000

# Anti-detection settings
HEADLESS = False  # Set to False to show browser (helps avoid detection)
USE_STEALTH = True  # Enable stealth mode features

# Common "expired/unavailable" signals on LinkedIn job pages
EXPIRED_TEXT_HINTS = [
    "no longer accepting applications",
    "job is no longer available",
    "this job is no longer available",
    "position has been filled",
    "this posting is no longer available",
    "we couldn’t find a match",
    "page not found",
    "this job has expired",
]

# Common "login wall / blocked" signals
BLOCKED_TEXT_HINTS = [
    "sign in",
    "join linkedin",
    "you’re signed out",
    "log in",
    "login",
    "confirm you’re a human",
    "security verification",
    "unusual activity",
    "captcha",
]

def normalize_text(s: str) -> str:
    return " ".join((s or "").lower().split())

async def check_one(page, url: str) -> dict:
    """
    Returns a dict with status for one LinkedIn job URL.
    """
    checked_at = datetime.now(timezone.utc).isoformat()

    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        status = resp.status if resp else None
        final_url = page.url

        # Give the page a moment to render key text (without waiting forever)
        # Random wait to simulate human behavior
        try:
            await page.wait_for_timeout(random.randint(1500, 3000))
        except Exception:
            pass
        
        # Simulate human scrolling behavior
        try:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await page.wait_for_timeout(random.randint(300, 800))
        except Exception:
            pass

        html_text = normalize_text(await page.inner_text("body"))

        # Detect blocked/login wall
        if any(hint in html_text for hint in BLOCKED_TEXT_HINTS):
            return {
                "checked_at": checked_at,
                "http_status": status,
                "final_url": final_url,
                "result": "unknown",
                "expired": None,
                "reason": "blocked_or_login_wall",
            }

        # Detect expired/unavailable
        if any(hint in html_text for hint in EXPIRED_TEXT_HINTS):
            return {
                "checked_at": checked_at,
                "http_status": status,
                "final_url": final_url,
                "result": "expired",
                "expired": True,
                "reason": "expired_text_detected",
            }

        # Also treat obvious HTTP signals as expired
        if status in (404, 410):
            return {
                "checked_at": checked_at,
                "http_status": status,
                "final_url": final_url,
                "result": "expired",
                "expired": True,
                "reason": f"http_{status}",
            }

        # Otherwise assume active (best-effort)
        return {
            "checked_at": checked_at,
            "http_status": status,
            "final_url": final_url,
            "result": "active",
            "expired": False,
            "reason": "no_expired_signals_detected",
        }

    except PWTimeoutError:
        return {
            "checked_at": checked_at,
            "http_status": None,
            "final_url": None,
            "result": "unknown",
            "expired": None,
            "reason": "timeout",
        }
    except Exception as e:
        return {
            "checked_at": checked_at,
            "http_status": None,
            "final_url": None,
            "result": "unknown",
            "expired": None,
            "reason": f"error:{type(e).__name__}",
        }

async def main():
    input_path = Path(INPUT_CSV)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path.resolve()}")

    df = pd.read_csv(input_path)

    if URL_COLUMN not in df.columns:
        raise ValueError(f"CSV must contain a '{URL_COLUMN}' column. Found: {list(df.columns)}")

    urls = df[URL_COLUMN].astype(str).tolist()

    async with async_playwright() as p:
        # Launch browser with anti-detection args
        browser = await p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-web-security",
            ]
        )

        context_kwargs = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        }
        if STORAGE_STATE:
            context_kwargs["storage_state"] = STORAGE_STATE

        context = await browser.new_context(**context_kwargs)
        
        # Additional stealth measures
        if USE_STEALTH:
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            """)
        
        page = await context.new_page()

        results = []
        for i, url in enumerate(urls, start=1):
            url = url.strip()
            if not url:
                results.append({
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "http_status": None,
                    "final_url": None,
                    "result": "unknown",
                    "expired": None,
                    "reason": "empty_url",
                })
                continue

            print(f"[{i}/{len(urls)}] Checking: {url}")
            row_result = await check_one(page, url)
            results.append(row_result)

            # polite delay
            await asyncio.sleep(random.uniform(MIN_DELAY_S, MAX_DELAY_S))

        await context.close()
        await browser.close()

    # merge back into original df
    res_df = pd.DataFrame(results)
    out = pd.concat([df, res_df], axis=1)

    out.to_csv(OUTPUT_CSV, index=False)

    # summary
    summary = out["result"].value_counts(dropna=False).to_dict()
    print("\nSaved:", OUTPUT_CSV)
    print("Summary:", summary)

if __name__ == "__main__":
    asyncio.run(main())
