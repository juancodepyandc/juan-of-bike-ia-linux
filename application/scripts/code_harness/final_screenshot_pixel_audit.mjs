import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import process from 'node:process'
import { chromium } from 'playwright'

const visualReportPath = process.argv[2]
const outputPath = process.argv[3]

if (!visualReportPath || !outputPath) {
  throw new Error('usage: final_screenshot_pixel_audit.mjs <visual-report> <pixel-report>')
}

const visualReport = JSON.parse(await readFile(visualReportPath, 'utf8'))
const screenshots = []
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage()
  for (const profile of visualReport.profiles || []) {
    const screenshotPath = path.resolve(profile.screenshot)
    const png = await readFile(screenshotPath)
    const dataUrl = `data:image/png;base64,${png.toString('base64')}`
    const stats = await page.evaluate(async (source) => {
      const image = new Image()
      image.src = source
      await image.decode()
      const canvas = document.createElement('canvas')
      canvas.width = image.naturalWidth
      canvas.height = image.naturalHeight
      const context = canvas.getContext('2d', { willReadFrequently: true })
      context.drawImage(image, 0, 0)
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data
      const sampleStride = Math.max(1, Math.floor(Math.sqrt((canvas.width * canvas.height) / 120_000)))
      const sums = [0, 0, 0]
      const squareSums = [0, 0, 0]
      const luminanceBins = new Array(32).fill(0)
      let count = 0
      for (let y = 0; y < canvas.height; y += sampleStride) {
        for (let x = 0; x < canvas.width; x += sampleStride) {
          const offset = (y * canvas.width + x) * 4
          const rgb = [pixels[offset], pixels[offset + 1], pixels[offset + 2]]
          for (let channel = 0; channel < 3; channel += 1) {
            sums[channel] += rgb[channel]
            squareSums[channel] += rgb[channel] ** 2
          }
          const luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
          luminanceBins[Math.min(31, Math.floor(luminance / 8))] += 1
          count += 1
        }
      }
      const stdev = sums.map((sum, channel) => {
        const mean = sum / count
        return Math.sqrt(Math.max(0, squareSums[channel] / count - mean ** 2))
      })
      const entropy = luminanceBins.reduce((total, bin) => {
        if (bin === 0) return total
        const probability = bin / count
        return total - probability * Math.log2(probability)
      }, 0)
      return { width: canvas.width, height: canvas.height, entropy, channelSpread: stdev.reduce((a, b) => a + b, 0) }
    }, dataUrl)
    const dimensionsMatch = stats.width === profile.width && stats.height === profile.height
    const nonBlank = stats.entropy > 1 && stats.channelSpread > 8
    screenshots.push({
      id: profile.id,
      path: screenshotPath,
      width: stats.width,
      height: stats.height,
      expectedWidth: profile.width,
      expectedHeight: profile.height,
      entropy: Number(stats.entropy.toFixed(4)),
      channelSpread: Number(stats.channelSpread.toFixed(4)),
      dimensionsMatch,
      nonBlank,
      ok: dimensionsMatch && nonBlank,
    })
  }
} finally {
  await browser.close()
}

const report = {
  schemaVersion: 'aurora.code.final-screenshot-pixels/1',
  visualReportPath: path.resolve(visualReportPath),
  screenshots,
  ok: visualReport.ok === true && screenshots.length === 7 && screenshots.every((item) => item.ok),
}

await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`)
process.stdout.write(`${JSON.stringify(report, null, 2)}\n`)
if (!report.ok) process.exitCode = 1
