import asyncio
import random
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError

# ---------- CONFIG ----------
# Part 2: Check LinkedIn Job Expiry Status
#
# Strategy for handling larger bulks (50-100 URLs) at speed without tripping
# LinkedIn's bot detection:
#   1. Primary check uses the *guest* job-posting endpoint (no login, very
#      light). This is fast AND keeps the bulk of traffic off your logged-in
#      account, which is what usually gets flagged.
#   2. The heavy full-browser render is used ONLY as a fallback for the small
#      number of URLs the guest check can't classify.
#   3. Bounded concurrency + jittered delays give speed without a burst that
#      looks robotic.
#   4. Adaptive backoff pauses everything if LinkedIn starts rate-limiting.
#   5. Checkpointing: already-classified URLs are skipped on re-run.
INPUT_CSV = "data_ready_for_bot_25_.csv"
OUTPUT_CSV = "linkedin_job_status_results_25_2.csv"

URL_COLUMN = "application_url"

# Saved logged-in session (only used for the browser fallback).
# Run login_helper.py first to create it.
STORAGE_STATE = "linkedin_session.json"

# Recommended batch size: keep runs to ~50-100 URLs. Larger is fine but split
# across multiple runs (checkpointing lets you resume) rather than one giant run.

# --- Guest-endpoint checks (the fast path) ---
GUEST_CONCURRENCY = 4          # parallel guest requests; keep modest (3-5)
GUEST_MIN_DELAY_S = 0.6        # per-worker jittered delay between requests
GUEST_MAX_DELAY_S = 1.6
GUEST_TIMEOUT_MS = 20000

# --- Browser fallback (the slow, human-like path; used rarely) ---
BROWSER_MIN_DELAY_S = 1.5
BROWSER_MAX_DELAY_S = 3.5
NAV_TIMEOUT_MS = 45000

# --- Anti-detection ---
HEADLESS = False               # visible browser is less bot-like for fallback
USE_STEALTH = True

# --- Adaptive backoff ---
# If we hit this many rate-limit/block signals in a row, pause all workers.
BLOCK_BACKOFF_THRESHOLD = 3
BACKOFF_PAUSE_S = 90

# --- Checkpointing ---
# On re-run, skip URLs already classified as one of these (definitive) results.
RESUME_SKIP_RESULTS = {"active", "expired"}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# LinkedIn guest job-posting fragment (no login required)
GUEST_ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

# The primary "Apply" call-to-action. LinkedIn keeps a closed job's page
# rendered but DROPS this CTA once it stops accepting applications, so its
# presence is a reliable "still hiring" signal and its absence flags a
# likely-closed posting (verified via browser fallback).
APPLY_CTA_MARKER = "top-card-layout__cta--primary"

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

# LinkedIn's anti-scraping HTTP status is 999; 429 is standard rate limiting.
RATE_LIMIT_STATUSES = {429, 999}


def normalize_text(s: str) -> str:
    return " ".join((s or "").lower().split())


def extract_job_id(url: str) -> str | None:
    """Pull the numeric LinkedIn job id out of an application URL."""
    if not url:
        return None
    # .../jobs/view/some-slug-1234567890  or  .../jobs/view/1234567890
    m = re.search(r"/jobs/view/(?:[^/?#]*?-)?(\d{6,})", url)
    if m:
        return m.group(1)
    # ...?currentJobId=1234567890
    m = re.search(r"[?&]currentJobId=(\d{6,})", url)
    if m:
        return m.group(1)
    # Fallback: last long digit run in the URL
    nums = re.findall(r"\d{6,}", url)
    return nums[-1] if nums else None


class RateController:
    """Shared adaptive-backoff coordinator across concurrent workers."""

    def __init__(self):
        self.consecutive_blocks = 0
        self.lock = asyncio.Lock()
        self.go = asyncio.Event()
        self.go.set()

    async def wait(self):
        await self.go.wait()

    async def report(self, blocked: bool):
        should_pause = False
        async with self.lock:
            if blocked:
                self.consecutive_blocks += 1
                if self.consecutive_blocks >= BLOCK_BACKOFF_THRESHOLD and self.go.is_set():
                    self.go.clear()
                    should_pause = True
            else:
                self.consecutive_blocks = 0
        if should_pause:
            print(f"⚠️  Detection signals detected — cooling down for {BACKOFF_PAUSE_S}s...")
            await asyncio.sleep(BACKOFF_PAUSE_S)
            async with self.lock:
                self.consecutive_blocks = 0
                self.go.set()
            print("▶️  Resuming.")


async def check_guest(request_ctx, url: str, job_id: str):
    """
    Fast, login-free check via the guest endpoint.
    Returns (result_dict, needs_fallback, rate_limited).
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    endpoint = GUEST_ENDPOINT.format(job_id=job_id)
    base = {
        "checked_at": checked_at,
        "job_id": job_id,
        "method": "guest",
        "final_url": endpoint,
    }

    try:
        resp = await request_ctx.get(endpoint, timeout=GUEST_TIMEOUT_MS)
    except PWTimeoutError:
        return {**base, "http_status": None, "result": "unknown",
                "expired": None, "reason": "guest_timeout"}, True, True
    except Exception as e:
        return {**base, "http_status": None, "result": "unknown",
                "expired": None, "reason": f"guest_error:{type(e).__name__}"}, True, False

    status = resp.status
    try:
        body = normalize_text(await resp.text())
    except Exception:
        body = ""

    # Rate limited / bot-challenged
    if status in RATE_LIMIT_STATUSES or "captcha" in body or "unusual activity" in body:
        return {**base, "http_status": status, "result": "unknown",
                "expired": None, "reason": f"rate_limited_{status}"}, True, True

    # Hard "gone" signals
    if status in (404, 410):
        return {**base, "http_status": status, "result": "expired",
                "expired": True, "reason": f"http_{status}"}, False, False

    if status == 200:
        if any(h in body for h in EXPIRED_TEXT_HINTS):
            return {**base, "http_status": 200, "result": "expired",
                    "expired": True, "reason": "expired_text_detected"}, False, False
        if len(body) < 200:
            # Empty/near-empty fragment — can't be sure; verify in browser.
            return {**base, "http_status": 200, "result": "unknown",
                    "expired": None, "reason": "empty_guest_body"}, True, False
        # Apply CTA present → posting is still accepting applications.
        if APPLY_CTA_MARKER in body:
            return {**base, "http_status": 200, "result": "active",
                    "expired": False, "reason": "guest_apply_cta_present"}, False, False
        # Content but no Apply CTA → posting likely closed; confirm in browser
        # (guards against a rare rendering quirk wrongly filtering a live job).
        return {**base, "http_status": 200, "result": "unknown",
                "expired": None, "reason": "no_apply_cta"}, True, False

    # Anything else (e.g. 400) — ambiguous, verify in browser.
    return {**base, "http_status": status, "result": "unknown",
            "expired": None, "reason": f"guest_http_{status}"}, True, False


async def check_browser(page, url: str) -> dict:
    """Full-render fallback (login-aware). Same detection logic as before."""
    checked_at = datetime.now(timezone.utc).isoformat()
    base = {"checked_at": checked_at, "job_id": extract_job_id(url), "method": "browser"}

    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        status = resp.status if resp else None
        final_url = page.url

        # Let key text render + light human-like activity
        try:
            await page.wait_for_timeout(random.randint(1500, 3000))
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await page.wait_for_timeout(random.randint(300, 800))
        except Exception:
            pass

        html_text = normalize_text(await page.inner_text("body"))

        if any(hint in html_text for hint in BLOCKED_TEXT_HINTS):
            return {**base, "http_status": status, "final_url": final_url,
                    "result": "unknown", "expired": None, "reason": "blocked_or_login_wall"}

        if any(hint in html_text for hint in EXPIRED_TEXT_HINTS):
            return {**base, "http_status": status, "final_url": final_url,
                    "result": "expired", "expired": True, "reason": "expired_text_detected"}

        if status in (404, 410):
            return {**base, "http_status": status, "final_url": final_url,
                    "result": "expired", "expired": True, "reason": f"http_{status}"}

        return {**base, "http_status": status, "final_url": final_url,
                "result": "active", "expired": False, "reason": "no_expired_signals_detected"}

    except PWTimeoutError:
        return {**base, "http_status": None, "final_url": None,
                "result": "unknown", "expired": None, "reason": "timeout"}
    except Exception as e:
        return {**base, "http_status": None, "final_url": None,
                "result": "unknown", "expired": None, "reason": f"error:{type(e).__name__}"}


def load_prior_results(df: pd.DataFrame) -> dict:
    """Return {row_index: result_dict} for URLs already definitively classified."""
    out_path = Path(OUTPUT_CSV)
    if not out_path.exists():
        return {}
    try:
        prior = pd.read_csv(out_path)
    except Exception:
        return {}
    if URL_COLUMN not in prior.columns or "result" not in prior.columns:
        return {}

    # Map url -> most recent definitive result row
    by_url = {}
    for _, row in prior.iterrows():
        if str(row.get("result")) in RESUME_SKIP_RESULTS:
            by_url[str(row.get(URL_COLUMN)).strip()] = row.to_dict()

    seeded = {}
    result_cols = ["checked_at", "job_id", "method", "http_status",
                   "final_url", "result", "expired", "reason"]
    for idx, url in enumerate(df[URL_COLUMN].astype(str)):
        prior_row = by_url.get(url.strip())
        if prior_row:
            seeded[idx] = {c: prior_row.get(c) for c in result_cols if c in prior_row}
    return seeded


async def guest_worker(name, queue, request_ctx, controller, results, results_lock, fallback):
    while True:
        try:
            idx, url = queue.get_nowait()
        except asyncio.QueueEmpty:
            return

        await controller.wait()
        job_id = extract_job_id(url)

        if not job_id:
            # Not a recognizable LinkedIn job URL — send straight to browser.
            fallback.append((idx, url))
            print(f"  · [{idx + 1}] no job id → browser fallback")
        else:
            res, needs_fallback, rate_limited = await check_guest(request_ctx, url, job_id)
            await controller.report(rate_limited)
            async with results_lock:
                results[idx] = res
            if needs_fallback:
                fallback.append((idx, url))
                print(f"  · [{idx + 1}] guest={res['reason']} → browser fallback")
            else:
                print(f"  ✓ [{idx + 1}] guest → {res['result']} ({res['reason']})")
            await asyncio.sleep(random.uniform(GUEST_MIN_DELAY_S, GUEST_MAX_DELAY_S))

        queue.task_done()


async def main():
    input_path = Path(INPUT_CSV)
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path.resolve()}")

    df = pd.read_csv(input_path)
    if URL_COLUMN not in df.columns:
        raise ValueError(f"CSV must contain a '{URL_COLUMN}' column. Found: {list(df.columns)}")

    urls = df[URL_COLUMN].astype(str).tolist()

    # Seed already-done rows (checkpoint/resume)
    results = load_prior_results(df)
    if results:
        print(f"↩️  Resuming: {len(results)} URLs already classified, skipping them.")

    # Build the work queue for everything not yet definitively classified
    queue: asyncio.Queue = asyncio.Queue()
    empty_count = 0
    for idx, raw in enumerate(urls):
        url = raw.strip()
        if idx in results:
            continue
        if not url or url.lower() == "nan":
            results[idx] = {
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "job_id": None, "method": None, "http_status": None,
                "final_url": None, "result": "unknown", "expired": None,
                "reason": "empty_url",
            }
            empty_count += 1
            continue
        queue.put_nowait((idx, url))

    todo = queue.qsize()
    print(f"🔎 {todo} URLs to check ({empty_count} empty, {len(results) - empty_count} resumed).")

    async with async_playwright() as p:
        # ---- Phase 1: fast guest-endpoint checks (concurrent, no login) ----
        guest_request = await p.request.new_context(
            user_agent=USER_AGENT,
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.linkedin.com/jobs/",
            },
        )
        controller = RateController()
        results_lock = asyncio.Lock()
        fallback: list = []

        if todo:
            print(f"\n--- Phase 1: guest checks ({GUEST_CONCURRENCY} workers) ---")
            workers = [
                asyncio.create_task(
                    guest_worker(f"g{i}", queue, guest_request, controller,
                                 results, results_lock, fallback)
                )
                for i in range(GUEST_CONCURRENCY)
            ]
            await asyncio.gather(*workers)
        await guest_request.dispose()

        # ---- Phase 2: browser fallback for the ambiguous few ----
        if fallback:
            print(f"\n--- Phase 2: browser fallback ({len(fallback)} URLs) ---")
            browser = await p.chromium.launch(
                headless=HEADLESS,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            context_kwargs = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": USER_AGENT,
            }
            if STORAGE_STATE and Path(STORAGE_STATE).exists():
                context_kwargs["storage_state"] = STORAGE_STATE

            context = await browser.new_context(**context_kwargs)
            if USE_STEALTH:
                await context.add_init_script(
                    """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    """
                )
            # Skip heavy assets: faster + lighter footprint
            await context.route(
                "**/*",
                lambda route: route.abort()
                if route.request.resource_type in {"image", "media", "font"}
                else route.continue_(),
            )
            page = await context.new_page()

            for n, (idx, url) in enumerate(fallback, start=1):
                print(f"  [{n}/{len(fallback)}] browser: {url}")
                res = await check_browser(page, url)
                results[idx] = res
                await asyncio.sleep(random.uniform(BROWSER_MIN_DELAY_S, BROWSER_MAX_DELAY_S))

            await context.close()
            await browser.close()

    # ---- Merge results back in original row order ----
    ordered = [results.get(i, {"result": "unknown", "reason": "not_processed"})
               for i in range(len(urls))]
    res_df = pd.DataFrame(ordered)
    out = pd.concat([df.reset_index(drop=True), res_df], axis=1)
    out.to_csv(OUTPUT_CSV, index=False)

    summary = out["result"].value_counts(dropna=False).to_dict()
    method_summary = out["method"].value_counts(dropna=False).to_dict() if "method" in out else {}
    print("\nSaved:", OUTPUT_CSV)
    print("Summary:", summary)
    print("By method:", method_summary)


if __name__ == "__main__":
    asyncio.run(main())
