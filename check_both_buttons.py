"""Test both settings buttons (⚙ + indicator) end-to-end."""
import asyncio
import sys
from playwright.async_api import async_playwright

URL = "https://lodging-fragrance-infections-expires.trycloudflare.com/"
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1400, "height": 900})
        page = await ctx.new_page()

        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)[:300]))

        await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3500)

        async def label_count():
            return await page.evaluate('() => document.querySelectorAll(".sp-label").length')

        async def close_panel():
            # Press Escape to close.
            await page.keyboard.press('Escape')
            await page.wait_for_timeout(400)

        # ──────────────────────────────────────────────────────
        # TEST 1 : ⚙ button
        # ──────────────────────────────────────────────────────
        print("\n=== TEST 1 : ⚙ button ===")
        before = await label_count()
        print(f"  before: sp-labels={before}")
        gear_btn = await page.query_selector('button[aria-label="Ouvrir les réglages"]')
        if not gear_btn:
            print("  ❌ ⚙ button NOT FOUND")
        else:
            box = await gear_btn.bounding_box()
            print(f"  ⚙ button found at {box}")
            await gear_btn.click()
            await page.wait_for_timeout(700)
            after = await label_count()
            print(f"  after click: sp-labels={after}  -> {'✓ OPENS' if after > before else '❌ NO EFFECT'}")
            if after > 0:
                await close_panel()

        # ──────────────────────────────────────────────────────
        # TEST 2 : indicator dot
        # ──────────────────────────────────────────────────────
        print("\n=== TEST 2 : indicator dot ===")
        before = await label_count()
        print(f"  before: sp-labels={before}")
        # Find indicator by its inner pulse dot or its title
        indicator = await page.evaluate_handle('''
            () => {
                const divs = Array.from(document.querySelectorAll('div'));
                return divs.find(d => {
                    const s = d.getAttribute('style') || '';
                    return s.includes('top: 12px') && s.includes('right: 12px') && s.includes('border-radius: 50%');
                });
            }
        ''')
        ind = indicator.as_element()
        if not ind:
            print("  ❌ indicator NOT FOUND")
        else:
            box = await ind.bounding_box()
            print(f"  indicator found at {box}")
            await ind.click()
            await page.wait_for_timeout(700)
            after = await label_count()
            print(f"  after click: sp-labels={after}  -> {'✓ OPENS' if after > before else '❌ NO EFFECT'}")
            if after > 0:
                await close_panel()

        # ──────────────────────────────────────────────────────
        # TEST 3 : event dispatch direct (control)
        # ──────────────────────────────────────────────────────
        print("\n=== TEST 3 : direct dispatch (control) ===")
        before = await label_count()
        print(f"  before: sp-labels={before}")
        await page.evaluate("() => window.dispatchEvent(new Event('aurora:open-settings'))")
        await page.wait_for_timeout(700)
        after = await label_count()
        print(f"  after dispatch: sp-labels={after}  -> {'✓ OPENS' if after > before else '❌ NO EFFECT'}")

        # Screenshot final
        await page.screenshot(path="both_buttons_check.png", full_page=False)

        print(f"\n=== page errors ({len(errors)}) ===")
        for e in errors[:5]:
            print(e)

        await browser.close()
        print("\n[screenshot] both_buttons_check.png")


asyncio.run(main())
