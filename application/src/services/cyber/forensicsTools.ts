// Forensics tools — extracteurs locaux pour binaires / images.
//   - strings : printable strings d'un blob binaire (taille min 4 chars)
//   - exif : parse minimal des tags EXIF d'une image JPEG
//   - hex / hexdump : dump hexadécimal avec offset + ASCII view
//   - file magic : détecte le type de fichier par signature (magic bytes)

export type StringMatch = {
  offset: number
  text: string
  length: number
}

/**
 * Extrait toutes les chaînes printables ASCII de longueur ≥ minLen.
 */
export function extractStrings(bytes: Uint8Array, minLen = 4): StringMatch[] {
  const out: StringMatch[] = []
  let current = ''
  let start = 0
  for (let i = 0; i < bytes.length; i += 1) {
    const c = bytes[i]
    const printable = c >= 0x20 && c < 0x7f
    if (printable) {
      if (current.length === 0) start = i
      current += String.fromCharCode(c)
    } else {
      if (current.length >= minLen) {
        out.push({ offset: start, text: current, length: current.length })
      }
      current = ''
    }
  }
  if (current.length >= minLen) {
    out.push({ offset: start, text: current, length: current.length })
  }
  return out
}

export type MagicHit = {
  type: string
  description: string
  confidence: number
}

const MAGIC_TABLE: Array<{ sig: number[]; type: string; description: string }> = [
  { sig: [0xff, 0xd8, 0xff], type: 'JPEG', description: 'JPEG image (3-byte SOI + APPx)' },
  { sig: [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a], type: 'PNG', description: 'PNG image (RFC 2083)' },
  { sig: [0x47, 0x49, 0x46, 0x38], type: 'GIF', description: 'GIF (87a/89a)' },
  { sig: [0x25, 0x50, 0x44, 0x46], type: 'PDF', description: 'PDF document' },
  { sig: [0x50, 0x4b, 0x03, 0x04], type: 'ZIP/DOCX/JAR', description: 'ZIP archive (or Office/JAR)' },
  { sig: [0x1f, 0x8b], type: 'GZIP', description: 'GZIP compressed' },
  { sig: [0x42, 0x5a, 0x68], type: 'BZIP2', description: 'bzip2 compressed' },
  { sig: [0x37, 0x7a, 0xbc, 0xaf, 0x27, 0x1c], type: '7Z', description: '7-Zip archive' },
  { sig: [0x52, 0x61, 0x72, 0x21], type: 'RAR', description: 'RAR archive' },
  { sig: [0x4d, 0x5a], type: 'PE/EXE', description: 'Windows executable (PE/COFF)' },
  { sig: [0x7f, 0x45, 0x4c, 0x46], type: 'ELF', description: 'Linux executable (ELF)' },
  { sig: [0xfe, 0xed, 0xfa, 0xce], type: 'MachO', description: 'macOS executable (Mach-O 32)' },
  { sig: [0xcf, 0xfa, 0xed, 0xfe], type: 'MachO64', description: 'macOS executable (Mach-O 64)' },
  { sig: [0x49, 0x44, 0x33], type: 'MP3', description: 'MP3 audio (ID3 tag)' },
  { sig: [0xff, 0xfb], type: 'MP3', description: 'MP3 audio (raw)' },
  { sig: [0x52, 0x49, 0x46, 0x46], type: 'RIFF', description: 'RIFF (WAV/AVI)' },
  { sig: [0x66, 0x74, 0x79, 0x70], type: 'MP4', description: 'MP4 video (ftyp box)' },
  { sig: [0x4f, 0x67, 0x67, 0x53], type: 'OGG', description: 'OGG container' },
  { sig: [0x49, 0x49, 0x2a, 0x00], type: 'TIFF-LE', description: 'TIFF little-endian' },
  { sig: [0x4d, 0x4d, 0x00, 0x2a], type: 'TIFF-BE', description: 'TIFF big-endian' },
  { sig: [0x42, 0x4d], type: 'BMP', description: 'Bitmap BMP' },
]

export function detectMagic(bytes: Uint8Array): MagicHit[] {
  const out: MagicHit[] = []
  for (const m of MAGIC_TABLE) {
    if (bytes.length < m.sig.length) continue
    let ok = true
    for (let i = 0; i < m.sig.length; i += 1) {
      // MP4 ftyp is at offset 4, others at 0. For simplicity check both.
      if (m.type === 'MP4') {
        if (bytes[i + 4] !== m.sig[i]) { ok = false; break }
      } else {
        if (bytes[i] !== m.sig[i]) { ok = false; break }
      }
    }
    if (ok) out.push({ type: m.type, description: m.description, confidence: 0.95 })
  }
  return out
}

/**
 * Hex dump : produit des lignes "OFFSET  HEX  ASCII" comme xxd / hexdump.
 */
export function hexDump(bytes: Uint8Array, maxLines = 64, perLine = 16): string {
  const lines: string[] = []
  const total = Math.min(bytes.length, maxLines * perLine)
  for (let i = 0; i < total; i += perLine) {
    const offset = i.toString(16).padStart(8, '0')
    const slice = bytes.slice(i, i + perLine)
    const hex = Array.from(slice).map((b) => b.toString(16).padStart(2, '0')).join(' ')
    const ascii = Array.from(slice).map((b) => b >= 0x20 && b < 0x7f ? String.fromCharCode(b) : '.').join('')
    lines.push(`${offset}  ${hex.padEnd(perLine * 3 - 1, ' ')}  ${ascii}`)
  }
  if (bytes.length > total) {
    lines.push(`… (+ ${bytes.length - total} bytes)`)
  }
  return lines.join('\n')
}

/**
 * EXIF minimal pour JPEG : parse les APP1 markers et extrait quelques tags
 * communs (Make, Model, DateTime, GPS).
 *
 * Approche : on cherche le marker APP1 (0xFFE1) + signature "Exif\0\0",
 * puis on parse les IFDs minimalement. Pas de full TIFF parser — juste les
 * tags les plus pertinents pour forensics.
 */
export type ExifTag = {
  tag: string
  value: string
}

const KNOWN_TAGS: Record<number, string> = {
  0x010f: 'Make',
  0x0110: 'Model',
  0x0112: 'Orientation',
  0x011a: 'XResolution',
  0x011b: 'YResolution',
  0x0131: 'Software',
  0x0132: 'DateTime',
  0x013b: 'Artist',
  0x013e: 'WhitePoint',
  0x8769: 'ExifIFDPointer',
  0x8825: 'GPSInfoIFDPointer',
  0x9003: 'DateTimeOriginal',
  0x9004: 'DateTimeDigitized',
  0x920a: 'FocalLength',
  0x927c: 'MakerNote',
  0x9286: 'UserComment',
  0xa002: 'ImageWidth',
  0xa003: 'ImageHeight',
  0x010e: 'ImageDescription',
}

export function parseExif(bytes: Uint8Array): ExifTag[] {
  // Vérifie SOI JPEG.
  if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) return []
  let i = 2
  while (i < bytes.length - 4) {
    if (bytes[i] !== 0xff) break
    const marker = bytes[i + 1]
    const size = (bytes[i + 2] << 8) | bytes[i + 3]
    if (marker === 0xe1) {
      // APP1 segment. Check "Exif\0\0".
      const sigStart = i + 4
      if (
        bytes[sigStart] === 0x45 && bytes[sigStart + 1] === 0x78 &&
        bytes[sigStart + 2] === 0x69 && bytes[sigStart + 3] === 0x66 &&
        bytes[sigStart + 4] === 0x00 && bytes[sigStart + 5] === 0x00
      ) {
        return parseTiffIfd(bytes, sigStart + 6)
      }
    }
    if (size === 0) break
    i += 2 + size
  }
  return []
}

function parseTiffIfd(bytes: Uint8Array, base: number): ExifTag[] {
  // Endianness (II = little-endian, MM = big-endian).
  if (base + 8 > bytes.length) return []
  const littleEndian = bytes[base] === 0x49 && bytes[base + 1] === 0x49
  const u16 = (off: number) => littleEndian
    ? bytes[off] | (bytes[off + 1] << 8)
    : (bytes[off] << 8) | bytes[off + 1]
  const u32 = (off: number) => littleEndian
    ? bytes[off] | (bytes[off + 1] << 8) | (bytes[off + 2] << 16) | (bytes[off + 3] << 24)
    : (bytes[off] << 24) | (bytes[off + 1] << 16) | (bytes[off + 2] << 8) | bytes[off + 3]

  // Magic 0x002A.
  const magic = u16(base + 2)
  if (magic !== 0x002a) return []
  const ifdOffset = u32(base + 4)
  const ifdStart = base + ifdOffset
  if (ifdStart + 2 > bytes.length) return []
  const count = u16(ifdStart)
  const out: ExifTag[] = []
  for (let i = 0; i < count; i += 1) {
    const entry = ifdStart + 2 + i * 12
    if (entry + 12 > bytes.length) break
    const tagId = u16(entry)
    const type = u16(entry + 2)
    const valCount = u32(entry + 4)
    const valOffset = u32(entry + 8)
    const name = KNOWN_TAGS[tagId]
    if (!name) continue
    let value: string = ''
    if (type === 2) {
      // ASCII string. Value at offset OR inline if ≤ 4 bytes.
      const len = valCount
      let stringStart: number
      if (len <= 4) {
        stringStart = entry + 8
      } else {
        stringStart = base + valOffset
      }
      if (stringStart + len <= bytes.length) {
        let s = ''
        for (let j = 0; j < len - 1; j += 1) {
          const c = bytes[stringStart + j]
          if (c >= 0x20 && c < 0x7f) s += String.fromCharCode(c)
        }
        value = s
      }
    } else if (type === 3) {
      // SHORT (uint16)
      value = String(valOffset & 0xffff)
    } else if (type === 4) {
      // LONG
      value = String(valOffset)
    } else if (type === 5) {
      // RATIONAL (8 bytes : num/denom). Read at offset.
      if (base + valOffset + 8 <= bytes.length) {
        const num = u32(base + valOffset)
        const den = u32(base + valOffset + 4)
        value = den !== 0 ? `${num}/${den} = ${(num / den).toFixed(3)}` : `${num}`
      }
    } else {
      value = `(type=${type}, val=${valOffset})`
    }
    if (value) out.push({ tag: name, value })
  }
  return out
}
