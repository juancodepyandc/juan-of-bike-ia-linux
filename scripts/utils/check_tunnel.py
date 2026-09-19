"""Headless browse the tunnel + interact + capture errors."""
import asyncio
import sys
from playwright.async_api import async_playwright

URL = "https://lodging-fragrance-infections-expires.trycloudflare.com/"

# Force UTF-8 stdout for Windows.
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()

        console_msgs = []
        page_errors = []
        failed_reqs = []

        page.on("console", lambda msg: console_msgs.append(f"[{msg.type}] {msg.text[:300]}"))
        page.on("pageerror", lambda err: page_errors.append(str(err)[:500]))
        page.on("requestfailed", lambda req: failed_reqs.append(f"{req.url[:120]} {req.failure}"))

        print(f"-> Navigating to {URL}")
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"NAV ERROR: {e}")

        # Wait React mount.
        await page.wait_for_timeout(4000)

        title = await page.title()
        skin = await page.evaluate("() => document.documentElement.getAttribute('data-ui-skin')")
        root_size = await page.evaluate("() => document.getElementById('root')?.innerHTML.length || 0")
        body_text = await page.evaluate("() => (document.body.innerText || '').slice(0, 500)")

        # Take screenshot.
        await page.screenshot(path="tunnel_screenshot.png", full_page=False)

        print(f"\n=== TITLE: {title}")
        print(f"=== SKIN: {skin}")
        print(f"=== #root size: {root_size} chars")
        print(f"\n=== body.innerText preview ===")
        print(body_text)

        # Try clicking a module to see if interactions work.
        try:
            buttons = await page.query_selector_all("button")
            print(f"\n=== {len(buttons)} buttons found")
            # Look for sidebar buttons
            for i, b in enumerate(buttons[:10]):
                txt = (await b.inner_text())[:80].replace('\n', ' / ')
                print(f"  btn[{i}]: {txt}")
        except Exception as e:
            print(f"button query: {e}")

        print(f"\n=== console ({len(console_msgs)} msgs, last 25) ===")
        for m in console_msgs[-25:]:
            print(m)
        print(f"\n=== page errors ({len(page_errors)}) ===")
        for e in page_errors:
            print(e)
        print(f"\n=== failed requests ({len(failed_reqs)}) ===")
        for r in failed_reqs[:10]:
            print(r)

        await browser.close()
        print("\n[screenshot] tunnel_screenshot.png")

asyncio.run(main())
