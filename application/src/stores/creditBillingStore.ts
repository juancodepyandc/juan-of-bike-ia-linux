import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type BillingMode = 'infinite' | 'subscription' | 'juan_of_bike_coins'

export type SubscriptionTierId = 'starter_local' | 'pro_dual_vm' | 'ultimate_commercial'

export type BillingCycle = 'monthly' | 'annual'

export type PaymentMethodId =
  | 'cb_stripe'
  | 'paypal'
  | 'apple_pay'
  | 'google_pay'
  | 'klarna_3x'
  | 'sepa_instant'
  | 'crypto_web3'

export interface PaymentMethodSpec {
  id: PaymentMethodId
  labelFr: string
  shortBadgeFr: string
  providerName: string
  processingFeeLabelFr: string
  bonusCoinsPercent: number
  installmentAvailableFr?: string
  securityProtocolFr: string
}

export const PAYMENT_METHODS_CATALOG: PaymentMethodSpec[] = [
  {
    id: 'cb_stripe',
    labelFr: 'Carte Bancaire (CB / Visa / Mastercard / Amex)',
    shortBadgeFr: 'CB · Visa · Mastercard',
    providerName: 'Stripe 3DS2',
    processingFeeLabelFr: '0 € de frais',
    bonusCoinsPercent: 0,
    installmentAvailableFr: 'Paiement comptant ou 3× sans frais dès 15 €',
    securityProtocolFr: 'Chiffrement PCI-DSS Niveau 1 & 3D Secure 2.2',
  },
  {
    id: 'paypal',
    labelFr: 'PayPal & PayPal 4× Sans Frais',
    shortBadgeFr: 'PayPal · 4× Sans Frais',
    providerName: 'PayPal Express',
    processingFeeLabelFr: '0 € de frais · Protection Acheteur',
    bonusCoinsPercent: 0,
    installmentAvailableFr: 'Éligible au 4× sans frais PayPal dès 30 €',
    securityProtocolFr: 'Authentification OAuth2 PayPal sans partage de carte',
  },
  {
    id: 'apple_pay',
    labelFr: 'Apple Pay (Face ID / Touch ID 1-Clic)',
    shortBadgeFr: 'Apple Pay',
    providerName: 'Apple Pay Token',
    processingFeeLabelFr: 'Validation instantanée 0 €',
    bonusCoinsPercent: 0,
    securityProtocolFr: 'Secure Enclave & Jeton cryptographique à usage unique',
  },
  {
    id: 'google_pay',
    labelFr: 'Google Pay (Validation Biométrique)',
    shortBadgeFr: 'Google Pay',
    providerName: 'Google Pay',
    processingFeeLabelFr: 'Validation instantanée 0 €',
    bonusCoinsPercent: 0,
    securityProtocolFr: 'Tokenisation virtuelle Google Wallet',
  },
  {
    id: 'klarna_3x',
    labelFr: 'Klarna / Revolut Pay (3× Sans Frais ou J+30)',
    shortBadgeFr: 'Klarna · Revolut 3×',
    providerName: 'Klarna & Revolut',
    processingFeeLabelFr: '0 % TAEG · Aucun intérêt',
    bonusCoinsPercent: 0,
    installmentAvailableFr: 'Payez en 3 mensualités égales ou dans 30 jours',
    securityProtocolFr: 'Validation bancaire Open-Banking PSD2',
  },
  {
    id: 'sepa_instant',
    labelFr: 'Virement SEPA Instantané / Prélèvement Pro',
    shortBadgeFr: 'SEPA Instant · Facture TVA',
    providerName: 'SEPA Instant Euro',
    processingFeeLabelFr: '0 € de frais · Facture Pro PDF',
    bonusCoinsPercent: 5,
    securityProtocolFr: 'IBAN Européen vérifié + Facture comptable automatique',
  },
  {
    id: 'crypto_web3',
    labelFr: 'Crypto & Stablecoins (USDC / USDT / BTC / ETH / SOL)',
    shortBadgeFr: 'Crypto · +10 % JB Bonus',
    providerName: 'Solana / Polygon / Lightning',
    processingFeeLabelFr: 'Frais réseau < 0,01 € + 10 % de pièces JB offertes',
    bonusCoinsPercent: 10,
    securityProtocolFr: 'Règlement on-chain non-custodial instantané',
  },
]

export interface SubscriptionPlanSpec {
  id: SubscriptionTierId
  titleFr: string
  taglineFr: string
  monthlyPriceEur: number
  annualMonthlyEquivalentEur: number
  firstMonthTrialEur: number
  includedMonthlyJbCoins: number
  videoDualVmIncluded: boolean
  badgeFr?: string
  highlightsFr: string[]
}

export const SUBSCRIPTION_PLANS_CATALOG: SubscriptionPlanSpec[] = [
  {
    id: 'starter_local',
    titleFr: 'Pass Découverte Local+',
    taglineFr: 'Idéal pour démarrer avec les 12 modules locaux Renforcés',
    monthlyPriceEur: 4.99,
    annualMonthlyEquivalentEur: 3.49,
    firstMonthTrialEur: 0.99,
    includedMonthlyJbCoins: 350,
    videoDualVmIncluded: false,
    badgeFr: '1er mois à 0,99 €',
    highlightsFr: [
      '12 modules locaux illimités (Modèle Renforcé actif par défaut)',
      '350 Pièces Juan of Bike (JB) offertes chaque mois (utilisables sur la Vidéo VM)',
      '3D Volumétrique 360°, Cristal Optique PBR & Studio 11 Ancres d’Animation',
      'Anti-Hallucination & Juges Premiers Principes SymPy/Z3 inclus',
    ],
  },
  {
    id: 'pro_dual_vm',
    titleFr: 'Pass Pro Dual-VM & Vidéo',
    taglineFr: 'Le tarif le plus compétitif du marché pour la Vidéo Cloud Dual-GPU & 3D',
    monthlyPriceEur: 12.99,
    annualMonthlyEquivalentEur: 8.99,
    firstMonthTrialEur: 2.99,
    includedMonthlyJbCoins: 1800,
    videoDualVmIncluded: true,
    badgeFr: '⭐ BEST-SELLER · -31 % en Annuel',
    highlightsFr: [
      'Accès ILLIMITÉ au Module Vidéo sur les 2 VMs Cloud Dual-GPU (Wan2.2 5B + HY-Motion)',
      '1 800 Pièces Juan of Bike (JB) créditées chaque mois (~72 vidéos ou 120 modèles 3D)',
      'Les 13 modules Renforcés à pleine vitesse (3D TRELLIS.2, Image 16K PBR, Code, Cyber)',
      '3× moins cher que les abonnements cloud concurrents à 35–45 €/mois',
    ],
  },
  {
    id: 'ultimate_commercial',
    titleFr: 'Pass Studio Ultimate RTX 6000',
    taglineFr: 'Puissance maximale dédiée, file prioritaire & droits commerciaux complets',
    monthlyPriceEur: 29.99,
    annualMonthlyEquivalentEur: 19.99,
    firstMonthTrialEur: 9.99,
    includedMonthlyJbCoins: 6500,
    videoDualVmIncluded: true,
    badgeFr: '💎 PUISSANCE MAX RTX 6000',
    highlightsFr: [
      'File GPU Prioritaire dédiée RTX 6000 / Blackwell + Dual-VM Cloud sans attente',
      '6 500 Pièces Juan of Bike (JB) / mois + report des pièces non utilisées sans expiration',
      'Licence Commerciale 100 % Libre de Droits sur toutes vos créations 3D, Vidéo, Code & Audio',
      'Accès API & Multi-postes Cowork / Business Lab inclus',
    ],
  },
]

export interface JbCoinPackSpec {
  id: string
  titleFr: string
  baseCoins: number
  bonusCoins: number
  totalCoins: number
  priceEur: number
  unitCostLabelFr: string
  equivalentRunsLabelFr: string
  popularBadgeFr?: string
}

export const JB_COIN_PACKS_CATALOG: JbCoinPackSpec[] = [
  {
    id: 'pack_mini_250',
    titleFr: 'Pack Découverte',
    baseCoins: 250,
    bonusCoins: 25,
    totalCoins: 275,
    priceEur: 1.99,
    unitCostLabelFr: '0,0072 € / JB',
    equivalentRunsLabelFr: '≈ 11 vidéos Dual-VM ou 18 modèles 3D',
  },
  {
    id: 'pack_createur_950',
    titleFr: 'Pack Créateur',
    baseCoins: 800,
    bonusCoins: 200,
    totalCoins: 1000,
    priceEur: 4.99,
    unitCostLabelFr: '0,0049 € / JB (+25 % offerts)',
    equivalentRunsLabelFr: '≈ 40 vidéos Dual-VM ou 66 modèles 3D',
    popularBadgeFr: '+200 JB OFFERTS',
  },
  {
    id: 'pack_pro_2800',
    titleFr: 'Pack Pro Populaire',
    baseCoins: 2200,
    bonusCoins: 800,
    totalCoins: 3000,
    priceEur: 9.99,
    unitCostLabelFr: '0,0033 € / JB (+36 % offerts)',
    equivalentRunsLabelFr: '≈ 120 vidéos Dual-VM ou 200 modèles 3D',
    popularBadgeFr: '🔥 MEILLEURE OFFRE · 0,08 € / Vidéo',
  },
  {
    id: 'pack_studio_10000',
    titleFr: 'Pack Méga Studio',
    baseCoins: 7000,
    bonusCoins: 3500,
    totalCoins: 10500,
    priceEur: 24.99,
    unitCostLabelFr: '0,0023 € / JB (+50 % offerts)',
    equivalentRunsLabelFr: '≈ 420 vidéos Dual-VM ou 700 modèles 3D',
    popularBadgeFr: '💎 +3 500 JB GRATUITS',
  },
]

export interface BillingTransactionReceipt {
  id: string
  createdAtIso: string
  itemLabelFr: string
  paymentMethodId: PaymentMethodId
  paymentMethodLabelFr: string
  amountEur: number
  coinsCredited: number
  promoCodeApplied?: string
  status: 'paid_verified'
}

export interface ModuleBestModelArchitecture {
  moduleId:
    | '3d'
    | 'image'
    | 'video'
    | 'animation'
    | 'code'
    | 'cyber'
    | 'conversation'
    | 'cowork'
    | 'academy'
    | 'audio'
    | 'business'
    | 'drawing'
    | 'simulator'
  moduleLabelFr: string
  defaultVariant: 'renforce'
  bestModelStack: string
  reinforcedAdapterPath: string
  computeExecutionTarget: 'local_and_vm' | 'vm_cloud_exclusive'
  computeTargetLabelFr: string
  vramRequirementGb: number
  speedRatingLabelFr: string
  jbCoinCostPerRun: number
  commercialScalabilityNotesFr: string
}

export const BEST_MODELS_ARCHITECTURE_CATALOG: ModuleBestModelArchitecture[] = [
  {
    moduleId: 'video',
    moduleLabelFr: 'Vidéo Cinématographique & Lip-Sync (Exclusif Dual-VM)',
    defaultVariant: 'renforce',
    bestModelStack: 'Wan-AI/Wan2.2-TI2V-5B + Tencent/HY-Motion-1.0 + MuseTalk + Kokoro-82M (LoRA Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/video/adapter.safetensors',
    computeExecutionTarget: 'vm_cloud_exclusive',
    computeTargetLabelFr: 'Exclusif Dual-VM Cloud (2× GPU 30 Go VRAM)',
    vramRequirementGb: 28,
    speedRatingLabelFr: 'Ultra-Haute Puissance VM (~45s / clip 720p-1080p)',
    jbCoinCostPerRun: 25,
    commercialScalabilityNotesFr: 'Exécuté à 100 % sur les VMs distantes pour préserver la VRAM locale ; facturable en pièces Juan of Bike ou Abonnement Pro.',
  },
  {
    moduleId: '3d',
    moduleLabelFr: '3D Volumétrique, Cristal Optique PBR 16K & CAO Mécatronique',
    defaultVariant: 'renforce',
    bestModelStack: 'microsoft/TRELLIS.2-4B + FLUX.2-dev Reference + Manifold64 + UniversalAnatomicalRig (Flow-DPO Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/3d/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'Hybride RTX 5070 Ti (16 Go) + Dual-VM Cloud',
    vramRequirementGb: 16,
    speedRatingLabelFr: 'Haute Précision & Vitesse Accélérée (~35-65s)',
    jbCoinCostPerRun: 15,
    commercialScalabilityNotesFr: 'Points d’ancrage d’animation auto/manuels par paires de couleurs + verre/cristal optique KHR_materials_transmission.',
  },
  {
    moduleId: 'animation',
    moduleLabelFr: 'Animation Squelettique 3D & Rigging Zéro-Déformation',
    defaultVariant: 'renforce',
    bestModelStack: 'Blender 5.1 Geodesic Medial Rig + HY-Motion-1.0 + SE(3) Pivot-Locked Keyframes (Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/animation/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'Hybride Local + Dual-VM',
    vramRequirementGb: 8,
    speedRatingLabelFr: 'Temps Réel / Haute Cadence (< 4s par rig)',
    jbCoinCostPerRun: 8,
    commercialScalabilityNotesFr: 'Détection médiale 11 articulations sans retournement jacobien et placement interactif par paires de couleurs.',
  },
  {
    moduleId: 'image',
    moduleLabelFr: 'Image Studio FLUX.2-dev & Super-Résolution 16K PBR',
    defaultVariant: 'renforce',
    bestModelStack: 'FLUX.2-dev Q4_K_M + Mistral-3-Small FP8 + ReferenceLatent + Qwen3-VL:8B (DPO Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/image/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'Local RTX 5070 Ti + Burst VM Cloud',
    vramRequirementGb: 14,
    speedRatingLabelFr: 'Rapide Haute Fidélité (~12-18s)',
    jbCoinCostPerRun: 10,
    commercialScalabilityNotesFr: 'Anti-hallucination ontologique objet vs personnage et upscaling 8K/16K.',
  },
  {
    moduleId: 'code',
    moduleLabelFr: 'Architecture Logicielle, Motion Design UI & Preuve Z3',
    defaultVariant: 'renforce',
    bestModelStack: 'Qwen3-Coder / DeepSeek-R1 Distill + Sandbox 22 Langages + Vérificateur SymPy/Z3 (Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/code/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'Local + Accélération Cloud',
    vramRequirementGb: 10,
    speedRatingLabelFr: 'Ultra-Rapide (~95 tok/s)',
    jbCoinCostPerRun: 5,
    commercialScalabilityNotesFr: 'Zéro TODO/stub, compilation automatique tsc/cargo/py_compile.',
  },
  {
    moduleId: 'cyber',
    moduleLabelFr: 'Cybersécurité Symbolique 0-Day & Patch en Boucle Fermée',
    defaultVariant: 'renforce',
    bestModelStack: 'Moteur AST/CFG SMT Z3 + ClosedLoopPatchEngine + 9 Labs Cyber (Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/cyber/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'Local Isolé + VM Banc de Falsification',
    vramRequirementGb: 8,
    speedRatingLabelFr: 'Preuve Formelle UNSAT (< 3s)',
    jbCoinCostPerRun: 8,
    commercialScalabilityNotesFr: 'Audit de sécurité automatisé avec preuve formelle de non-exploitabilité après patch.',
  },
  {
    moduleId: 'conversation',
    moduleLabelFr: 'Conversation Multimodale, Vision & Recherche Web Temps Réel',
    defaultVariant: 'renforce',
    bestModelStack: 'Qwen3-VL:8B + Pipeline Cognitif 6 Étapes + Fact-Checker Web (Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/conversation/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'Local Basse Latence + Cloud Burst',
    vramRequirementGb: 8,
    speedRatingLabelFr: 'Streaming Instantané (< 250ms TTFT)',
    jbCoinCostPerRun: 2,
    commercialScalabilityNotesFr: 'Mémoire épisodique ChromaDB et vérification anti-hallucination.',
  },
  {
    moduleId: 'cowork',
    moduleLabelFr: 'Cowork Multi-Agents, Extension Chrome MV3 & Extraction Doc',
    defaultVariant: 'renforce',
    bestModelStack: 'CoworkPlanner DAG + CoworkSafety + Extracteur PDF/DOCX/CSV (Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/cowork/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'Local + Workspace Navigateur :3034',
    vramRequirementGb: 8,
    speedRatingLabelFr: 'Exécution Parallèle Multi-Étapes',
    jbCoinCostPerRun: 6,
    commercialScalabilityNotesFr: 'Automatisation bureautique et navigateur sécurisée avec audit transactionnel.',
  },
  {
    moduleId: 'academy',
    moduleLabelFr: 'Academy, Oracle Formel SymPy/Z3 & Laboratoires Interactifs',
    defaultVariant: 'renforce',
    bestModelStack: 'ScientificOracle (SymPy + Z3) + Tuteur Adaptatif Bac/Supérieur (Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/academy/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'Local + Calcul Formel Vérifié',
    vramRequirementGb: 8,
    speedRatingLabelFr: 'Vérification Mathématique Exacte (< 1.5s)',
    jbCoinCostPerRun: 3,
    commercialScalabilityNotesFr: 'Zéro erreur algébrique grâce à la preuve formelle systématique.',
  },
  {
    moduleId: 'audio',
    moduleLabelFr: 'Voix Duplex Live, Kokoro TTS 82M & Whisper Large-v3 STT',
    defaultVariant: 'renforce',
    bestModelStack: 'hexgrad/Kokoro-82M + faster-whisper-large-v3 + Rhubarb Visèmes A-X (Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/audio/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'Local Temps Réel Duplex',
    vramRequirementGb: 6,
    speedRatingLabelFr: 'Synthèse & Transcription Temps Réel (< 180ms)',
    jbCoinCostPerRun: 3,
    commercialScalabilityNotesFr: 'Phonétique française haute fidélité et synchronisation labiale temps réel.',
  },
  {
    moduleId: 'business',
    moduleLabelFr: 'Business CEO, Quant Walk-Forward & IndependentRiskManager',
    defaultVariant: 'renforce',
    bestModelStack: '9 Agents Économiques + Monte-Carlo Queues Épaisses + Audit SHA-256 (Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/business/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'Local + Flux Marché Temps Réel (BCE/Binance/Yahoo)',
    vramRequirementGb: 8,
    speedRatingLabelFr: 'Simulation Quantitative Rapide (< 2s)',
    jbCoinCostPerRun: 6,
    commercialScalabilityNotesFr: 'Garde-fou non-LLM IndependentRiskManager (réserve >= 25 %, ruine <= 2 %).',
  },
  {
    moduleId: 'drawing',
    moduleLabelFr: 'Dessin Vectoriel/WebGL, Sketch-to-Image & Character Forge',
    defaultVariant: 'renforce',
    bestModelStack: 'ControlNet Sketch Renderer + Qwen3-VL Stroke Interpreter + FLUX.2-dev (Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/drawing/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'Toile 120 FPS + Rendu GPU Local/VM',
    vramRequirementGb: 12,
    speedRatingLabelFr: 'Latence Stylet 0ms / Rendu ~10s',
    jbCoinCostPerRun: 8,
    commercialScalabilityNotesFr: 'Passerelle directe Character Forge vers 3D et Vidéo.',
  },
  {
    moduleId: 'simulator',
    moduleLabelFr: 'Simulateur Physique, Fluides SPH, Chimie & Électronique',
    defaultVariant: 'renforce',
    bestModelStack: 'Solveur Symplectique Hamiltonien + Navier-Stokes SPH + Stœchiométrie (Renforcé)',
    reinforcedAdapterPath: 'modele/renforce/simulator/adapter.safetensors',
    computeExecutionTarget: 'local_and_vm',
    computeTargetLabelFr: 'WebGL2 / WebGPU 60 FPS + Validation SymPy',
    vramRequirementGb: 6,
    speedRatingLabelFr: 'Simulation 60 FPS Temps Réel',
    jbCoinCostPerRun: 4,
    commercialScalabilityNotesFr: 'Conservation exacte de l’énergie et export de scènes reproductibles.',
  },
]

export interface CreditBillingState {
  billingMode: BillingMode
  infiniteCreditsActive: boolean
  juanOfBikeCoins: number
  subscriptionTier: SubscriptionTierId
  billingCycle: BillingCycle
  selectedPaymentMethod: PaymentMethodId
  promoCode: string
  transactions: BillingTransactionReceipt[]
  videoVmOnlyEnforced: boolean
  setBillingMode: (mode: BillingMode) => void
  setSubscriptionTier: (tier: SubscriptionTierId) => void
  setBillingCycle: (cycle: BillingCycle) => void
  setSelectedPaymentMethod: (method: PaymentMethodId) => void
  setPromoCode: (code: string) => void
  addJuanOfBikeCoins: (amount: number) => void
  processCheckoutPurchase: (params: {
    itemType: 'subscription' | 'coin_pack'
    tierId?: SubscriptionTierId
    packId?: string
    paymentMethodId?: PaymentMethodId
    promoCode?: string
  }) => BillingTransactionReceipt
  consumeCoinsForModule: (moduleId: ModuleBestModelArchitecture['moduleId']) => {
    allowed: boolean
    cost: number
    remainingCoins: number | 'INFINI'
    reasonFr: string
  }
  syncWithBackend: () => Promise<void>
}

export const useCreditBillingStore = create<CreditBillingState>()(
  persist(
    (set, get) => ({
      billingMode: 'infinite',
      infiniteCreditsActive: true,
      juanOfBikeCoins: 2500,
      subscriptionTier: 'pro_dual_vm',
      billingCycle: 'annual',
      selectedPaymentMethod: 'cb_stripe',
      promoCode: 'BIENVENUE30',
      transactions: [],
      videoVmOnlyEnforced: true,

      setBillingMode: (mode) => {
        const isInf = mode === 'infinite'
        set({ billingMode: mode, infiniteCreditsActive: isInf })
        fetch('/api/billing/credits', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ billing_mode: mode, infinite_credits_active: isInf }),
        }).catch(() => {})
      },

      setSubscriptionTier: (tier) => {
        set({ subscriptionTier: tier })
        fetch('/api/billing/credits', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ subscription_tier: tier }),
        }).catch(() => {})
      },

      setBillingCycle: (cycle) => set({ billingCycle: cycle }),

      setSelectedPaymentMethod: (method) => set({ selectedPaymentMethod: method }),

      setPromoCode: (code) => set({ promoCode: code.toUpperCase().trim() }),

      addJuanOfBikeCoins: (amount) => {
        const next = Math.max(0, get().juanOfBikeCoins + amount)
        set({ juanOfBikeCoins: next })
        fetch('/api/billing/credits', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ juan_of_bike_coins: next }),
        }).catch(() => {})
      },

      processCheckoutPurchase: ({ itemType, tierId, packId, paymentMethodId, promoCode }) => {
        const state = get()
        const methodId = paymentMethodId || state.selectedPaymentMethod
        const methodSpec =
          PAYMENT_METHODS_CATALOG.find((m) => m.id === methodId) || PAYMENT_METHODS_CATALOG[0]
        const cleanPromo = (promoCode ?? state.promoCode ?? '').toUpperCase().trim()

        let basePrice = 9.99
        let baseCoins = 0
        let itemLabelFr = ''

        if (itemType === 'subscription') {
          const plan =
            SUBSCRIPTION_PLANS_CATALOG.find((p) => p.id === (tierId || state.subscriptionTier)) ||
            SUBSCRIPTION_PLANS_CATALOG[1]
          basePrice =
            state.billingCycle === 'annual' ? plan.annualMonthlyEquivalentEur : plan.monthlyPriceEur
          baseCoins = plan.includedMonthlyJbCoins
          itemLabelFr = `${plan.titleFr} (${state.billingCycle === 'annual' ? 'Tarif Annuel -31%' : 'Mensuel'})`
        } else {
          const pack =
            JB_COIN_PACKS_CATALOG.find((p) => p.id === packId) || JB_COIN_PACKS_CATALOG[2]
          basePrice = pack.priceEur
          baseCoins = pack.totalCoins
          itemLabelFr = `${pack.titleFr} (${pack.totalCoins.toLocaleString('fr-FR')} JB)`
        }

        let discountMultiplier = 1.0
        let promoBonusCoins = 0
        if (cleanPromo === 'BIENVENUE30' || cleanPromo === 'AURORA30') {
          discountMultiplier = 0.7
        } else if (cleanPromo === 'LAUNCH50') {
          discountMultiplier = 0.5
        } else if (cleanPromo === 'JUANVIP') {
          discountMultiplier = 0.8
          promoBonusCoins = 500
        }

        const methodBonus = Math.round((baseCoins * methodSpec.bonusCoinsPercent) / 100)
        const totalCredited = baseCoins + methodBonus + promoBonusCoins
        const finalEur = Number((basePrice * discountMultiplier).toFixed(2))
        const nextCoins = state.juanOfBikeCoins + totalCredited

        const receipt: BillingTransactionReceipt = {
          id: `JB-${Date.now().toString(36).toUpperCase()}`,
          createdAtIso: new Date().toISOString(),
          itemLabelFr,
          paymentMethodId: methodSpec.id,
          paymentMethodLabelFr: methodSpec.shortBadgeFr,
          amountEur: finalEur,
          coinsCredited: totalCredited,
          promoCodeApplied: cleanPromo || undefined,
          status: 'paid_verified',
        }

        set({
          juanOfBikeCoins: nextCoins,
          selectedPaymentMethod: methodSpec.id,
          subscriptionTier:
            itemType === 'subscription' && tierId ? tierId : state.subscriptionTier,
          transactions: [receipt, ...state.transactions].slice(0, 15),
        })

        fetch('/api/billing/credits', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            juan_of_bike_coins: nextCoins,
            subscription_tier:
              itemType === 'subscription' && tierId ? tierId : state.subscriptionTier,
            last_receipt: receipt,
          }),
        }).catch(() => {})

        return receipt
      },

      consumeCoinsForModule: (moduleId) => {
        const state = get()
        const arch = BEST_MODELS_ARCHITECTURE_CATALOG.find((m) => m.moduleId === moduleId)
        const cost = arch?.jbCoinCostPerRun ?? 5

        if (state.billingMode === 'infinite' || state.infiniteCreditsActive) {
          return {
            allowed: true,
            cost: 0,
            remainingCoins: 'INFINI',
            reasonFr: 'Mode Crédits Infinis actif (0 pièce débitée · Meilleur modèle Renforcé Dual-VM activé)',
          }
        }

        if (state.billingMode === 'subscription') {
          if (moduleId === 'video' && state.subscriptionTier === 'starter_local') {
            return {
              allowed: false,
              cost,
              remainingCoins: state.juanOfBikeCoins,
              reasonFr: 'Le module Vidéo s’exécute exclusivement sur les VMs Cloud Dual-GPU : passez à l’abonnement Pro Dual-VM ou utilisez vos pièces Juan of Bike.',
            }
          }
          return {
            allowed: true,
            cost: 0,
            remainingCoins: state.juanOfBikeCoins,
            reasonFr: `Inclus dans votre abonnement (${state.subscriptionTier})`,
          }
        }

        // Mode Pièces Juan of Bike (JB Coins)
        if (state.juanOfBikeCoins < cost) {
          return {
            allowed: false,
            cost,
            remainingCoins: state.juanOfBikeCoins,
            reasonFr: `Solde insuffisant (${state.juanOfBikeCoins} JB disponibles, ${cost} JB requis pour ${arch?.moduleLabelFr || moduleId}). Rechargez vos pièces Juan of Bike ou réactivez le mode Crédits Infinis dans Paramètres.`,
          }
        }
        const nextCoins = state.juanOfBikeCoins - cost
        set({ juanOfBikeCoins: nextCoins })
        fetch('/api/billing/credits', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ juan_of_bike_coins: nextCoins }),
        }).catch(() => {})
        return {
          allowed: true,
          cost,
          remainingCoins: nextCoins,
          reasonFr: `${cost} pièces Juan of Bike (JB) utilisées pour exécuter le meilleur modèle Renforcé sur VM.`,
        }
      },

      syncWithBackend: async () => {
        try {
          const resp = await fetch('/api/billing/credits')
          if (!resp.ok) return
          const data = await resp.json()
          if (data && typeof data === 'object') {
            set({
              billingMode: (data.billing_mode as BillingMode) || 'infinite',
              infiniteCreditsActive: data.billing_mode ? data.billing_mode === 'infinite' : true,
              juanOfBikeCoins: typeof data.juan_of_bike_coins === 'number' ? data.juan_of_bike_coins : get().juanOfBikeCoins,
            })
          }
        } catch {
          // Keep local state if offline
        }
      },
    }),
    {
      name: 'aurora-credit-billing-store-v1',
    },
  ),
)
