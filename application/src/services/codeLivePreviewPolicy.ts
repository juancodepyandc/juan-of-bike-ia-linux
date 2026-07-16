export const LIVE_PREVIEW_TOTAL_CAP_BYTES = 150_000

export function shouldPauseLivePreviewDuringGeneration({
  isGenerating,
  totalBytes,
  isHeavy,
  byteCap = LIVE_PREVIEW_TOTAL_CAP_BYTES,
}: {
  isGenerating: boolean
  totalBytes: number
  isHeavy: boolean
  byteCap?: number
}): boolean {
  return isGenerating && (isHeavy || totalBytes > byteCap)
}
