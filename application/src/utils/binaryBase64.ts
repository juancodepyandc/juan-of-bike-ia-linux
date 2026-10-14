/** Encode image bytes without exceeding the JavaScript argument stack. */
export function binaryBase64(input: Uint8Array | number[]): string {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input)
  const chunks: string[] = []
  for (let offset = 0; offset < bytes.length; offset += 32768) {
    chunks.push(String.fromCharCode(...bytes.subarray(offset, offset + 32768)))
  }
  return btoa(chunks.join(''))
}
