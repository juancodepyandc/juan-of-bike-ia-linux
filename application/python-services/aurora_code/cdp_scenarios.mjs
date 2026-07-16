import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

export function viewportName(width, height) {
  return `${width}x${height}`
}

const USER_AGENTS = {
  desktop: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36',
  android: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Mobile Safari/537.36',
  tablet: 'Mozilla/5.0 (Linux; Android 14; Pixel Tablet) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36',
}

const SIMULATION_PRESETS = [
  {
    id: 'chromium_desktop_fast',
    label: 'Chromium desktop 1440 fast',
    width: 1440,
    height: 900,
    dpr: 1,
    mobile: false,
    touch: false,
    cpuThrottle: 1,
    userAgent: USER_AGENTS.desktop,
  },
  {
    id: 'chromium_mobile_4g_touch',
    label: 'Chromium Pixel 8 touch 4G',
    width: 390,
    height: 844,
    dpr: 3,
    mobile: true,
    touch: true,
    cpuThrottle: 4,
    userAgent: USER_AGENTS.android,
    network: {
      latencyMs: 90,
      downloadBytesPerSecond: 1_600_000,
      uploadBytesPerSecond: 750_000,
      connectionType: 'cellular4g',
    },
  },
  {
    id: 'chromium_tablet_slow_3g_touch',
    label: 'Chromium tablet touch slow-3G',
    width: 834,
    height: 1112,
    dpr: 2,
    mobile: true,
    touch: true,
    cpuThrottle: 6,
    userAgent: USER_AGENTS.tablet,
    network: {
      latencyMs: 320,
      downloadBytesPerSecond: 55_000,
      uploadBytesPerSecond: 32_000,
      connectionType: 'cellular3g',
    },
  },
]

export async function simulate(url, outDir, waitMs, inspect) {
  mkdirSync(outDir, { recursive: true })
  const stages = []
  for (const preset of SIMULATION_PRESETS) {
    const screenshotPath = join(outDir, `${preset.id}.png`)
    try {
      const report = await inspect(url, screenshotPath, preset.width, preset.height, waitMs, preset.mobile, preset)
      const metrics = report.render_metrics || {}
      stages.push({
        id: preset.id,
        label: preset.label,
        family: 'web',
        browser: 'chromium',
        status: 'executed',
        realExecution: true,
        viewport: viewportName(preset.width, preset.height),
        width: preset.width,
        height: preset.height,
        dpr: preset.dpr,
        touch: !!preset.touch,
        userAgent: preset.userAgent,
        throttling: { cpu: preset.cpuThrottle || 1, network: preset.network || null },
        screenshotPath,
        bodyTextLength: metrics.bodyTextLength || report.body_text_len || 0,
        headingCount: metrics.headingCount || 0,
        mediaCount: metrics.mediaCount || 0,
        interactiveCount: metrics.interactiveCount || 0,
        consoleErrors: (report.console_errors || []).map((item) => item.text || String(item)),
        exceptions: (report.exceptions || []).map((item) => item.text || String(item)),
        failedRequests: (report.failed_requests || []).map((item) => item.url ? `${item.url} ${item.errorText || ''}` : String(item)),
        performanceMetrics: report.performance_metrics || {},
      })
    } catch (error) {
      stages.push({
        id: preset.id,
        label: preset.label,
        family: 'web',
        browser: 'chromium',
        status: 'unavailable',
        realExecution: false,
        viewport: viewportName(preset.width, preset.height),
        error: String(error?.message || error),
      })
    }
  }
  return {
    schemaVersion: 'aurora.code.simulation-lab/1',
    url,
    createdAt: Date.now(),
    stages,
  }
}

export async function audit(url, outDir, waitMs, inspect) {
  mkdirSync(outDir, { recursive: true })
  const viewports = [
    { width: 390, height: 844, mobile: true },
    { width: 834, height: 1112, mobile: true },
    { width: 1440, height: 900, mobile: false },
  ]
  const viewportsReport = []
  for (const viewport of viewports) {
    const name = viewportName(viewport.width, viewport.height)
    const screenshotPath = join(outDir, `${name}.png`)
    const report = await inspect(url, screenshotPath, viewport.width, viewport.height, waitMs, viewport.mobile)
    const metrics = report.render_metrics || {}
    viewportsReport.push({
      viewport: name,
      width: viewport.width,
      height: viewport.height,
      screenshotPath,
      bodyTextLength: metrics.bodyTextLength || report.body_text_len || 0,
      consoleErrors: (report.console_errors || []).map((item) => item.text || String(item)),
      exceptions: (report.exceptions || []).map((item) => item.text || String(item)),
      failedRequests: (report.failed_requests || []).map((item) => item.url ? `${item.url} ${item.errorText || ''}` : String(item)),
      canvasPresent: !!metrics.canvasPresent,
      textNodeCount: metrics.textNodeCount || 0,
      headingCount: metrics.headingCount || 0,
      mediaCount: metrics.mediaCount || 0,
      interactiveCount: metrics.interactiveCount || 0,
      cssVarCount: metrics.cssVarCount || 0,
      fontFamilies: metrics.fontFamilies || [],
      verticalGapMedian: metrics.verticalGapMedian ?? null,
      contrastSamples: metrics.contrastSamples || [],
    })
  }
  return {
    schemaVersion: 'aurora.code.visual-render-audit/1',
    url,
    createdAt: Date.now(),
    viewports: viewportsReport,
  }
}
