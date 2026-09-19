import { chromium, firefox, webkit } from 'playwright'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const BROWSERS = [
  { id: 'playwright_chromium', label: 'Playwright Chromium desktop', family: 'web', browser: 'chromium', launcher: chromium },
  { id: 'playwright_firefox', label: 'Playwright Firefox desktop', family: 'web', browser: 'firefox', launcher: firefox },
  { id: 'playwright_webkit', label: 'Playwright WebKit desktop', family: 'web', browser: 'webkit', launcher: webkit },
]

async function runBrowser(profile, url, outDir, waitMs) {
  const { launcher, ...publicProfile } = profile
  const consoleErrors = []
  let browser = null
  try {
    browser = await launcher.launch({
      headless: true,
      ...(profile.browser === 'chromium' ? { args: ['--no-sandbox', '--disable-dev-shm-usage'] } : {}),
    })
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      deviceScaleFactor: 1,
      userAgent: `AuroraCodeWS12/${profile.browser}`,
    })
    const page = await context.newPage()
    page.on('console', (msg) => {
      if (msg.type() === 'error' || msg.type() === 'warning') consoleErrors.push(msg.text().slice(0, 300))
    })
    page.on('pageerror', (err) => consoleErrors.push((err.message || String(err)).slice(0, 300)))
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: Math.max(15000, waitMs + 10000) })
    await sleep(waitMs)
    const screenshotPath = join(outDir, `${profile.id}.png`)
    await page.screenshot({ path: screenshotPath, fullPage: true })
    const metrics = await page.evaluate(() => ({
      bodyTextLength: (document.body?.innerText || '').length,
      headingCount: document.querySelectorAll('h1,h2,h3,[role="heading"]').length,
      mediaCount: document.querySelectorAll('img,svg,video,picture,canvas').length,
      interactiveCount: document.querySelectorAll('a[href],button,input,select,textarea,[role="button"],[tabindex]').length,
    }))
    await browser.close()
    return {
      ...publicProfile,
      status: 'executed',
      realExecution: true,
      viewport: '1280x800',
      width: 1280,
      height: 800,
      dpr: 1,
      touch: false,
      screenshotPath,
      bodyTextLength: metrics.bodyTextLength,
      headingCount: metrics.headingCount,
      mediaCount: metrics.mediaCount,
      interactiveCount: metrics.interactiveCount,
      consoleErrors,
      exceptions: [],
      failedRequests: [],
    }
  } catch (error) {
    try { await browser?.close() } catch (_) {}
    return {
      ...publicProfile,
      status: 'unavailable',
      realExecution: false,
      error: String(error?.message || error).split('\n').slice(0, 8).join('\n'),
    }
  }
}

async function main() {
  const [url, outDir, waitRaw] = process.argv.slice(2)
  if (!url || !outDir) {
    console.error('usage: playwright_execute.mjs <url> <out_dir> [wait_ms]')
    process.exit(2)
  }
  mkdirSync(outDir, { recursive: true })
  const waitMs = Math.max(500, Math.min(8000, Number(waitRaw) || 2500))
  const stages = []
  for (const browser of BROWSERS) {
    stages.push(await runBrowser(browser, url, outDir, waitMs))
  }
  process.stdout.write(JSON.stringify({
    schemaVersion: 'aurora.code.simulation-lab/1',
    url,
    createdAt: Date.now(),
    stages,
  }))
}

main().catch((error) => {
  process.stdout.write(JSON.stringify({ ok: false, error: String(error?.message || error) }))
  process.exit(1)
})
