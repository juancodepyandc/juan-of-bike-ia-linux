"""Test 'Charger ma session' button via Playwright."""
import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from playwright.async_api import async_playwright

URL = 'https://lodging-fragrance-infections-expires.trycloudflare.com/'

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})
        msgs = []
        page.on('console', lambda m: msgs.append(f'[{m.type}] {m.text[:300]}'))

        # Pre-set localStorage to match BUILD_ID so auto-purge doesn't fire.
        await page.context.add_init_script(
            "try{localStorage.setItem('aurora_build_id_html','v82lg')}catch(e){}"
        )
        await page.goto(URL, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(5500)

        # Click Academy module (find by emoji "∎" or label "Academy" with shortcut "8")
        clicked = await page.evaluate('''() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const acad = btns.find(b => b.textContent && b.textContent.includes('Academy'));
            if (acad) { acad.click(); return true; }
            return false;
        }''')
        print(f'Academy click: {clicked}')
        await page.wait_for_timeout(2500)

        # Select parcours-bac mode
        sel = await page.evaluate('''() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const m = btns.find(b => /Parcours BAC/i.test(b.textContent || ''));
            if (m) { m.click(); return true; }
            return false;
        }''')
        print(f'parcours-bac mode select: {sel}')
        await page.wait_for_timeout(500)

        # Click "Charger ma session"
        loaded = await page.evaluate('''() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const ld = btns.find(b => /Charger.*session/i.test(b.textContent || ''));
            if (ld) {
                ld.click();
                return { found: true, text: ld.textContent };
            }
            return { found: false };
        }''')
        print(f'load click: {loaded}')
        await page.wait_for_timeout(3500)

        # Check what's now visible
        info = await page.evaluate('''() => {
            const txt = document.body.innerText;
            return {
                hasSynthese: txt.includes('Synthèse') || txt.includes('Synthese'),
                has2020: txt.includes('20/20'),
                hasFiches: txt.includes('Fiches stylis'),
                hasMondialisation: txt.includes('Mondialisation') || txt.includes('mondialisation'),
                hasControle: txt.includes('Contrôle') || txt.includes('Controle'),
                academyOutput: txt.length,
            };
        }''')
        print(f'synthese visible : {info["hasSynthese"]}')
        print(f'20/20 visible    : {info["has2020"]}')
        print(f'fiches visible   : {info["hasFiches"]}')
        print(f'mondialisation   : {info["hasMondialisation"]}')
        print(f'contrôle         : {info["hasControle"]}')
        print(f'body text length : {info["academyOutput"]}')

        print()
        print('--- console aurora messages ---')
        for m in msgs:
            if 'aurora' in m.lower():
                print(m)

        await page.screenshot(path='check_charger.png', full_page=False)
        print('\n[screenshot] check_charger.png')
        await browser.close()

asyncio.run(main())
