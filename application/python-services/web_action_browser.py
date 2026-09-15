import sys
import json
import asyncio
from playwright.async_api import async_playwright

async def run_action(payload):
    action = payload.get("action")
    url = payload.get("url")
    selector = payload.get("selector")
    value = payload.get("value")
    headless = payload.get("headless", True)  # Autonome et background par defaut

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            if action == "navigate":
                await page.goto(url)
                await page.wait_for_load_state("networkidle")
                return {"ok": True, "title": await page.title(), "url": page.url}
            
            elif action == "click":
                if url:
                    await page.goto(url)
                    await page.wait_for_load_state("networkidle")
                await page.click(selector)
                await page.wait_for_load_state("networkidle")
                return {"ok": True, "title": await page.title(), "url": page.url}
            
            elif action == "fill":
                if url:
                    await page.goto(url)
                    await page.wait_for_load_state("networkidle")
                await page.fill(selector, value)
                return {"ok": True, "title": await page.title(), "url": page.url}
                
            elif action == "extract_dom":
                # Extrait une vue simplifiee du DOM pour l'agent (liens, boutons, inputs)
                if url:
                    await page.goto(url)
                    await page.wait_for_load_state("networkidle")
                
                # Script JS pour recuperer les elements interactifs
                script = """
                () => {
                    const elements = Array.from(document.querySelectorAll('a, button, input, textarea, select'));
                    return elements.map(el => {
                        let id = el.id ? `#${el.id}` : '';
                        let cls = el.className ? `.${el.className.split(' ').join('.')}` : '';
                        let text = el.innerText || el.value || el.placeholder || '';
                        let tag = el.tagName.toLowerCase();
                        return `${tag}${id}${cls} -> ${text}`;
                    }).filter(s => s.length > 5);
                }
                """
                interactive_elements = await page.evaluate(script)
                return {"ok": True, "url": page.url, "interactive_elements": interactive_elements}

            elif action == "extract_html":
                if url:
                    await page.goto(url)
                    await page.wait_for_load_state("networkidle")
                html = await page.content()
                return {"ok": True, "html": html[:50000]}

            else:
                return {"ok": False, "error": f"Unknown action: {action}"}
        
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            if not headless:
                await asyncio.sleep(2.0)
            await browser.close()

if __name__ == "__main__":
    try:
        input_data = sys.stdin.read()
        payload = json.loads(input_data)
        result = asyncio.run(run_action(payload))
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
