import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { BAC_STI2D_SIN_ID, buildBacSTI2DSINCategory } from './bacSti2dSinSeed'

export type ItemKind = 'cours' | 'exo' | 'fiche' | 'quiz'

export type AcademyItemVerification = {
  status: 'verified' | 'general' | 'uncertain' | 'contradicted'
  citedSources?: number[]
  reasoning?: string
}

export type AcademyItem = {
  id: string
  kind: ItemKind
  title: string
  content: string
  subCategoryId: string
  createdAt: number
  createdByAI: boolean
  /** Fact-check verdict from academicContentVerification (best-effort). */
  verification?: AcademyItemVerification
}

export type SubCategory = {
  id: string
  name: string
  emoji?: string
}

export type Category = {
  id: string
  name: string
  description: string
  emoji: string
  tone: string
  subCategories: SubCategory[]
  items: AcademyItem[]
  createdByAI: boolean
  createdAt: number
}

const now = () => Date.now()
const uid = (prefix = 'id') => `${prefix}-${Math.random().toString(36).slice(2, 9)}${now().toString(36)}`

const mkSub = (name: string, emoji?: string): SubCategory => ({ id: uid('sub'), name, emoji })

const DEFAULT_CATEGORIES: Category[] = [
  {
    id: 'cat-cyber',
    name: 'Cybersécurité',
    description: 'Traque, protège, analyse. Chaque faille se comble par la discipline.',
    emoji: '🛡',
    tone: '#e63412',
    subCategories: [
      mkSub('Forensic', '🔍'),
      mkSub('OSINT', '🕸'),
      mkSub('Reverse Engineering', '⚙'),
      mkSub('Web Security', '🕷'),
      mkSub('Simulation PC / Tracking', '🖥'),
      mkSub('Cryptographie', '🔐'),
      mkSub('Stéganographie', '👁'),
      mkSub('Pentest', '⚔'),
    ],
    items: [],
    createdByAI: false,
    createdAt: now(),
  },
  {
    id: 'cat-maths',
    name: 'Mathématiques',
    description: 'De l\'arithmétique aux fractales, la langue universelle de l\'IA.',
    emoji: '∑',
    tone: '#5b3fc9',
    subCategories: [
      mkSub('Algèbre', 'x'),
      mkSub('Analyse', '∫'),
      mkSub('Géométrie', '△'),
      mkSub('Probabilités', '🎲'),
      mkSub('Statistiques', '📊'),
      mkSub('Logique', '¬'),
      mkSub('Arithmétique', 'π'),
    ],
    items: [],
    createdByAI: false,
    createdAt: now(),
  },
  {
    id: 'cat-physique',
    name: 'Physique',
    description: 'Lois de la matière et de l\'énergie, du quark au cosmos.',
    emoji: '⚛',
    tone: '#1f4ec9',
    subCategories: [
      mkSub('Mécanique', '⚙'),
      mkSub('Électricité', '⚡'),
      mkSub('Optique', '🔦'),
      mkSub('Thermodynamique', '🔥'),
      mkSub('Relativité', '🌀'),
      mkSub('Quantique', '⚛'),
    ],
    items: [],
    createdByAI: false,
    createdAt: now(),
  },
  {
    id: 'cat-chimie',
    name: 'Chimie',
    description: 'Réactions, molécules, équilibres — la danse des atomes.',
    emoji: '⚗',
    tone: '#2f8f5a',
    subCategories: [
      mkSub('Organique', '🧬'),
      mkSub('Inorganique', '⚗'),
      mkSub('Analytique', '🔬'),
      mkSub('Physique-chimie', '⚡'),
      mkSub('Biochimie', '🧪'),
    ],
    items: [],
    createdByAI: false,
    createdAt: now(),
  },
  {
    id: 'cat-info',
    name: 'Informatique',
    description: 'Du langage machine aux architectures d\'agents IA.',
    emoji: '⌘',
    tone: '#00add8',
    subCategories: [
      mkSub('Langages', '💻'),
      mkSub('Algorithmique', '🧩'),
      mkSub('Architecture', '🏛'),
      mkSub('Réseaux', '🌐'),
      mkSub('Bases de données', '🗃'),
      mkSub('Intelligence artificielle', '🤖'),
      mkSub('Systèmes', '🐧'),
    ],
    items: [],
    createdByAI: false,
    createdAt: now(),
  },
  {
    id: 'cat-sin',
    name: 'SIN / Électronique',
    description: 'Circuits, capteurs, embarqué — de la théorie au PCB.',
    emoji: '⚡',
    tone: '#f78324',
    subCategories: [
      mkSub('Circuits logiques', '⚙'),
      mkSub('Microcontrôleurs', '🔌'),
      mkSub('Traitement du signal', '📡'),
      mkSub('Automatique', '🤖'),
    ],
    items: [],
    createdByAI: false,
    createdAt: now(),
  },
  {
    id: 'cat-philo',
    name: 'Philosophie',
    description: 'Questionner l\'évident, penser contre soi, chercher la mesure.',
    emoji: '☯',
    tone: '#7a4b22',
    subCategories: [
      mkSub('Éthique', '⚖'),
      mkSub('Métaphysique', '🌌'),
      mkSub('Logique', '⊕'),
      mkSub('Politique', '🏛'),
      mkSub('Esthétique', '🎭'),
      mkSub('Épistémologie', '🔍'),
    ],
    items: [],
    createdByAI: false,
    createdAt: now(),
  },
  {
    id: 'cat-astro',
    name: 'Astronomie',
    description: 'Cartes du ciel, orbites, spectres — tu n\'es jamais vraiment perdu.',
    emoji: '✨',
    tone: '#c586c0',
    subCategories: [
      mkSub('Système solaire', '🪐'),
      mkSub('Étoiles', '⭐'),
      mkSub('Galaxies', '🌌'),
      mkSub('Cosmologie', '🌠'),
      mkSub('Instruments', '🔭'),
    ],
    items: [],
    createdByAI: false,
    createdAt: now(),
  },
  {
    id: 'cat-langues',
    name: 'Langues',
    description: 'Parle, traduis, ouvre-toi au monde.',
    emoji: '🗣',
    tone: '#d6a012',
    subCategories: [
      mkSub('Anglais', '🇬🇧'),
      mkSub('Espagnol', '🇪🇸'),
      mkSub('Italien', '🇮🇹'),
      mkSub('Allemand', '🇩🇪'),
      mkSub('Japonais', '🇯🇵'),
    ],
    items: [],
    createdByAI: false,
    createdAt: now(),
  },
]

interface AcademyState {
  categories: Category[]
  addCategory: (cat: Omit<Category, 'id' | 'createdAt'>) => string
  removeCategory: (id: string) => void
  addSubCategory: (catId: string, sub: SubCategory) => void
  addItem: (catId: string, item: Omit<AcademyItem, 'id' | 'createdAt'>) => string
  removeItem: (catId: string, itemId: string) => void
  updateItem: (catId: string, itemId: string, patch: Partial<AcademyItem>) => void
  reset: () => void
}

function buildInitialCategories(): Category[] {
  return [buildBacSTI2DSINCategory(), ...DEFAULT_CATEGORIES]
}

export const useAcademyStore = create<AcademyState>()(
  persist(
    (set) => ({
      categories: buildInitialCategories(),
      addCategory: (cat) => {
        const id = uid('cat')
        set((s) => ({ categories: [...s.categories, { ...cat, id, createdAt: now() }] }))
        return id
      },
      removeCategory: (id) => set((s) => ({ categories: s.categories.filter((c) => c.id !== id) })),
      addSubCategory: (catId, sub) =>
        set((s) => ({
          categories: s.categories.map((c) => c.id === catId ? { ...c, subCategories: [...c.subCategories, sub] } : c),
        })),
      addItem: (catId, item) => {
        const id = uid('it')
        set((s) => ({
          categories: s.categories.map((c) =>
            c.id === catId
              ? { ...c, items: [{ ...item, id, createdAt: now() }, ...c.items] }
              : c,
          ),
        }))
        return id
      },
      removeItem: (catId, itemId) =>
        set((s) => ({
          categories: s.categories.map((c) =>
            c.id === catId ? { ...c, items: c.items.filter((i) => i.id !== itemId) } : c,
          ),
        })),
      updateItem: (catId, itemId, patch) =>
        set((s) => ({
          categories: s.categories.map((c) =>
            c.id === catId
              ? { ...c, items: c.items.map((i) => i.id === itemId ? { ...i, ...patch } : i) }
              : c,
          ),
        })),
      reset: () => set({ categories: buildInitialCategories() }),
    }),
    {
      name: 'aurora-academy-store',
      version: 2,
      migrate: (persisted: any, version: number) => {
        const state = persisted as AcademyState | undefined
        if (!state) return { categories: buildInitialCategories() } as any
        if (version < 2 || !state.categories?.some((c) => c.id === BAC_STI2D_SIN_ID)) {
          // Inject BAC STI2D SIN category if missing
          return { ...state, categories: [buildBacSTI2DSINCategory(), ...(state.categories || [])] } as any
        }
        return state as any
      },
    },
  ),
)
