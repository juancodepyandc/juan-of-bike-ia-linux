// ---------------------------------------------------------------------------
// Brand profile dictionary
// Extracted from codeIntent.ts during WS1 modularisation.
// ---------------------------------------------------------------------------

import type { BrandProfile } from './codeIntentTypes.ts'
import { BRAND_DICTIONARY_A } from './codeIntentBrandProfilesA.ts'
import { BRAND_DICTIONARY_B } from './codeIntentBrandProfilesB.ts'

export type BrandDictionaryEntry = {
  token: RegExp
  canonical: string
  domain: string
  profile: BrandProfile
}

export const BRAND_DICTIONARY: BrandDictionaryEntry[] = [
  ...BRAND_DICTIONARY_A,
  ...BRAND_DICTIONARY_B,
]
