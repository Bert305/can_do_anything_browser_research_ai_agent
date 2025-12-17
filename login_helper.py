"""
LinkedIn Login Helper
Run this script once to log into LinkedIn and save your session.
Then use STORAGE_STATE = "linkedin_session.json" in check_linkedin_jobs.py
"""
import asyncio
from playwright.async_api import async_playwright

async def save_linkedin_session():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]
        )
        
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        
        # Anti-detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)
        
        page = await context.new_page()
        
        print("Opening LinkedIn...")
        await page.goto("https://www.linkedin.com/login")
        
        print("\n" + "="*60)
        print("INSTRUCTIONS:")
        print("1. Log into LinkedIn manually in the browser window")
        print("2. Complete any security checks if prompted")
        print("3. Once you see your LinkedIn feed, press Enter here")
        print("="*60 + "\n")
        
        # Wait for user to log in
        input("Press Enter after you've logged in successfully...")
        
        # Save the session
        await context.storage_state(path="linkedin_session.json")
        
        print("\n✓ Session saved to 'linkedin_session.json'")
        print("✓ Now set STORAGE_STATE = 'linkedin_session.json' in check_linkedin_jobs.py")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(save_linkedin_session())
