import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import { chromium } from 'playwright'

const baseUrl = process.env.AURORA_URL || 'http://127.0.0.1:1431'
const outputDir = path.resolve(
  process.env.AURORA_PROOF_DIR || 'output/final_code_refonte_validation/screens',
)

const files = [
  {
    name: 'index.html',
    language: 'html',
    content: `<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Aurora Control</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <aside>
    <strong>AURORA / CONTROL</strong>
    <nav><button class="active">Vue generale</button><button>Projets</button><button>Qualite</button></nav>
  </aside>
  <main>
    <header><div><small>MISSION ACTIVE</small><h1>Orchestration produit</h1></div><span class="status">Systemes operationnels</span></header>
    <section class="metrics">
      <article><small>Score qualite</small><b>96</b><span>+8 cette semaine</span></article>
      <article><small>Modules valides</small><b>11</b><span>0 regression</span></article>
      <article><small>Environnements</small><b>11</b><span>Executions reelles</span></article>
    </section>
    <section class="work">
      <article class="chart"><div class="section-title"><h2>Signal de livraison</h2><span>7 derniers runs</span></div><div class="bars">${[58, 72, 66, 84, 78, 91, 96].map((height) => `<i style="height:${height}%"></i>`).join('')}</div></article>
      <article class="feed"><div class="section-title"><h2>Activite</h2><span>Temps reel</span></div><ul><li><b>Build production</b><span>reussi</span></li><li><b>Audit visuel</b><span>96 / 100</span></li><li><b>Android tablette</b><span>verifie</span></li></ul></article>
    </section>
  </main>
  <script src="app.js"></script>
</body>
</html>`,
  },
  {
    name: 'styles.css',
    language: 'css',
    content: `:root{font-family:Inter,system-ui,sans-serif;color:#eef3f8;background:#090c10}*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;grid-template-columns:220px 1fr;background:#090c10}aside{padding:28px 18px;border-right:1px solid #28313a;background:#0e1318}aside strong{font-size:12px;letter-spacing:.12em;color:#74d9cd}nav{display:grid;gap:7px;margin-top:38px}button{border:0;background:transparent;color:#8795a3;text-align:left;padding:11px 12px;border-radius:6px}button.active,button:hover{background:#182129;color:#f4f8fb}main{padding:32px;min-width:0}header,.section-title{display:flex;align-items:center;justify-content:space-between;gap:18px}small{font-size:10px;letter-spacing:.12em;color:#758491}h1{font-size:27px;margin:6px 0 0}h2{font-size:14px;margin:0}.status{font-size:11px;color:#67d6a8;border:1px solid #2b6851;padding:7px 10px;border-radius:999px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:28px 0}.metrics article,.work article{border:1px solid #27313a;background:#11171d;border-radius:7px;padding:18px}.metrics b{display:block;font-size:29px;margin:10px 0 4px}.metrics span,.section-title span,li span{font-size:11px;color:#81909d}.work{display:grid;grid-template-columns:1.4fr 1fr;gap:12px}.bars{height:230px;display:flex;align-items:end;gap:9px;padding-top:32px}.bars i{flex:1;min-width:9px;background:#53c8b6;border-radius:3px 3px 0 0}ul{list-style:none;padding:10px 0 0;margin:0}li{display:flex;justify-content:space-between;gap:12px;padding:15px 0;border-bottom:1px solid #242d35;font-size:12px}@media(max-width:720px){body{grid-template-columns:1fr}aside{display:none}main{padding:20px}.metrics,.work{grid-template-columns:1fr}.metrics{gap:8px;margin:20px 0}.bars{height:180px}header{align-items:flex-start;flex-direction:column}h1{font-size:22px}}`,
  },
  {
    name: 'app.js',
    language: 'javascript',
    content: `document.querySelectorAll('nav button').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('nav button').forEach((item) => item.classList.remove('active'))
    button.classList.add('active')
    document.body.dataset.interaction = 'verified'
  })
})
document.body.dataset.execution = 'verified'
parent.postMessage({ source: 'aurora-final-proof', execution: 'verified', title: document.querySelector('h1')?.textContent }, '*')`,
  },
  {
    name: 'README.md',
    language: 'markdown',
    content: '# Aurora Control\n\nDashboard de preuve pour la validation visuelle finale.',
  },
]

const validationResult = {
  ok: true,
  rootPath: '/workspace/aurora-control',
  summary: 'Build, tests fonctionnels et audit visuel valides.',
  question: null,
  detectedLanguage: 'node',
  steps: [
    { label: 'Build production', command: 'npm run build', ok: true, output: 'Build termine sans erreur.' },
  ],
}

const requestedProfiles = new Set(
  (process.env.AURORA_PROFILES || '').split(',').map((value) => value.trim()).filter(Boolean),
)
const profiles = [
  { id: 'v4_desktop', skin: 'aurora_v4', width: 1440, height: 1000 },
  { id: 'v4_tablet', skin: 'aurora_v4', width: 1024, height: 1366 },
  { id: 'v4_tablet_delivery', skin: 'aurora_v4', width: 1024, height: 1366, focus: 'delivery' },
  { id: 'v4_mobile', skin: 'aurora_v4', width: 390, height: 844 },
  { id: 'v4_mobile_delivery', skin: 'aurora_v4', width: 390, height: 844, focus: 'delivery' },
  { id: 'v1_desktop', skin: 'aurora_v1', width: 1440, height: 1000 },
  { id: 'v3_desktop', skin: 'aurora_v3', width: 1440, height: 1000 },
].filter((profile) => requestedProfiles.size === 0 || requestedProfiles.has(profile.id))

async function seedCodeModule(page) {
  await page.evaluate(async ({ proofFiles, proofValidation }) => {
    const [{ useAppStore }, { useCodeWorkspaceStore }, { useModuleHistoryStore }, { useCodeStreamStore }] = await Promise.all([
      import('/src/stores/appStore.ts'),
      import('/src/stores/codeWorkspaceStore.ts'),
      import('/src/stores/moduleHistoryStore.ts'),
      import('/src/stores/codeStreamStore.ts'),
    ])
    const history = useModuleHistoryStore.getState()
    const sessionId = history.createSession('code', 'Preuve finale refonte Code')
    useCodeWorkspaceStore.getState().setWorkspaceSnapshot({
      sessionId,
      prompt: 'Construis un tableau de bord operationnel complet et responsive.',
      progress: 'Projet valide et pret a livrer.',
      notes: 'Contrats WS7, WS9, WS11, WS12 et WS15 verifies.',
      files: proofFiles,
      activeFile: 0,
      error: null,
      validationResult: proofValidation,
      correctionLog: [],
      intent: null,
      totalAttempts: 2,
      finalScore: 96,
      consoleOutput: '[build] production OK\n[visual] score 96/100',
      recoveryStatus: null,
      preflightReport: null,
      pendingResume: false,
      resumeFailCount: 0,
      lastResumeAttempt: null,
    })
    useCodeStreamStore.setState({
      activeSessionId: sessionId,
      draft: 'Construis un tableau de bord operationnel complet et responsive.',
      streaming: false,
      streamOutput: '',
      error: null,
      lastCompletedAt: Date.now(),
      runId: 1,
      phase: 'done',
      phaseMessage: '',
      errorDialog: null,
      modelUsed: 'qwen3-coder:30b',
      files: proofFiles,
      notes: 'Build et validation termines.',
      finalScore: 96,
      totalAttempts: 2,
      progressPct: 100,
      genStartedAt: Date.now() - 42_000,
      etaSecondsRemaining: 0,
      etaTotalSeconds: 42,
      messages: [{ role: 'user', content: 'Construis le tableau de bord.' }],
    })
    useAppStore.getState().setActiveModule('code')
  }, { proofFiles: files, proofValidation: validationResult })
}

async function dismissPrivilegeDialog(page) {
  const dismiss = page.getByRole('button', { name: 'Continuer sans admin' })
  if (await dismiss.isVisible({ timeout: 1_500 }).catch(() => false)) await dismiss.click()
}

async function inspectLayout(page) {
  return page.evaluate(() => {
    const root = document.querySelector('[data-code-view="true"], .aurora-v1-cols')
    const iframe = document.querySelector('iframe[title="Rendu live de la page"], iframe[title="aurora-code-preview"]')
    const iframeBody = iframe?.contentDocument?.body
    const runtimeProof = window.__auroraFinalProof
    const visibleControls = [...root?.querySelectorAll('button, input, textarea, [role="button"]') || []]
      .filter((element) => {
        const node = element
        const style = getComputedStyle(node)
        const rect = node.getBoundingClientRect()
        return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none'
      })
    const clippedText = visibleControls
      .filter((element) => element.scrollWidth > element.clientWidth + 2)
      .map((element) => (element.textContent || element.getAttribute('placeholder') || '').trim())
      .filter(Boolean)
      .slice(0, 20)
    const clippedButtons = visibleControls
      .filter((element) => element.matches('button, [role="button"]'))
      .filter((element) => element.scrollWidth > element.clientWidth + 2)
      .map((element) => (element.textContent || element.getAttribute('aria-label') || '').trim())
      .filter(Boolean)
      .slice(0, 20)
    const offscreenControls = visibleControls
      .filter((element) => {
        const rect = element.getBoundingClientRect()
        return rect.left < -1 || rect.right > document.documentElement.clientWidth + 1
      })
      .map((element) => ({
        text: (element.textContent || element.getAttribute('aria-label') || element.getAttribute('placeholder') || '').trim(),
        rect: element.getBoundingClientRect().toJSON(),
      }))
      .slice(0, 20)
    return {
      codeViewFound: Boolean(root),
      codeViewRect: root ? root.getBoundingClientRect().toJSON() : null,
      bodyTextLength: document.body.innerText.length,
      iframeFound: Boolean(iframe),
      previewTitle: iframeBody?.querySelector('h1')?.textContent || runtimeProof?.title || null,
      previewExecution: iframeBody?.dataset.execution || runtimeProof?.execution || null,
      documentClientWidth: document.documentElement.clientWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      horizontalOverflowPx: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
      clippedText,
      clippedButtons,
      offscreenControls,
    }
  })
}

async function captureProfile(browser, profile) {
  const context = await browser.newContext({
    viewport: { width: profile.width, height: profile.height },
    deviceScaleFactor: 1,
    colorScheme: 'dark',
    reducedMotion: 'reduce',
  })
  const page = await context.newPage()
  const consoleErrors = []
  const pageErrors = []
  const failedRequests = []
  page.on('console', async (message) => {
    if (message.type() !== 'error') return
    const args = await Promise.all(message.args().map(async (argument) => {
      try { return await argument.jsonValue() } catch { return String(argument) }
    }))
    consoleErrors.push({ text: message.text(), args, location: message.location() })
  })
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('requestfailed', (request) => failedRequests.push({
    url: request.url(),
    error: request.failure()?.errorText || 'unknown',
  }))

  const shellUrl = new URL('/scripts/code_harness/visual_shell.html', baseUrl)
  shellUrl.searchParams.set('skin', profile.skin)
  await page.goto(shellUrl.href, { waitUntil: 'domcontentloaded', timeout: 60_000 })
  await dismissPrivilegeDialog(page)
  await page.evaluate(async () => {
    const { installReactKeyProbe } = await import('/scripts/code_harness/react_key_probe.ts')
    installReactKeyProbe()
    window.__auroraFinalProof = null
    window.addEventListener('message', (event) => {
      if (event.data?.source === 'aurora-final-proof') window.__auroraFinalProof = event.data
    })
  })
  await seedCodeModule(page)
  await dismissPrivilegeDialog(page)
  const rootSelector = profile.skin === 'aurora_v1' ? '.aurora-v1-cols' : '[data-code-view="true"]'
  await page.locator(rootSelector).waitFor({ state: 'visible', timeout: 60_000 })
  await page.waitForTimeout(2_500)
  await page.waitForFunction(() => {
    const frame = document.querySelector('iframe[title="Rendu live de la page"], iframe[title="aurora-code-preview"]')
    return frame?.contentDocument?.body?.dataset.execution === 'verified'
      || window.__auroraFinalProof?.execution === 'verified'
  }, null, { timeout: 30_000 })

  if (profile.focus === 'delivery') {
    await page.getByRole('heading', { name: 'Scene code', exact: true }).scrollIntoViewIfNeeded()
    await page.waitForTimeout(300)
  }

  const screenshot = path.join(outputDir, `${profile.id}.png`)
  await page.screenshot({ path: screenshot, fullPage: false })
  const layout = await inspectLayout(page)
  const relevantFailedRequests = failedRequests.filter((request) => request.error !== 'net::ERR_ABORTED')
  const result = {
    ...profile,
    screenshot,
    url: page.url(),
    ...layout,
    consoleErrors: consoleErrors.slice(0, 50),
    pageErrors: [...new Set(pageErrors)].slice(0, 50),
    failedRequests: relevantFailedRequests.slice(0, 50),
    cancelledRequestCount: failedRequests.length - relevantFailedRequests.length,
    reactKeyOwnerStacks: await page.evaluate(() => window.__auroraReactKeyStacks || []),
  }
  await context.close()
  return result
}

await mkdir(outputDir, { recursive: true })
const browser = await chromium.launch({ headless: true })
const startedAt = new Date().toISOString()
const results = []
try {
  for (const profile of profiles) results.push(await captureProfile(browser, profile))
} finally {
  await browser.close()
}

const failures = results.flatMap((result) => {
  const issues = []
  if (!result.codeViewFound) issues.push('module Code absent')
  if (!result.iframeFound) issues.push('preview absente')
  if (result.previewExecution !== 'verified') issues.push('code preview non execute')
  if (result.previewTitle !== 'Orchestration produit') issues.push('contenu preview inattendu')
  if (result.horizontalOverflowPx > 1) issues.push(`debordement horizontal ${result.horizontalOverflowPx}px`)
  if (result.clippedButtons.length > 0) issues.push(`${result.clippedButtons.length} bouton(s) tronque(s)`)
  if (result.offscreenControls.length > 0) issues.push(`${result.offscreenControls.length} controle(s) hors viewport`)
  if (result.consoleErrors.length > 0) issues.push(`${result.consoleErrors.length} erreur(s) console`)
  if (result.pageErrors.length > 0) issues.push(`${result.pageErrors.length} erreur(s) page`)
  if (result.failedRequests.length > 0) issues.push(`${result.failedRequests.length} requete(s) echouee(s)`)
  return issues.map((issue) => ({ profile: result.id, issue }))
})
const report = {
  startedAt,
  finishedAt: new Date().toISOString(),
  baseUrl,
  profiles: results,
  failures,
  ok: failures.length === 0,
}
await writeFile(path.join(outputDir, 'report.json'), `${JSON.stringify(report, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
if (!report.ok) process.exitCode = 1
