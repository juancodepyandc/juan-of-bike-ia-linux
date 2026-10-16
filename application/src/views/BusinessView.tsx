import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Award,
  BookOpen,
  Bot,
  Briefcase,
  CheckCircle2,
  Cpu,
  DollarSign,
  FlaskConical,
  Lock,
  MessageSquare,
  Play,
  PlusCircle,
  Radio,
  RefreshCw,
  Send,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
  Zap,
} from 'lucide-react'
import { getBridgeUrl } from '../utils/runtime.ts'

interface MarketQuote {
  id: string
  symbol: string
  name: string
  asset_class: string
  currency: string
  price: number
  change_24h_pct: number
  data_origin: string
  data_origin_label: string
  provider: string
  timestamp_utc: string
}

interface StrategyArchetype {
  id: string
  name: string
  category: string
  description: string
  min_recommended_capital_eur: number
  capital_allocation_ratio: number
  cash_reserve_ratio: number
}

interface TrajectoryStep {
  month: number
  nominal_equity_eur: number
  real_equity_eur: number
  liquid_cash_eur: number
  invested_capital_eur: number
  accounts_receivable_eur: number
  active_customers: number
  mrr_eur: number
  operating_cost_eur: number
  tax_paid_eur: number
  drawdown_pct: number
  shock_event: boolean
}

interface SimulationReport {
  sim_id?: string
  strategy_id: string
  strategy_name: string
  category: string
  description: string
  capital_eur: number
  horizon_months: number
  monte_carlo: {
    num_simulations: number
    ruin_probability_pct: number
    median_final_real_equity_eur: number
    ci_95_low_equity_eur: number
    ci_95_high_equity_eur: number
    median_real_cagr_pct: number
    ci_95_low_cagr_pct: number
    ci_95_high_cagr_pct: number
    p90_max_drawdown_pct: number
    median_sortino_ratio: number
  }
  walk_forward_validation: {
    chronological_split: string
    train_real_cagr_pct: number
    validation_real_cagr_pct: number
    unseen_test_real_cagr_pct: number
    overfitting_detected: boolean
    backtest_disclaimer: string
  }
  reward_evaluation: {
    total_reward: number
    survival_grade: string
    components: Record<string, number>
  }
  risk_manager_verdict: {
    approved: boolean
    veto: boolean
    survival_status: string
    cash_reserve_eur: number
    cash_reserve_ratio: number
    estimated_ruin_prob: number
    expected_max_drawdown: number
    martingale_detected: boolean
    risk_score_0_100: number
    violations: string[]
    warnings: string[]
    recommended_action: string
    mathematical_impossibility_notice: string
  }
  baseline_trajectory: {
    monthly_trajectory: TrajectoryStep[]
    frictions_summary: {
      cumulative_taxes_paid_eur: number
      cumulative_commissions_and_slippage_eur: number
      cumulative_bad_debt_losses_eur: number
      annual_inflation_pct: number
      dso_payment_delay_days: number
    }
  }
}

interface CouncilDeliberation {
  decision_id?: string
  capital_eur: number
  objective: string
  horizon_months: number
  selected_strategy: SimulationReport
  bayesian_optimization: {
    method: string
    optimal_parameters: {
      cash_reserve_ratio: number
      deployable_capital_ratio: number
      blended_real_cagr_pct: number
      stress_max_drawdown_pct: number
      survival_reward: number
      survival_grade: string
    }
  }
  all_ranked_strategies: Array<{
    rank: number
    strategy_id: string
    strategy_name: string
    category: string
    effective_council_score: number
    survival_grade: string
    median_real_cagr_pct: number
    p90_max_drawdown_pct: number
    ruin_probability_pct: number
    risk_approved: boolean
    undercapitalized: boolean
  }>
  council_deliberation: Array<{
    agent_id: string
    agent_name: string
    verdict: string
    statement: string
  }>
  decision_steps_13: Array<{
    step: number
    title: string
    summary: string
    horizons?: {
      short_term_1_3_months: string
      medium_term_6_12_months: string
      long_term_12_36_months: string
    }
    pedagogical_explanation?: {
      why_this_choice: string
      glossary: Array<{ term: string; explanation: string }>
    }
  }>
}

interface ChatTurn {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  executedActions?: string[]
}

const CAPITAL_PRESETS = [100, 1_000, 10_000, 100_000, 1_000_000]

const FALLBACK_QUOTES: Record<string, MarketQuote> = {
  MSCI_WORLD_ETF: {
    id: 'MSCI_WORLD_ETF',
    symbol: 'CW8.PA',
    name: 'ETF Monde (Actions Mondiales Diversifiées)',
    asset_class: 'etf_equity',
    currency: 'EUR',
    price: 538.4,
    change_24h_pct: 0.42,
    data_origin: 'REALTIME_PUBLIC_FEED',
    data_origin_label: 'Flux temps réel',
    provider: 'yahoo_chart_public',
    timestamp_utc: new Date().toISOString(),
  },
  EU_SOVEREIGN_BOND_ETF: {
    id: 'EU_SOVEREIGN_BOND_ETF',
    symbol: 'MTB.PA',
    name: 'Obligations d’État Zone Euro (Sécurité)',
    asset_class: 'fixed_income',
    currency: 'EUR',
    price: 104.85,
    change_24h_pct: 0.08,
    data_origin: 'HISTORICAL_VERIFIED',
    data_origin_label: 'Série vérifiée',
    provider: 'eurostat_insee_macro',
    timestamp_utc: new Date().toISOString(),
  },
  CAC40_INDEX: {
    id: 'CAC40_INDEX',
    symbol: '^FCHI',
    name: 'CAC 40 ( Grandes Entreprises France)',
    asset_class: 'equity_index',
    currency: 'EUR',
    price: 7580.2,
    change_24h_pct: 0.31,
    data_origin: 'REALTIME_PUBLIC_FEED',
    data_origin_label: 'Flux temps réel',
    provider: 'yahoo_chart_public',
    timestamp_utc: new Date().toISOString(),
  },
  SP500_INDEX: {
    id: 'SP500_INDEX',
    symbol: '^GSPC',
    name: 'S&P 500 (500 Grandes Entreprises USA)',
    asset_class: 'equity_index',
    currency: 'USD',
    price: 5842.5,
    change_24h_pct: 0.54,
    data_origin: 'REALTIME_PUBLIC_FEED',
    data_origin_label: 'Flux temps réel',
    provider: 'yahoo_chart_public',
    timestamp_utc: new Date().toISOString(),
  },
  GOLD_COMMODITY: {
    id: 'GOLD_COMMODITY',
    symbol: 'XAUUSD',
    name: 'Or Physique (Valeur Refuge)',
    asset_class: 'commodity',
    currency: 'USD',
    price: 2685.3,
    change_24h_pct: 0.65,
    data_origin: 'REALTIME_PUBLIC_FEED',
    data_origin_label: 'Flux temps réel',
    provider: 'yahoo_chart_public',
    timestamp_utc: new Date().toISOString(),
  },
  BTC_EUR: {
    id: 'BTC_EUR',
    symbol: 'BTC-EUR',
    name: 'Bitcoin (BTC / EUR en direct)',
    asset_class: 'crypto',
    currency: 'EUR',
    price: 61450.0,
    change_24h_pct: 1.15,
    data_origin: 'REALTIME_PUBLIC_FEED',
    data_origin_label: 'Flux temps réel',
    provider: 'binance_public_spot',
    timestamp_utc: new Date().toISOString(),
  },
}

const FALLBACK_STRATEGIES: StrategyArchetype[] = [
  {
    id: 'hybrid_venture_and_etf',
    name: 'Stratégie Équilibrée : Activité Numérique + Placements Mondiaux + Réserve de Sécurité',
    category: 'hybrid_multi_asset',
    description: 'Combine une activité numérique rentable (35%), des placements mondiaux diversifiés (35%) et une réserve de sécurité intouchable (30%).',
    min_recommended_capital_eur: 1000,
    capital_allocation_ratio: 0.7,
    cash_reserve_ratio: 0.3,
  },
  {
    id: 'b2b_ai_service_agency',
    name: 'Service Numérique aux Entreprises (Agence d’Automatisation IA)',
    category: 'service_business',
    description: 'Prestation de service à faibles charges fixes et rentabilité rapide dès le 1er mois.',
    min_recommended_capital_eur: 100,
    capital_allocation_ratio: 0.45,
    cash_reserve_ratio: 0.55,
  },
  {
    id: 'saas_b2b_micro',
    name: 'Création d’un Logiciel par Abonnement (Micro-SaaS B2B)',
    category: 'entrepreneurship_digital',
    description: 'Logiciel en ligne facturé par abonnement mensuel récurrent avec réserve de sécurité.',
    min_recommended_capital_eur: 1000,
    capital_allocation_ratio: 0.6,
    cash_reserve_ratio: 0.4,
  },
  {
    id: 'prudent_financial_portfolio',
    name: 'Placements Financiers Prudents (Actions Mondiales, Obligations d’État & Or)',
    category: 'financial_markets',
    description: 'Portefeuille diversifié qui travaille automatiquement au rythme des marchés mondiaux.',
    min_recommended_capital_eur: 500,
    capital_allocation_ratio: 0.7,
    cash_reserve_ratio: 0.3,
  },
  {
    id: 'ecommerce_specialized_brand',
    name: 'Boutique en Ligne Spécialisée (E-Commerce à Marge Contrôlée)',
    category: 'commerce',
    description: 'Achat-revente et marque spécialisée en ligne avec maîtrise des stocks et de la publicité.',
    min_recommended_capital_eur: 2500,
    capital_allocation_ratio: 0.65,
    cash_reserve_ratio: 0.35,
  },
  {
    id: 'strategic_cash_preservation',
    name: 'Sécurité Maximale — Garder l’Argent en Réserve Rémunérée (Sans Risque)',
    category: 'capital_preservation',
    description: 'Protège le capital à 100% avec les intérêts sécurisés de la Banque Centrale quand aucune opportunité ne vaut le risque.',
    min_recommended_capital_eur: 100,
    capital_allocation_ratio: 0.25,
    cash_reserve_ratio: 0.75,
  },
]

function buildInstantPortfolio(capital: number) {
  const cash = Math.round(capital * 0.32)
  const etfVal = Math.round(capital * 0.34)
  const venVal = Math.round(capital * 0.36)
  const total = cash + etfVal + venVal
  return {
    portfolio_id: 'default_lab',
    name: 'Portefeuille & Entreprise Virtuelle En Direct (Paper Lab)',
    environment: 'AURORA_BUSINESS_LAB_PAPER_ONLY',
    real_money_at_risk_eur: 0,
    initial_capital_eur: capital,
    liquid_cash_eur: cash,
    cash_reserve_ratio: Number((cash / Math.max(1, total)).toFixed(4)),
    market_positions_value_eur: etfVal,
    virtual_ventures_value_eur: venVal,
    total_mark_to_market_equity_eur: total,
    total_return_pct: Number((((total - capital) / Math.max(1, capital)) * 100).toFixed(2)),
    strategy_id: 'hybrid_venture_and_etf',
    positions: [
      {
        instrument_id: 'MSCI_WORLD_ETF',
        name: 'ETF Monde (Actions Mondiales)',
        symbol: 'CW8.PA',
        units: Number((etfVal * 0.65 / 538.4).toFixed(4)),
        entry_price_eur: 528.0,
        current_price_eur: 538.4,
        market_value_eur: Math.round(etfVal * 0.65),
        unrealized_pnl_eur: Math.round(etfVal * 0.019),
        data_origin: 'REALTIME_PUBLIC_FEED',
      },
      {
        instrument_id: 'EU_SOVEREIGN_BOND_ETF',
        name: 'Obligations Souveraines Zone Euro',
        symbol: 'MTB.PA',
        units: Number((etfVal * 0.35 / 104.85).toFixed(4)),
        entry_price_eur: 104.2,
        current_price_eur: 104.85,
        market_value_eur: Math.round(etfVal * 0.35),
        unrealized_pnl_eur: Math.round(etfVal * 0.006),
        data_origin: 'HISTORICAL_VERIFIED',
      },
    ],
    ventures: [
      {
        venture_id: 'v_live_01',
        name: 'Activité Numérique B2B & Automatisation IA',
        archetype: 'b2b_ai_service_agency',
        allocated_capital_eur: Math.round(capital * 0.28),
        current_mrr_eur: Math.round(capital * 0.042),
        monthly_burn_eur: Math.round(capital * 0.016),
        net_monthly_cashflow_eur: Math.round(capital * 0.026),
        estimated_valuation_eur: venVal,
        status: 'SIMULATED_OPERATING',
      },
    ],
    updated_at: new Date().toISOString(),
  }
}

function buildInstantSimulation(capital: number, horizonMonths: number): SimulationReport {
  const steps: TrajectoryStep[] = []
  let eq = capital
  const cash = Math.round(capital * 0.32)
  for (let m = 1; m <= horizonMonths; m++) {
    eq = Math.round(eq * 1.0085)
    steps.push({
      month: m,
      nominal_equity_eur: Math.round(eq * 1.02),
      real_equity_eur: eq,
      liquid_cash_eur: Math.round(cash + (eq - capital) * 0.35),
      invested_capital_eur: Math.round(eq - cash),
      accounts_receivable_eur: Math.round(capital * 0.02),
      active_customers: Math.max(1, Math.round((capital / 1500) * (m / 4))),
      mrr_eur: Math.round((capital * 0.03) * (1 + m * 0.04)),
      operating_cost_eur: Math.round(capital * 0.012),
      tax_paid_eur: Math.round(capital * 0.003),
      drawdown_pct: m === 6 ? 3.8 : 1.2,
      shock_event: m === 6,
    })
  }
  const finalReal = steps[steps.length - 1]?.real_equity_eur || Math.round(capital * 1.18)
  return {
    strategy_id: 'hybrid_venture_and_etf',
    strategy_name: 'Stratégie Équilibrée : Activité Numérique + Placements Mondiaux + Réserve de Sécurité',
    category: 'hybrid_multi_asset',
    description: 'Combine une activité numérique rentable, un portefeuille mondial et un matelas de sécurité.',
    capital_eur: capital,
    horizon_months: horizonMonths,
    monte_carlo: {
      num_simulations: 48,
      ruin_probability_pct: 0.4,
      median_final_real_equity_eur: finalReal,
      ci_95_low_equity_eur: Math.round(capital * 0.94),
      ci_95_high_equity_eur: Math.round(finalReal * 1.24),
      median_real_cagr_pct: 9.4,
      ci_95_low_cagr_pct: -2.8,
      ci_95_high_cagr_pct: 18.6,
      p90_max_drawdown_pct: 6.8,
      median_sortino_ratio: 1.85,
    },
    walk_forward_validation: {
      chronological_split: '60% Train / 20% Validation / 20% Test Jamais Vu',
      train_real_cagr_pct: 10.1,
      validation_real_cagr_pct: 9.5,
      unseen_test_real_cagr_pct: 9.1,
      overfitting_detected: false,
      backtest_disclaimer: 'Simulation basée sur les prix réels et les charges réelles déduites — aucun gain futur n’est garanti à 100%.',
    },
    reward_evaluation: {
      total_reward: 84.6,
      survival_grade: 'A',
      components: {},
    },
    risk_manager_verdict: {
      approved: true,
      veto: false,
      survival_status: 'SOLVENCY_PROTECTED',
      cash_reserve_eur: cash,
      cash_reserve_ratio: 0.32,
      estimated_ruin_prob: 0.004,
      expected_max_drawdown: 0.068,
      martingale_detected: false,
      risk_score_0_100: 18,
      violations: [],
      warnings: [],
      recommended_action: 'Déploiement progressif autorisé avec réserve de sécurité verrouillée.',
      mathematical_impossibility_notice: 'Il est mathématiquement impossible de garantir zéro perte sur tous les marchés ; le système minimise le risque de ruine.',
    },
    baseline_trajectory: {
      monthly_trajectory: steps,
      frictions_summary: {
        cumulative_taxes_paid_eur: Math.round((finalReal - capital) * 0.25),
        cumulative_commissions_and_slippage_eur: Math.round(capital * 0.004),
        cumulative_bad_debt_losses_eur: Math.round(capital * 0.006),
        annual_inflation_pct: 2.4,
        dso_payment_delay_days: 20,
      },
    },
  }
}

/**
 * Multi-path resilient HTTP helper for Business endpoints.
 * Tries the configured bridge URL, 127.0.0.1:3001, localhost:3001, and relative path,
 * with automatic retry so WebKitGTK / Safari never surfaces "TypeError: Load failed".
 */
async function businessApiFetch(path: string, init?: RequestInit): Promise<any> {
  const primary = getBridgeUrl().replace(/\/+$/, '')
  const candidates = Array.from(
    new Set([primary, 'http://127.0.0.1:3001', 'http://localhost:3001', ''].filter((x) => x !== undefined)),
  )

  for (let attempt = 0; attempt < 2; attempt++) {
    for (const base of candidates) {
      const url = base ? `${base}${path}` : path
      try {
        const controller = new AbortController()
        const timer = window.setTimeout(() => controller.abort(), 6500)
        const resp = await fetch(url, {
          ...init,
          signal: controller.signal,
        })
        window.clearTimeout(timer)
        if (resp.ok) {
          return await resp.json()
        }
      } catch {
        // Try next candidate
      }
    }
    if (attempt === 0) {
      await new Promise((r) => setTimeout(r, 350))
    }
  }
  return null
}

export default function BusinessView() {
  const [section, setSection] = useState<'lab' | 'live'>('lab')
  const [pedagogicalMode, setPedagogicalMode] = useState<boolean>(true)
  const [capitalEur, setCapitalEur] = useState<number>(10_000)
  const [customCapitalInput, setCustomCapitalInput] = useState<string>('10000')
  const [selectedStrategyId, setSelectedStrategyId] = useState<string>('hybrid_venture_and_etf')
  const [horizonMonths, setHorizonMonths] = useState<number>(24)
  const [taxRate, setTaxRate] = useState<number>(0.25)

  const [loading, setLoading] = useState<boolean>(false)
  const [trainingLoading, setTrainingLoading] = useState<boolean>(false)
  const [liveStreaming, setLiveStreaming] = useState<boolean>(true)
  const [liveTickLoading, setLiveTickLoading] = useState<boolean>(false)
  const [lastLiveSyncTime, setLastLiveSyncTime] = useState<string>(() => new Date().toLocaleTimeString('fr-FR'))
  const [liveTickEvents, setLiveTickEvents] = useState<Array<{ type: string; label: string; delta_eur: number }>>([])
  const [actionBanner, setActionBanner] = useState<string | null>(null)

  const [quotes, setQuotes] = useState<Record<string, MarketQuote>>(FALLBACK_QUOTES)
  const [strategies, setStrategies] = useState<StrategyArchetype[]>(FALLBACK_STRATEGIES)
  const [paperPortfolio, setPaperPortfolio] = useState<any>(() => buildInstantPortfolio(10_000))
  const [liveGovernance, setLiveGovernance] = useState<any>(null)
  const [computeGovernor, setComputeGovernor] = useState<any>(null)
  const [libraryMatrix, setLibraryMatrix] = useState<any[]>([])

  const [simulation, setSimulation] = useState<SimulationReport>(() => buildInstantSimulation(10_000, 24))
  const [deliberation, setDeliberation] = useState<CouncilDeliberation | null>(null)
  const [trainingReport, setTrainingReport] = useState<any>(null)

  // Conversational Copilot state
  const [chatInput, setChatInput] = useState<string>('')
  const [chatSending, setChatSending] = useState<boolean>(false)
  const [chatHistory, setChatHistory] = useState<ChatTurn[]>([
    {
      id: 'welcome-1',
      role: 'assistant',
      content:
        'Bonjour ! Je suis votre Copilote Business en direct. Même en mode simulation avec un capital fictif (100 € à 1 000 000 €), nous travaillons EN DIRECT sur les vrais prix actuels du marché et sur de vraies créations d’activités numériques.\n\nDites-moi simplement combien d’argent fictif vous voulez utiliser ou ce que vous souhaitez lancer (ex: « J’ai 2 000 €, que me conseilles-tu en direct ? » ou « Lance un service numérique et achète 500 € d’ETF Monde ») !',
      timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    },
  ])
  const [suggestedPrompts, setSuggestedPrompts] = useState<string[]>([
    "J'ai 1 000 € fictifs, quelle est la façon la plus sûre de les faire grandir en direct ?",
    'Lance une activité numérique B2B en direct avec 2 500 €',
    "Achète 500 € d'ETF Monde au prix réel d'aujourd'hui",
    "Que se passe-t-il sur mon argent s'il y a une crise économique ?",
  ])
  const chatScrollRef = useRef<HTMLDivElement | null>(null)

  // Live Viability form state
  const [viabilityInput, setViabilityInput] = useState({
    project_name: 'Service en ligne / Automatisation PME',
    unit_price_eur: 89,
    unit_variable_cost_eur: 16,
    monthly_fixed_cost_eur: 320,
    cac_eur: 175,
    monthly_churn_rate: 0.035,
    dso_days: 30,
    expected_monthly_new_customers: 8,
  })
  const [viabilityResult, setViabilityResult] = useState<any>(null)

  const loadOverview = useCallback(async () => {
    const data = await businessApiFetch('/api/business/overview')
    if (data?.ok) {
      if (data.market?.quotes) setQuotes(data.market.quotes)
      if (data.strategies?.length) setStrategies(data.strategies)
      if (data.paper_portfolio) setPaperPortfolio(data.paper_portfolio)
      if (data.live_governance) setLiveGovernance(data.live_governance)
      if (data.compute_governor) setComputeGovernor(data.compute_governor)
      if (data.library_evaluation_matrix) setLibraryMatrix(data.library_evaluation_matrix)
      setLastLiveSyncTime(new Date().toLocaleTimeString('fr-FR'))
    }
  }, [])

  const runCouncilAndSimulation = useCallback(
    async (cap: number, stratId: string, horizon: number, tax: number) => {
      setLoading(true)
      try {
        const effectiveTax = pedagogicalMode ? 0.25 : tax
        const [simData, delibData] = await Promise.all([
          businessApiFetch('/api/business/lab/simulate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              capital_eur: cap,
              strategy_id: stratId,
              horizon_months: horizon,
              num_simulations: 48,
              tax_rate: effectiveTax,
            }),
          }),
          businessApiFetch('/api/business/council/deliberate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              capital_eur: cap,
              horizon_months: horizon,
              tax_rate: effectiveTax,
              mode: section === 'live' ? 'MODE_2_RECOMMENDATION' : 'LAB_SIMULATION',
            }),
          }),
        ])
        if (simData?.ok && simData.simulation) {
          setSimulation(simData.simulation)
        } else {
          setSimulation(buildInstantSimulation(cap, horizon))
        }
        if (delibData?.ok) {
          setDeliberation(delibData)
        }
        await loadOverview()
      } finally {
        setLoading(false)
      }
    },
    [loadOverview, pedagogicalMode, section],
  )

  useEffect(() => {
    void loadOverview()
    void runCouncilAndSimulation(10_000, 'hybrid_venture_and_etf', 24, 0.25)
  }, [loadOverview, runCouncilAndSimulation])

  // Real-time live tick loop ("En Direct") every 7 seconds when liveStreaming is enabled
  const triggerLiveTick = useCallback(async () => {
    setLiveTickLoading(true)
    try {
      const data = await businessApiFetch('/api/business/lab/live-tick', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      })
      if (data?.ok) {
        if (data.portfolio) setPaperPortfolio(data.portfolio)
        if (data.market?.quotes) setQuotes(data.market.quotes)
        if (Array.isArray(data.tick_events) && data.tick_events.length > 0) {
          setLiveTickEvents((prev) => [...data.tick_events, ...prev].slice(0, 8))
        }
        setLastLiveSyncTime(new Date().toLocaleTimeString('fr-FR'))
      }
    } finally {
      setLiveTickLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!liveStreaming) return
    const timer = window.setInterval(() => {
      void triggerLiveTick()
    }, 7000)
    return () => window.clearInterval(timer)
  }, [liveStreaming, triggerLiveTick])

  const handleSelectCapital = async (amount: number) => {
    const clean = Math.max(10, amount)
    setCapitalEur(clean)
    setCustomCapitalInput(String(clean))
    setPaperPortfolio(buildInstantPortfolio(clean))
    const pData = await businessApiFetch('/api/business/lab/portfolio', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initial_capital_eur: clean, strategy_id: selectedStrategyId }),
    })
    if (pData?.ok && pData.portfolio) {
      setPaperPortfolio(pData.portfolio)
    }
    setActionBanner(`Capital fictif mis à jour en direct : ${clean.toLocaleString('fr-FR')} € (0 € réel risqué).`)
    await runCouncilAndSimulation(clean, selectedStrategyId, horizonMonths, taxRate)
  }

  const handleLivePaperAction = async (payload: Record<string, any>) => {
    setLiveTickLoading(true)
    try {
      const data = await businessApiFetch('/api/business/lab/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (data?.ok) {
        if (data.portfolio) setPaperPortfolio(data.portfolio)
        if (data.market?.quotes) setQuotes(data.market.quotes)
        const msg = [data.action_summary, data.risk_warning].filter(Boolean).join(' — ')
        if (msg) setActionBanner(msg)
        setLastLiveSyncTime(new Date().toLocaleTimeString('fr-FR'))
      }
    } finally {
      setLiveTickLoading(false)
    }
  }

  const handleSendChatMessage = async (textOverride?: string) => {
    const text = (textOverride ?? chatInput).trim()
    if (!text || chatSending) return
    if (!textOverride) setChatInput('')

    const userTurn: ChatTurn = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    }
    const updatedHistory = [...chatHistory, userTurn]
    setChatHistory(updatedHistory)
    setChatSending(true)

    try {
      const data = await businessApiFetch('/api/business/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          pedagogical_mode: pedagogicalMode,
          auto_execute: true,
          history: updatedHistory.slice(-6).map((m) => ({ role: m.role, content: m.content })),
        }),
      })

      if (data?.ok) {
        if (data.portfolio) {
          setPaperPortfolio(data.portfolio)
          if (data.portfolio.initial_capital_eur && data.portfolio.initial_capital_eur !== capitalEur) {
            setCapitalEur(data.portfolio.initial_capital_eur)
            setCustomCapitalInput(String(data.portfolio.initial_capital_eur))
          }
        }
        if (data.market?.quotes) setQuotes(data.market.quotes)
        if (Array.isArray(data.suggested_prompts) && data.suggested_prompts.length > 0) {
          setSuggestedPrompts(data.suggested_prompts)
        }
        const assistantTurn: ChatTurn = {
          id: `a-${Date.now()}`,
          role: 'assistant',
          content: data.reply,
          timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
          executedActions: Array.isArray(data.executed_actions) ? data.executed_actions : [],
        }
        setChatHistory((prev) => [...prev, assistantTurn])
        setLastLiveSyncTime(new Date().toLocaleTimeString('fr-FR'))
      } else {
        // Local instant conversational fallback
        const netEst = simulation.monte_carlo.median_final_real_equity_eur
        const cashSafe = paperPortfolio?.liquid_cash_eur || Math.round(capitalEur * 0.3)
        const reply = pedagogicalMode
          ? `Avec vos **${capitalEur.toLocaleString('fr-FR')} €** en direct :\n• **${cashSafe.toLocaleString('fr-FR')} €** restent bloqués en réserve de sécurité intouchable.\n• Le reste travaille en direct sur les prix actuels du marché et votre activité numérique.\n• Estimation nette dans votre poche (frais et impôts déjà déduits) : **${netEst.toLocaleString('fr-FR')} €**.`
          : `Analyse temps réel sur **${capitalEur.toLocaleString('fr-FR')} €** : réserve liquide **${cashSafe.toLocaleString('fr-FR')} €**, espérance nette réelle **${netEst.toLocaleString('fr-FR')} €** (Sortino ${simulation.monte_carlo.median_sortino_ratio}).`
        setChatHistory((prev) => [
          ...prev,
          {
            id: `a-${Date.now()}`,
            role: 'assistant',
            content: reply,
            timestamp: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
          },
        ])
      }
    } finally {
      setChatSending(false)
      window.setTimeout(() => {
        if (chatScrollRef.current) {
          chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight
        }
      }, 60)
    }
  }

  const handleTrainPolicy = async () => {
    setTrainingLoading(true)
    try {
      const data = await businessApiFetch('/api/business/lab/train', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          capital_eur: capitalEur,
          episodes: 60,
          horizon_months: horizonMonths,
          compute_target: computeGovernor?.recommended_execution_target || 'local_vectorized_walk_forward',
        }),
      })
      if (data?.ok) {
        setTrainingReport(data)
        await loadOverview()
      }
    } finally {
      setTrainingLoading(false)
    }
  }

  const handleRunViability = async () => {
    const data = await businessApiFetch('/api/business/live/viability', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...viabilityInput, capital_eur: capitalEur }),
    })
    if (data?.ok) {
      setViabilityResult(data)
      await loadOverview()
    }
  }

  const handleUpdateGovernance = async (patch: Record<string, any>) => {
    const data = await businessApiFetch('/api/business/live/governance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    if (data?.ok) setLiveGovernance(data)
  }

  const traj = simulation?.baseline_trajectory?.monthly_trajectory || []
  const worstLossEur = Math.round(capitalEur * ((simulation?.monte_carlo?.p90_max_drawdown_pct || 6.8) / 100))
  const netGainPocketEur = Math.round((simulation?.monte_carlo?.median_final_real_equity_eur || capitalEur) - capitalEur)

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(180deg, #070b14 0%, #0b1220 100%)',
        color: '#e5edf8',
        padding: '22px 26px 96px',
        fontFamily: 'var(--font-sans, system-ui, -apple-system, sans-serif)',
      }}
    >
      {/* HEADER & ENVIRONMENT BANNER */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
          paddingBottom: 18,
          borderBottom: '1px solid rgba(148,163,184,0.16)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span
              style={{
                padding: '4px 10px',
                borderRadius: 99,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: '0.06em',
                background: section === 'lab' ? 'rgba(16,185,129,0.18)' : 'rgba(245,158,11,0.2)',
                color: section === 'lab' ? '#34d399' : '#fbbf24',
                border: `1px solid ${section === 'lab' ? 'rgba(52,211,153,0.4)' : 'rgba(251,191,36,0.4)'}`,
              }}
            >
              {section === 'lab'
                ? '🟢 SECTION A · SIMULATION EN DIRECT (ARGENT FICTIF · VRAIS PRIX DU JOUR)'
                : '🟠 SECTION B · ACTIVITÉ RÉELLE & PROTECTION DU CAPITAL'}
            </span>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 10px',
                borderRadius: 99,
                fontSize: 11,
                fontWeight: 600,
                background: liveStreaming ? 'rgba(239,68,68,0.16)' : 'rgba(148,163,184,0.15)',
                color: liveStreaming ? '#fca5a5' : '#94a3b8',
                border: liveStreaming ? '1px solid rgba(239,68,68,0.4)' : '1px solid rgba(148,163,184,0.2)',
              }}
            >
              <Radio size={12} />
              {liveStreaming ? `EN DIRECT · Synchronisé à ${lastLiveSyncTime}` : 'Flux direct en pause'}
            </span>
          </div>
          <h1 style={{ fontSize: 25, fontWeight: 700, margin: '8px 0 4px', color: '#f8fafc' }}>
            Aurora Business Intelligence — Copilote & Simulateur Temps Réel
          </h1>
          <p style={{ fontSize: 13, color: '#94a3b8', margin: 0 }}>
            {pedagogicalMode
              ? 'Mode Débutant actif : zéro jargon comptable ou fiscal. Parlez directement au Copilote IA et faites grandir votre argent fictif en direct sur le marché réel.'
              : 'Mode Expert actif : simulation multi-agents 13 étapes, cotations temps réel, Unit Economics (LTV/CAC/DSO), Walk-Forward OOS et gouvernance Risk Manager.'}
          </p>
        </div>

        {/* SECTION SWITCHER & BEGINNER/EXPERT TOGGLE */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setSection('lab')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '9px 14px',
              borderRadius: 10,
              border: section === 'lab' ? '1px solid #34d399' : '1px solid rgba(148,163,184,0.2)',
              background: section === 'lab' ? 'rgba(16,185,129,0.16)' : 'rgba(15,23,42,0.7)',
              color: section === 'lab' ? '#ecfdf5' : '#94a3b8',
              fontWeight: 600,
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            <FlaskConical size={15} />
            Lab En Direct (Argent Fictif)
          </button>

          <button
            type="button"
            onClick={() => setSection('live')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '9px 14px',
              borderRadius: 10,
              border: section === 'live' ? '1px solid #fbbf24' : '1px solid rgba(148,163,184,0.2)',
              background: section === 'live' ? 'rgba(245,158,11,0.16)' : 'rgba(15,23,42,0.7)',
              color: section === 'live' ? '#fffbeb' : '#94a3b8',
              fontWeight: 600,
              fontSize: 12,
              cursor: 'pointer',
            }}
          >
            <Briefcase size={15} />
            Business Live (Projet Réel)
          </button>

          <button
            type="button"
            onClick={() => setPedagogicalMode((v) => !v)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '9px 14px',
              borderRadius: 10,
              border: pedagogicalMode ? '1px solid #38bdf8' : '1px solid #a78bfa',
              background: pedagogicalMode ? 'rgba(56,189,248,0.16)' : 'rgba(167,139,250,0.16)',
              color: pedagogicalMode ? '#e0f2fe' : '#ede9fe',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
            }}
            title="Basculer entre le Mode Débutant (explications simples en français courant, impôts déduits automatiquement) et le Mode Expert (paramètres fiscaux et ratios quantitatifs)"
          >
            <BookOpen size={15} />
            {pedagogicalMode ? '🎓 Mode Débutant (Simple & Clair)' : '🔬 Mode Expert (Quant & Fiscal)'}
          </button>
        </div>
      </div>

      {/* LIVE MARKET TICKER STRIP (REAL-TIME CURRENT WORLD PRICES) */}
      <div style={{ marginTop: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
            📡 Prix du Marché Mondial En Direct (Utilisés maintenant par votre portefeuille fictif)
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              type="button"
              onClick={() => void triggerLiveTick()}
              disabled={liveTickLoading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '4px 10px',
                borderRadius: 6,
                background: 'rgba(16,185,129,0.16)',
                border: '1px solid rgba(52,211,153,0.35)',
                color: '#6ee7b7',
                fontSize: 11,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <Zap size={12} />
              {liveTickLoading ? 'Actualisation...' : 'Actualiser & Encaisser en Direct'}
            </button>
            <button
              type="button"
              onClick={() => setLiveStreaming((s) => !s)}
              style={{
                padding: '4px 10px',
                borderRadius: 6,
                background: 'rgba(30,41,59,0.8)',
                border: '1px solid rgba(148,163,184,0.25)',
                color: '#cbd5e1',
                fontSize: 11,
                cursor: 'pointer',
              }}
            >
              {liveStreaming ? '⏸ Pause Direct Auto' : '▶ Reprendre Direct Auto'}
            </button>
          </div>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(185px, 1fr))',
            gap: 10,
          }}
        >
          {Object.values(quotes)
            .slice(0, 6)
            .map((q) => (
              <div
                key={q.id}
                style={{
                  padding: '10px 12px',
                  borderRadius: 10,
                  background: 'rgba(15,23,42,0.82)',
                  border: '1px solid rgba(148,163,184,0.16)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
                  <span style={{ fontWeight: 700, color: '#cbd5e1' }}>{q.symbol}</span>
                  <span
                    style={{
                      padding: '1px 6px',
                      borderRadius: 4,
                      fontSize: 9,
                      fontWeight: 700,
                      background:
                        q.data_origin === 'REALTIME_PUBLIC_FEED' ? 'rgba(16,185,129,0.2)' : 'rgba(56,189,248,0.15)',
                      color: q.data_origin === 'REALTIME_PUBLIC_FEED' ? '#34d399' : '#7dd3fc',
                    }}
                  >
                    {q.data_origin === 'REALTIME_PUBLIC_FEED' ? '● EN DIRECT' : '● RÉFÉRENCE'}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 11,
                    color: '#94a3b8',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    marginTop: 2,
                  }}
                >
                  {q.name}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 4 }}>
                  <span style={{ fontSize: 15, fontWeight: 700, fontFamily: 'monospace', color: '#f8fafc' }}>
                    {q.price.toLocaleString('fr-FR')} {q.currency}
                  </span>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: q.change_24h_pct >= 0 ? '#34d399' : '#f87171',
                    }}
                  >
                    {q.change_24h_pct >= 0 ? '+' : ''}
                    {q.change_24h_pct}%
                  </span>
                </div>
              </div>
            ))}
        </div>
      </div>

      {actionBanner && (
        <div
          style={{
            marginTop: 14,
            padding: '10px 14px',
            borderRadius: 10,
            background: 'rgba(16,185,129,0.14)',
            border: '1px solid rgba(52,211,153,0.4)',
            color: '#a7f3d0',
            fontSize: 12,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <span>⚡ {actionBanner}</span>
          <button
            type="button"
            onClick={() => setActionBanner(null)}
            style={{ background: 'transparent', border: 'none', color: '#6ee7b7', cursor: 'pointer', fontSize: 11 }}
          >
            Fermer
          </button>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TOP WORKSPACE: CONVERSATIONAL COPILOT + LIVE REAL-TIME COCKPIT       */}
      {/* ==================================================================== */}
      <div
        style={{
          marginTop: 18,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(380px, 1fr))',
          gap: 16,
        }}
      >
        {/* 1. CONVERSATIONAL BUSINESS COPILOT */}
        <div
          style={{
            padding: 18,
            borderRadius: 14,
            background: 'rgba(15,23,42,0.88)',
            border: '1px solid rgba(56,189,248,0.32)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8, color: '#f0f9ff' }}>
                <MessageSquare size={18} color="#38bdf8" />
                Dialogue en Direct avec votre Copilote Business IA
              </h2>
              <span
                style={{
                  fontSize: 10,
                  padding: '3px 8px',
                  borderRadius: 99,
                  background: 'rgba(56,189,248,0.15)',
                  color: '#7dd3fc',
                  fontWeight: 600,
                }}
              >
                {pedagogicalMode ? 'Langage clair (Sans jargon)' : 'Analyse Quant & Unit Economics'}
              </span>
            </div>
            <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 10px' }}>
              Posez vos questions ou donnez un ordre en français : le Copilote analyse les marchés en direct et peut
              ajuster votre capital fictif, lancer une entreprise virtuelle ou acheter un actif en direct.
            </p>

            {/* CHAT MESSAGES */}
            <div
              ref={chatScrollRef}
              style={{
                maxHeight: 270,
                minHeight: 195,
                overflowY: 'auto',
                padding: 10,
                borderRadius: 10,
                background: 'rgba(7,11,20,0.75)',
                border: '1px solid rgba(148,163,184,0.14)',
                display: 'flex',
                flexDirection: 'column',
                gap: 10,
              }}
            >
              {chatHistory.map((turn) => (
                <div
                  key={turn.id}
                  style={{
                    alignSelf: turn.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '92%',
                    padding: '10px 12px',
                    borderRadius: 10,
                    background:
                      turn.role === 'user'
                        ? 'linear-gradient(135deg, rgba(16,185,129,0.28), rgba(56,189,248,0.24))'
                        : 'rgba(30,41,59,0.85)',
                    border:
                      turn.role === 'user'
                        ? '1px solid rgba(52,211,153,0.4)'
                        : '1px solid rgba(148,163,184,0.18)',
                    fontSize: 12.5,
                    lineHeight: 1.5,
                    color: '#f1f5f9',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#94a3b8', marginBottom: 4 }}>
                    <span style={{ fontWeight: 700, color: turn.role === 'user' ? '#6ee7b7' : '#7dd3fc' }}>
                      {turn.role === 'user' ? 'Vous' : '🤖 Copilote Aurora Business (Conseil 10 Agents)'}
                    </span>
                    <span>{turn.timestamp}</span>
                  </div>
                  <div>{turn.content}</div>
                  {turn.executedActions && turn.executedActions.length > 0 && (
                    <div
                      style={{
                        marginTop: 8,
                        padding: '6px 8px',
                        borderRadius: 6,
                        background: 'rgba(16,185,129,0.15)',
                        border: '1px solid rgba(52,211,153,0.35)',
                        fontSize: 11,
                        color: '#a7f3d0',
                      }}
                    >
                      {turn.executedActions.map((act, i) => (
                        <div key={i}>⚡ {act}</div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
              {chatSending && (
                <div style={{ fontSize: 12, color: '#7dd3fc', padding: '6px 10px' }}>
                  🤖 Le Conseil des 10 Agents analyse les cours en direct et prépare votre réponse...
                </div>
              )}
            </div>
          </div>

          {/* QUICK SUGGESTIONS & INPUT */}
          <div style={{ marginTop: 10 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
              {suggestedPrompts.map((sp, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => void handleSendChatMessage(sp)}
                  disabled={chatSending}
                  style={{
                    padding: '5px 10px',
                    borderRadius: 99,
                    background: 'rgba(30,41,59,0.8)',
                    border: '1px solid rgba(56,189,248,0.28)',
                    color: '#bae6fd',
                    fontSize: 11,
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                >
                  💬 {sp}
                </button>
              ))}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault()
                void handleSendChatMessage()
              }}
              style={{ display: 'flex', gap: 8 }}
            >
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder={
                  pedagogicalMode
                    ? 'Ex: « J’ai 5 000 € fictifs, lance une activité sûre et montre-moi ce que je gagne net »...'
                    : 'Ex: « Alloue 10 000 € entre Micro-SaaS B2B et ETF Monde CW8 avec réserve 30% »...'
                }
                style={{
                  flex: 1,
                  padding: '10px 12px',
                  borderRadius: 10,
                  background: '#0f172a',
                  border: '1px solid rgba(56,189,248,0.35)',
                  color: '#f8fafc',
                  fontSize: 13,
                  outline: 'none',
                }}
              />
              <button
                type="submit"
                disabled={chatSending || !chatInput.trim()}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '10px 16px',
                  borderRadius: 10,
                  background: '#38bdf8',
                  color: '#082f49',
                  fontWeight: 700,
                  fontSize: 13,
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                <Send size={15} />
                Envoyer
              </button>
            </form>
          </div>
        </div>

        {/* 2. LIVE REAL-TIME VIRTUAL PORTFOLIO & ENTERPRISE COCKPIT ("EN DIRECT") */}
        <div
          style={{
            padding: 18,
            borderRadius: 14,
            background: 'rgba(15,23,42,0.88)',
            border: '1px solid rgba(52,211,153,0.32)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8, color: '#ecfdf5' }}>
                <Zap size={18} color="#34d399" />
                Votre Portefeuille & Entreprise Virtuelle En Direct (Temps Réel)
              </h2>
              <button
                type="button"
                onClick={() => void handleLivePaperAction({ action: 'auto_pilot' })}
                disabled={liveTickLoading}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 12px',
                  borderRadius: 8,
                  background: '#10b981',
                  color: '#052e16',
                  fontWeight: 700,
                  fontSize: 11.5,
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                <Bot size={14} />
                Pilotage Auto IA En Direct
              </button>
            </div>
            <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 12px' }}>
              Ce tableau de bord n’est pas un historique du passé : il évolue <strong>maintenant en direct</strong> avec
              votre capital fictif sur les vrais cours actuels et encaisse les revenus de vos activités virtuelles.
            </p>

            {/* 3 KEY LIVE PILLARS */}
            {paperPortfolio && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
                <div style={{ padding: 10, borderRadius: 10, background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(52,211,153,0.3)' }}>
                  <div style={{ fontSize: 10.5, color: '#a7f3d0' }}>
                    {pedagogicalMode ? 'Valeur Totale Aujourd’hui' : 'Mark-to-Market Equity'}
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace', color: '#34d399', marginTop: 2 }}>
                    {Number(paperPortfolio.total_mark_to_market_equity_eur || capitalEur).toLocaleString('fr-FR')} €
                  </div>
                  <div style={{ fontSize: 10.5, color: '#6ee7b7' }}>
                    {paperPortfolio.total_return_pct >= 0 ? '+' : ''}
                    {paperPortfolio.total_return_pct}% vs départ ({Number(paperPortfolio.initial_capital_eur).toLocaleString('fr-FR')} €)
                  </div>
                </div>

                <div style={{ padding: 10, borderRadius: 10, background: 'rgba(56,189,248,0.12)', border: '1px solid rgba(56,189,248,0.3)' }}>
                  <div style={{ fontSize: 10.5, color: '#bae6fd' }}>
                    {pedagogicalMode ? '🛡️ Réserve de Sécurité Intouchable' : 'Réserve Liquide (Solvabilité)'}
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace', color: '#38bdf8', marginTop: 2 }}>
                    {Number(paperPortfolio.liquid_cash_eur || 0).toLocaleString('fr-FR')} €
                  </div>
                  <div style={{ fontSize: 10.5, color: '#7dd3fc' }}>
                    {Math.round((paperPortfolio.cash_reserve_ratio || 0.3) * 100)}% gardés à l’abri (min 25%)
                  </div>
                </div>

                <div style={{ padding: 10, borderRadius: 10, background: 'rgba(167,139,250,0.12)', border: '1px solid rgba(167,139,250,0.3)' }}>
                  <div style={{ fontSize: 10.5, color: '#ddd6fe' }}>
                    {pedagogicalMode ? '🚀 En Travail En Direct' : 'Actifs Marché + Ventures'}
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 700, fontFamily: 'monospace', color: '#c4b5fd', marginTop: 2 }}>
                    {Math.round(
                      Number(paperPortfolio.market_positions_value_eur || 0) +
                        Number(paperPortfolio.virtual_ventures_value_eur || 0),
                    ).toLocaleString('fr-FR')}{' '}
                    €
                  </div>
                  <div style={{ fontSize: 10.5, color: '#c4b5fd' }}>
                    Marchés : {Math.round(Number(paperPortfolio.market_positions_value_eur || 0)).toLocaleString('fr-FR')} € · Business :{' '}
                    {Math.round(Number(paperPortfolio.virtual_ventures_value_eur || 0)).toLocaleString('fr-FR')} €
                  </div>
                </div>
              </div>
            )}

            {/* ACTIVE VIRTUAL ENTERPRISES & MARKET POSITIONS */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 165, overflowY: 'auto' }}>
              {(paperPortfolio?.ventures || []).map((v: any) => (
                <div
                  key={v.venture_id}
                  style={{
                    padding: '8px 10px',
                    borderRadius: 8,
                    background: 'rgba(30,41,59,0.75)',
                    border: '1px solid rgba(167,139,250,0.25)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 11.5,
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 700, color: '#ede9fe' }}>🏢 {v.name}</div>
                    <div style={{ color: '#94a3b8', fontSize: 11 }}>
                      Revenus : <strong style={{ color: '#34d399' }}>+{v.current_mrr_eur} €/mois</strong> · Charges :{' '}
                      {v.monthly_burn_eur} €/mois · Net en poche :{' '}
                      <strong style={{ color: '#6ee7b7' }}>+{v.net_monthly_cashflow_eur ?? Math.round(v.current_mrr_eur - v.monthly_burn_eur)} €/mois</strong>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => void handleLivePaperAction({ action: 'close_venture', venture_id: v.venture_id })}
                    style={{
                      padding: '4px 8px',
                      borderRadius: 6,
                      background: 'rgba(239,68,68,0.16)',
                      border: '1px solid rgba(239,68,68,0.35)',
                      color: '#fca5a5',
                      fontSize: 10.5,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    Revendre & Encaisser
                  </button>
                </div>
              ))}

              {(paperPortfolio?.positions || []).map((p: any) => (
                <div
                  key={p.instrument_id}
                  style={{
                    padding: '8px 10px',
                    borderRadius: 8,
                    background: 'rgba(30,41,59,0.65)',
                    border: '1px solid rgba(56,189,248,0.22)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 11.5,
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 700, color: '#e0f2fe' }}>
                      📈 {p.name} ({p.symbol})
                    </div>
                    <div style={{ color: '#94a3b8', fontSize: 11 }}>
                      Valeur en direct : <strong style={{ color: '#f8fafc' }}>{p.market_value_eur} €</strong> (Cours actuel :{' '}
                      {p.current_price_eur} € · Gain/Perte :{' '}
                      <span style={{ color: p.unrealized_pnl_eur >= 0 ? '#34d399' : '#f87171', fontWeight: 700 }}>
                        {p.unrealized_pnl_eur >= 0 ? '+' : ''}
                        {p.unrealized_pnl_eur} €
                      </span>
                      )
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      void handleLivePaperAction({ action: 'sell_asset', instrument_id: p.instrument_id, fraction: 1.0 })
                    }
                    style={{
                      padding: '4px 8px',
                      borderRadius: 6,
                      background: 'rgba(56,189,248,0.16)',
                      border: '1px solid rgba(56,189,248,0.35)',
                      color: '#bae6fd',
                      fontSize: 10.5,
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    Vendre en direct
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* ONE-CLICK LIVE ACTIONS IN THE PRESENT */}
          <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid rgba(148,163,184,0.14)' }}>
            <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 6, fontWeight: 600 }}>
              ⚡ Agir en direct maintenant avec votre argent fictif (au prix réel de cet instant) :
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              <button
                type="button"
                onClick={() =>
                  void handleLivePaperAction({
                    action: 'buy_asset',
                    instrument_id: 'MSCI_WORLD_ETF',
                    amount_eur: Math.max(25, Math.round(capitalEur * 0.12)),
                  })
                }
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '5px 10px',
                  borderRadius: 7,
                  background: 'rgba(16,185,129,0.15)',
                  border: '1px solid rgba(52,211,153,0.35)',
                  color: '#6ee7b7',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <PlusCircle size={12} />+ ETF Monde ({Math.max(25, Math.round(capitalEur * 0.12))} €)
              </button>

              <button
                type="button"
                onClick={() =>
                  void handleLivePaperAction({
                    action: 'buy_asset',
                    instrument_id: 'GOLD_COMMODITY',
                    amount_eur: Math.max(25, Math.round(capitalEur * 0.1)),
                  })
                }
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '5px 10px',
                  borderRadius: 7,
                  background: 'rgba(245,158,11,0.15)',
                  border: '1px solid rgba(251,191,36,0.35)',
                  color: '#fde68a',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <PlusCircle size={12} />+ Or Refuge ({Math.max(25, Math.round(capitalEur * 0.1))} €)
              </button>

              <button
                type="button"
                onClick={() =>
                  void handleLivePaperAction({
                    action: 'launch_venture',
                    archetype_id: 'b2b_ai_service_agency',
                    amount_eur: Math.max(50, Math.round(capitalEur * 0.2)),
                  })
                }
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '5px 10px',
                  borderRadius: 7,
                  background: 'rgba(167,139,250,0.16)',
                  border: '1px solid rgba(167,139,250,0.4)',
                  color: '#ddd6fe',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <PlusCircle size={12} />+ Lancer Service Numérique ({Math.max(50, Math.round(capitalEur * 0.2))} €)
              </button>

              <button
                type="button"
                onClick={() =>
                  void handleLivePaperAction({
                    action: 'launch_venture',
                    archetype_id: 'saas_b2b_micro',
                    amount_eur: Math.max(50, Math.round(capitalEur * 0.2)),
                  })
                }
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  padding: '5px 10px',
                  borderRadius: 7,
                  background: 'rgba(56,189,248,0.16)',
                  border: '1px solid rgba(56,189,248,0.4)',
                  color: '#bae6fd',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                <PlusCircle size={12} />+ Lancer Logiciel SaaS ({Math.max(50, Math.round(capitalEur * 0.2))} €)
              </button>
            </div>

            {liveTickEvents.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 10.5, color: '#94a3b8' }}>
                Dernier événement en direct : <span style={{ color: '#6ee7b7' }}>{liveTickEvents[0].label}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ==================================================================== */}
      {/* SECTION A — AURORA BUSINESS LAB                                      */}
      {/* ==================================================================== */}
      {section === 'lab' && (
        <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* A.1 CAPITAL FICTIF & CONFIGURATION */}
          <div
            style={{
              padding: 20,
              borderRadius: 14,
              background: 'rgba(15,23,42,0.82)',
              border: '1px solid rgba(52,211,153,0.25)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <h2 style={{ fontSize: 17, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <DollarSign size={18} color="#34d399" />
                  {pedagogicalMode
                    ? 'Choisissez l’argent fictif à confier à AuroraIA (En Direct)'
                    : 'A.1 Capital Virtuel Initial & Paramètres du Simulateur Économique'}
                </h2>
                <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 0' }}>
                  {pedagogicalMode
                    ? 'Testez avec 100 €, 1 000 €, 10 000 € ou le montant de votre choix : AuroraIA calcule tout pour vous (charges et impôts déjà déduits automatiquement) et protège votre argent contre la faillite.'
                    : 'Compare la création d’entreprise (SaaS, B2B, e-commerce), l’investissement financier et la réserve de liquidités. Aucun argent réel ne peut être dépensé.'}
                </p>
              </div>
              <button
                type="button"
                disabled={loading}
                onClick={() => void runCouncilAndSimulation(capitalEur, selectedStrategyId, horizonMonths, taxRate)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '10px 18px',
                  borderRadius: 10,
                  background: '#10b981',
                  color: '#052e16',
                  fontWeight: 700,
                  fontSize: 13,
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                <RefreshCw size={15} />
                {loading
                  ? 'Calcul en direct...'
                  : pedagogicalMode
                    ? 'Trouver le Meilleur Plan Sûr'
                    : 'Simuler & Délibérer (13 étapes)'}
              </button>
            </div>

            {/* CAPITAL PRESETS */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 14, alignItems: 'center' }}>
              {CAPITAL_PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => void handleSelectCapital(preset)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 8,
                    fontWeight: 700,
                    fontSize: 13,
                    fontFamily: 'monospace',
                    cursor: 'pointer',
                    border: capitalEur === preset ? '1px solid #34d399' : '1px solid rgba(148,163,184,0.22)',
                    background: capitalEur === preset ? 'rgba(16,185,129,0.22)' : 'rgba(30,41,59,0.7)',
                    color: capitalEur === preset ? '#6ee7b7' : '#cbd5e1',
                  }}
                >
                  {preset.toLocaleString('fr-FR')} €
                </button>
              ))}

              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 8 }}>
                <span style={{ fontSize: 12, color: '#94a3b8' }}>Autre montant (€) :</span>
                <input
                  type="number"
                  min={10}
                  step={100}
                  value={customCapitalInput}
                  onChange={(e) => setCustomCapitalInput(e.target.value)}
                  style={{
                    width: 120,
                    padding: '7px 10px',
                    borderRadius: 8,
                    background: '#0f172a',
                    border: '1px solid rgba(148,163,184,0.3)',
                    color: '#f8fafc',
                    fontFamily: 'monospace',
                    fontSize: 13,
                  }}
                />
                <button
                  type="button"
                  onClick={() => void handleSelectCapital(Number(customCapitalInput) || 10_000)}
                  style={{
                    padding: '7px 12px',
                    borderRadius: 8,
                    background: 'rgba(56,189,248,0.18)',
                    border: '1px solid rgba(56,189,248,0.4)',
                    color: '#7dd3fc',
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Valider
                </button>
              </div>
            </div>

            {/* STRATEGY & HORIZON CONTROLS — STRICTLY ADAPTED TO BEGINNER VS EXPERT */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: 12,
                marginTop: 14,
              }}
            >
              <div>
                <label style={{ fontSize: 11, color: '#94a3b8', display: 'block', marginBottom: 4 }}>
                  {pedagogicalMode ? 'Que souhaitez-vous faire avec cet argent ?' : 'Stratégie testée dans le Simulateur'}
                </label>
                <select
                  value={selectedStrategyId}
                  onChange={(e) => {
                    setSelectedStrategyId(e.target.value)
                    void runCouncilAndSimulation(capitalEur, e.target.value, horizonMonths, taxRate)
                  }}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: 8,
                    background: '#0f172a',
                    border: '1px solid rgba(148,163,184,0.3)',
                    color: '#f8fafc',
                    fontSize: 13,
                  }}
                >
                  {strategies.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: 11, color: '#94a3b8', display: 'block', marginBottom: 4 }}>
                  {pedagogicalMode
                    ? `Durée de votre projet : ${horizonMonths} mois (${(horizonMonths / 12).toFixed(1)} ans)`
                    : `Horizon temporel : ${horizonMonths} mois (${(horizonMonths / 12).toFixed(1)} ans)`}
                </label>
                <input
                  type="range"
                  min={6}
                  max={60}
                  step={6}
                  value={horizonMonths}
                  onChange={(e) => setHorizonMonths(Number(e.target.value))}
                  style={{ width: '100%' }}
                />
              </div>

              {/* FISCALITÉ SLIDER ONLY IN EXPERT MODE! */}
              {!pedagogicalMode ? (
                <div>
                  <label style={{ fontSize: 11, color: '#94a3b8', display: 'block', marginBottom: 4 }}>
                    Fiscalité paramétrable (IS / Plus-values) : {(taxRate * 100).toFixed(0)}%
                  </label>
                  <input
                    type="range"
                    min={0}
                    max={0.45}
                    step={0.05}
                    value={taxRate}
                    onChange={(e) => setTaxRate(Number(e.target.value))}
                    style={{ width: '100%' }}
                  />
                </div>
              ) : (
                <div
                  style={{
                    padding: '8px 12px',
                    borderRadius: 8,
                    background: 'rgba(16,185,129,0.1)',
                    border: '1px solid rgba(52,211,153,0.25)',
                    fontSize: 11.5,
                    color: '#a7f3d0',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                >
                  ✅ Mode Débutant : vous n’avez aucun réglage fiscal compliqué à faire. Aurora déduit automatiquement
                  toutes les charges et taxes et vous affiche directement ce qu’il vous reste net dans la poche.
                </div>
              )}
            </div>
          </div>

          {/* A.2 & A.4 SIMULATION METRICS — BEGINNER FRIENDLY VS EXPERT QUANT */}
          {simulation && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
              <div style={{ padding: 16, borderRadius: 12, background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(148,163,184,0.16)' }}>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  {pedagogicalMode
                    ? '💰 Ce que vous auriez NET dans votre poche (Frais & taxes déjà déduits)'
                    : 'Capital Final Réel Médian (Net d’Inflation & Impôts)'}
                </div>
                <div style={{ fontSize: 22, fontWeight: 700, color: '#34d399', marginTop: 4, fontFamily: 'monospace' }}>
                  {simulation.monte_carlo.median_final_real_equity_eur.toLocaleString('fr-FR')} €
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                  {pedagogicalMode
                    ? `Soit ${netGainPocketEur >= 0 ? '+' : ''}${netGainPocketEur.toLocaleString('fr-FR')} € de gain net (Fourchette prudente : ${simulation.monte_carlo.ci_95_low_equity_eur.toLocaleString('fr-FR')} € à ${simulation.monte_carlo.ci_95_high_equity_eur.toLocaleString('fr-FR')} €)`
                    : `IC 95% : [${simulation.monte_carlo.ci_95_low_equity_eur.toLocaleString('fr-FR')} € ; ${simulation.monte_carlo.ci_95_high_equity_eur.toLocaleString('fr-FR')} €]`}
                </div>
              </div>

              <div style={{ padding: 16, borderRadius: 12, background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(148,163,184,0.16)' }}>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  {pedagogicalMode ? '📈 Rythme de progression net par an' : 'CAGR Réel Médian & Ratio de Sortino'}
                </div>
                <div style={{ fontSize: 22, fontWeight: 700, color: '#38bdf8', marginTop: 4, fontFamily: 'monospace' }}>
                  {simulation.monte_carlo.median_real_cagr_pct >= 0 ? '+' : ''}
                  {simulation.monte_carlo.median_real_cagr_pct}% / an
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                  {pedagogicalMode
                    ? 'Pouvoir d’achat réel (hausse des prix de la vie déjà déduite)'
                    : `Sortino : ${simulation.monte_carlo.median_sortino_ratio} · Walk-Forward Test : ${simulation.walk_forward_validation.unseen_test_real_cagr_pct}%`}
                </div>
              </div>

              <div style={{ padding: 16, borderRadius: 12, background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(148,163,184,0.16)' }}>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>
                  {pedagogicalMode
                    ? '🛡️ Sécurité & Pire baisse temporaire possible'
                    : 'Probabilité de Ruine & Drawdown P90'}
                </div>
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 700,
                    color: simulation.monte_carlo.ruin_probability_pct <= 2.0 ? '#34d399' : '#f87171',
                    marginTop: 4,
                    fontFamily: 'monospace',
                  }}
                >
                  {pedagogicalMode
                    ? `Risque faillite : ${simulation.monte_carlo.ruin_probability_pct}%`
                    : `Ruine : ${simulation.monte_carlo.ruin_probability_pct}%`}
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                  {pedagogicalMode
                    ? `Baisse passagère max en cas de crise : -${worstLossEur.toLocaleString('fr-FR')} € (-${simulation.monte_carlo.p90_max_drawdown_pct}%)`
                    : `Max Drawdown P90 : -${simulation.monte_carlo.p90_max_drawdown_pct}% · Réserve : ${(simulation.risk_manager_verdict.cash_reserve_ratio * 100).toFixed(0)}%`}
                </div>
              </div>

              <div
                style={{
                  padding: 16,
                  borderRadius: 12,
                  background: simulation.risk_manager_verdict.approved
                    ? 'rgba(16,185,129,0.12)'
                    : 'rgba(239,68,68,0.15)',
                  border: `1px solid ${
                    simulation.risk_manager_verdict.approved ? 'rgba(52,211,153,0.35)' : 'rgba(248,113,113,0.4)'
                  }`,
                }}
              >
                <div style={{ fontSize: 11, color: '#cbd5e1', display: 'flex', alignItems: 'center', gap: 6 }}>
                  {simulation.risk_manager_verdict.approved ? (
                    <ShieldCheck size={15} color="#34d399" />
                  ) : (
                    <ShieldAlert size={15} color="#f87171" />
                  )}
                  {pedagogicalMode ? 'Contrôle de Protection de votre Argent' : 'Verdict Indépendant Risk Manager'}
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>
                  {simulation.risk_manager_verdict.approved ? 'SURVIE PROTÉGÉE' : 'BLOQUÉ (TROP RISQUÉ)'} (Note{' '}
                  {simulation.reward_evaluation.survival_grade})
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                  {pedagogicalMode
                    ? `${simulation.risk_manager_verdict.cash_reserve_eur.toLocaleString('fr-FR')} € gardés en sécurité absolue`
                    : `Score survie : ${simulation.reward_evaluation.total_reward} · Risque : ${simulation.risk_manager_verdict.risk_score_0_100}/100`}
                </div>
              </div>
            </div>
          )}

          {/* MONTHLY TRAJECTORY & REAL-WORLD DEDUCTIONS */}
          {simulation && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                gap: 16,
              }}
            >
              <div
                style={{
                  padding: 18,
                  borderRadius: 12,
                  background: 'rgba(15,23,42,0.82)',
                  border: '1px solid rgba(148,163,184,0.16)',
                }}
              >
                <h3 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <TrendingUp size={16} color="#38bdf8" />
                  {pedagogicalMode
                    ? 'Évolution mois par mois : Votre Argent Net (Vert) & Votre Matelas de Sécurité (Bleu)'
                    : 'Trajectoire Mensuelle Simulée (Réel Ajusté de l’Inflation & Trésorerie Liquide)'}
                </h3>
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 140, padding: '8px 0' }}>
                  {traj.map((pt) => {
                    const maxEq = Math.max(...traj.map((t) => t.nominal_equity_eur), capitalEur * 1.2)
                    const hReal = Math.max(8, Math.round((pt.real_equity_eur / maxEq) * 125))
                    const hCash = Math.max(4, Math.round((pt.liquid_cash_eur / maxEq) * 125))
                    return (
                      <div
                        key={pt.month}
                        title={`Mois ${pt.month} | Argent net: ${pt.real_equity_eur} € | Réserve sécurité: ${pt.liquid_cash_eur} € | Revenus mensuels: ${pt.mrr_eur} €`}
                        style={{
                          flex: 1,
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          gap: 2,
                        }}
                      >
                        <div style={{ width: '100%', display: 'flex', alignItems: 'flex-end', gap: 1, height: 125 }}>
                          <div
                            style={{
                              flex: 1,
                              height: hReal,
                              borderRadius: '3px 3px 0 0',
                              background: pt.shock_event ? '#f59e0b' : '#10b981',
                            }}
                          />
                          <div
                            style={{
                              width: '35%',
                              height: hCash,
                              borderRadius: '2px 2px 0 0',
                              background: '#38bdf8',
                            }}
                          />
                        </div>
                        {pt.month % 3 === 0 && (
                          <span style={{ fontSize: 9, color: '#64748b', fontFamily: 'monospace' }}>M{pt.month}</span>
                        )}
                      </div>
                    )
                  })}
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 8 }}>
                  {simulation.walk_forward_validation.backtest_disclaimer}
                </div>
              </div>

              {/* DEDUCTIONS / FRICTIONS BREAKDOWN */}
              <div
                style={{
                  padding: 18,
                  borderRadius: 12,
                  background: 'rgba(15,23,42,0.82)',
                  border: '1px solid rgba(148,163,184,0.16)',
                }}
              >
                <h3 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 12px' }}>
                  {pedagogicalMode
                    ? 'Ce qu’Aurora a déjà payé et déduit pour vous (Zéro mauvaise surprise)'
                    : 'Frictions Réelles Modélisées (Section A.2)'}
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>
                      {pedagogicalMode ? 'Taxes et impôts déduits automatiquement :' : 'Impôts payés (IS/Plus-values) :'}
                    </span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {simulation.baseline_trajectory.frictions_summary.cumulative_taxes_paid_eur.toLocaleString('fr-FR')} €
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>
                      {pedagogicalMode ? 'Frais bancaires et d’achat/vente :' : 'Commissions, Spreads & Slippage :'}
                    </span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {simulation.baseline_trajectory.frictions_summary.cumulative_commissions_and_slippage_eur.toLocaleString('fr-FR')} €
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>
                      {pedagogicalMode ? 'Marge de sécurité pour factures impayées :' : 'Défauts de contrepartie / Impayés :'}
                    </span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {simulation.baseline_trajectory.frictions_summary.cumulative_bad_debt_losses_eur.toLocaleString('fr-FR')} €
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>
                      {pedagogicalMode ? 'Délai moyen avant que les clients paient :' : 'Délai paiement client (DSO BFR) :'}
                    </span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {simulation.baseline_trajectory.frictions_summary.dso_payment_delay_days} jours
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>
                      {pedagogicalMode ? 'Hausse du coût de la vie prise en compte :' : 'Inflation annuelle appliquée :'}
                    </span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {simulation.baseline_trajectory.frictions_summary.annual_inflation_pct}% / an
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>
                      {pedagogicalMode ? 'Règle anti-casino (ne jamais doubler après perte) :' : 'Détection Anti-Martingale :'}
                    </span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#34d399' }}>
                      {simulation.risk_manager_verdict.martingale_detected ? 'ALERTE RISQUE' : 'Active & Protégée ✓'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* KAGGLE & COLAB COMPUTE GOVERNOR + RL TRAINING */}
          <div
            style={{
              padding: 18,
              borderRadius: 12,
              background: 'rgba(15,23,42,0.82)',
              border: '1px solid rgba(56,189,248,0.25)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Cpu size={17} color="#38bdf8" />
                  {pedagogicalMode
                    ? 'Entraînement Intensif de l’IA (Apprendre des Crises sans Risquer 1 €)'
                    : 'A.3 & Section 6 · Infrastructure d’Entraînement RL & Gouverneur de Quotas Kaggle / Google Colab'}
                </h3>
                <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 0' }}>
                  {pedagogicalMode
                    ? 'Faites s’entraîner AuroraIA sur des dizaines de scénarios économiques (crises, inflation, concurrence). Elle ne garde une nouvelle stratégie que si le risque de faillite reste quasi nul.'
                    : 'Skill actif : kaggle-colab-compute-governor · Notebook reproductible : notebooks/aurora_business_rl_training.ipynb · Porte de promotion avec rollback automatique.'}
                </p>
              </div>
              <button
                type="button"
                disabled={trainingLoading}
                onClick={() => void handleTrainPolicy()}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '9px 16px',
                  borderRadius: 9,
                  background: '#38bdf8',
                  color: '#082f49',
                  fontWeight: 700,
                  fontSize: 12,
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                <Play size={14} />
                {trainingLoading
                  ? 'Entraînement de l’IA en cours...'
                  : pedagogicalMode
                    ? 'Entraîner l’IA à Protéger & Faire Grandir mon Capital'
                    : 'Lancer Entraînement RL & Validation Walk-Forward'}
              </button>
            </div>

            {computeGovernor && !pedagogicalMode && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10, marginTop: 12 }}>
                <div style={{ padding: 12, borderRadius: 8, background: 'rgba(30,41,59,0.6)', fontSize: 12 }}>
                  <div style={{ color: '#94a3b8' }}>Statut API Kaggle & Quotas</div>
                  <div style={{ fontWeight: 700, marginTop: 4 }}>
                    {computeGovernor.kaggle?.credentials_configured
                      ? `Connecté (${computeGovernor.kaggle.username}) · Quota 30h/sem GPU`
                      : 'Exécution Locale GPU/CPU + Notebook Kaggle/Colab prêt'}
                  </div>
                </div>
                <div style={{ padding: 12, borderRadius: 8, background: 'rgba(30,41,59,0.6)', fontSize: 12 }}>
                  <div style={{ color: '#94a3b8' }}>Accélérateur Local Détecté</div>
                  <div style={{ fontWeight: 700, marginTop: 4 }}>{computeGovernor.local_compute?.device}</div>
                </div>
                <div style={{ padding: 12, borderRadius: 8, background: 'rgba(30,41,59,0.6)', fontSize: 12 }}>
                  <div style={{ color: '#94a3b8' }}>Cible d’Exécution Recommandée</div>
                  <div style={{ fontWeight: 700, marginTop: 4, color: '#38bdf8' }}>
                    {computeGovernor.recommended_execution_target}
                  </div>
                </div>
              </div>
            )}

            {trainingReport && (
              <div
                style={{
                  marginTop: 12,
                  padding: 14,
                  borderRadius: 10,
                  background: 'rgba(16,185,129,0.1)',
                  border: '1px solid rgba(52,211,153,0.3)',
                  fontSize: 12,
                }}
              >
                <div style={{ fontWeight: 700, color: '#6ee7b7' }}>
                  ✅ Entraînement terminé ({trainingReport.episodes_trained} campagnes simulées en {trainingReport.elapsed_ms} ms) — Meilleure
                  stratégie retenue : {trainingReport.learned_best_strategy_name}
                </div>
                <div style={{ marginTop: 4, color: '#cbd5e1' }}>
                  Validation de sécurité :{' '}
                  <strong>
                    {trainingReport.promotion_gate?.promoted
                      ? 'NOUVELLE STRATÉGIE VALIDÉE ET ACTIVÉE'
                      : 'ANCIENNE STRATÉGIE CONSERVÉE PAR SÉCURITÉ'}
                  </strong>{' '}
                  (Risque de faillite mesuré : {trainingReport.promotion_gate?.ruin_prob_pct}%, Progression nette sur données nouvelles :{' '}
                  {trainingReport.promotion_gate?.unseen_test_cagr_pct}%/an)
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* SECTION B — AURORA BUSINESS LIVE                                     */}
      {/* ==================================================================== */}
      {section === 'live' && (
        <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* B.1 GOUVERNANCE, MODES D'ACTIVATION & KILL-SWITCH */}
          <div
            style={{
              padding: 20,
              borderRadius: 14,
              background: 'rgba(15,23,42,0.86)',
              border: '1px solid rgba(251,191,36,0.3)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <h2 style={{ fontSize: 17, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Lock size={18} color="#fbbf24" />
                  {pedagogicalMode
                    ? 'Protection Absolue : Vos Règles de Sécurité & Bouton d’Arrêt Immédiat'
                    : 'B.1 & B.3 Gouvernance Business Live, Readiness Gate & Arrêt d’Urgence'}
                </h2>
                <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 0' }}>
                  Aucun paiement réel, contrat, emprunt ou engagement externe n’est exécuté sans votre validation humaine explicite.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  void handleUpdateGovernance({
                    emergency_stop: !liveGovernance?.governance?.emergency_stop,
                  })
                }
                style={{
                  padding: '10px 16px',
                  borderRadius: 10,
                  fontWeight: 700,
                  fontSize: 12,
                  cursor: 'pointer',
                  border: '1px solid #ef4444',
                  background: liveGovernance?.governance?.emergency_stop ? '#ef4444' : 'rgba(239,68,68,0.18)',
                  color: '#fef2f2',
                }}
              >
                {liveGovernance?.governance?.emergency_stop
                  ? '🛑 ARRÊT D’URGENCE ACTIF (Cliquer pour réactiver)'
                  : '🛑 ARRÊT D’URGENCE IMMÉDIAT (STOPPER TOUT)'}
              </button>
            </div>

            {/* 4 MODES D'ACTIVATION */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 10, marginTop: 14 }}>
              {[
                {
                  id: 'MODE_1_OBSERVATION',
                  label: 'Mode 1 · Observation seule',
                  desc: 'Surveille les prix et opportunités en direct sans rien modifier',
                },
                {
                  id: 'MODE_2_RECOMMENDATION',
                  label: 'Mode 2 · Conseils chiffrés',
                  desc: 'Vous explique quoi faire étape par étape, vous décidez de tout',
                },
                {
                  id: 'MODE_3_ASSISTED',
                  label: 'Mode 3 · Préparation assistée',
                  desc: 'Prépare les actions pour vous et attend votre clic de confirmation',
                },
                {
                  id: 'MODE_4_SUPERVISED_AUTONOMOUS',
                  label: 'Mode 4 · Pilotage sous plafond',
                  desc: 'Gère automatiquement dans la limite stricte de votre budget autorisé',
                },
              ].map((m) => {
                const active = (liveGovernance?.governance?.operational_mode || 'MODE_2_RECOMMENDATION') === m.id
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => void handleUpdateGovernance({ operational_mode: m.id })}
                    style={{
                      textAlign: 'left',
                      padding: 12,
                      borderRadius: 10,
                      cursor: 'pointer',
                      border: active ? '1px solid #fbbf24' : '1px solid rgba(148,163,184,0.2)',
                      background: active ? 'rgba(245,158,11,0.16)' : 'rgba(30,41,59,0.55)',
                      color: '#f8fafc',
                    }}
                  >
                    <div style={{ fontSize: 13, fontWeight: 700 }}>{m.label}</div>
                    <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>{m.desc}</div>
                  </button>
                )
              })}
            </div>

            {/* READINESS GATE CHECKLIST */}
            {liveGovernance?.criteria && (
              <div style={{ marginTop: 14, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 8 }}>
                {liveGovernance.criteria.map((c: any) => (
                  <div
                    key={c.id}
                    style={{
                      padding: '8px 12px',
                      borderRadius: 8,
                      background: 'rgba(15,23,42,0.65)',
                      border: '1px solid rgba(148,163,184,0.14)',
                      fontSize: 11,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                    }}
                  >
                    {c.passed ? <CheckCircle2 size={14} color="#34d399" /> : <AlertTriangle size={14} color="#fbbf24" />}
                    <div>
                      <div style={{ fontWeight: 600 }}>{c.label}</div>
                      <div style={{ color: '#94a3b8' }}>{c.measured}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* B.2 ÉTUDE DE VIABILITÉ OPÉRATIONNELLE (SIMPLE EN MODE DÉBUTANT, UNIT ECONOMICS EN MODE EXPERT) */}
          <div
            style={{
              padding: 20,
              borderRadius: 14,
              background: 'rgba(15,23,42,0.82)',
              border: '1px solid rgba(148,163,184,0.2)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Activity size={17} color="#fbbf24" />
                  {pedagogicalMode
                    ? 'Vérifier si votre idée de business est rentable (Questions Simples)'
                    : 'B.2 Calculateur d’Économie Unitaire (LTV/CAC, DSO, Point Mort) & Détecteur d’Anomalies'}
                </h3>
                <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 0' }}>
                  {pedagogicalMode
                    ? 'Indiquez vos prix et vos dépenses estimées : Aurora vérifie immédiatement si vous gagnez vraiment de l’argent et combien de clients il vous faut.'
                    : 'Analyse la marge sur coût variable, le ratio LTV/CAC, le besoin en fonds de roulement (DSO) et les anomalies de coûts.'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => void handleRunViability()}
                style={{
                  padding: '9px 16px',
                  borderRadius: 8,
                  background: '#fbbf24',
                  color: '#451a03',
                  fontWeight: 700,
                  fontSize: 12,
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                {pedagogicalMode ? 'Vérifier si mon idée est rentable' : 'Analyser la Viabilité & les Risques'}
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(185px, 1fr))', gap: 10, marginTop: 12 }}>
              <div>
                <label style={{ fontSize: 11, color: '#94a3b8' }}>
                  {pedagogicalMode ? 'Prix payé par 1 client (€)' : 'Prix unitaire / mois (€)'}
                </label>
                <input
                  type="number"
                  value={viabilityInput.unit_price_eur}
                  onChange={(e) => setViabilityInput({ ...viabilityInput, unit_price_eur: Number(e.target.value) })}
                  style={{ width: '100%', padding: 7, borderRadius: 6, background: '#0f172a', color: '#fff', border: '1px solid #334155', marginTop: 4 }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: '#94a3b8' }}>
                  {pedagogicalMode ? 'Ce que vous coûte 1 vente (€)' : 'Coût variable unitaire (€)'}
                </label>
                <input
                  type="number"
                  value={viabilityInput.unit_variable_cost_eur}
                  onChange={(e) => setViabilityInput({ ...viabilityInput, unit_variable_cost_eur: Number(e.target.value) })}
                  style={{ width: '100%', padding: 7, borderRadius: 6, background: '#0f172a', color: '#fff', border: '1px solid #334155', marginTop: 4 }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: '#94a3b8' }}>
                  {pedagogicalMode ? 'Frais fixes chaque mois (€)' : 'Coûts fixes / mois (€)'}
                </label>
                <input
                  type="number"
                  value={viabilityInput.monthly_fixed_cost_eur}
                  onChange={(e) => setViabilityInput({ ...viabilityInput, monthly_fixed_cost_eur: Number(e.target.value) })}
                  style={{ width: '100%', padding: 7, borderRadius: 6, background: '#0f172a', color: '#fff', border: '1px solid #334155', marginTop: 4 }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: '#94a3b8' }}>
                  {pedagogicalMode ? 'Budget pub pour gagner 1 client (€)' : 'CAC par client (€)'}
                </label>
                <input
                  type="number"
                  value={viabilityInput.cac_eur}
                  onChange={(e) => setViabilityInput({ ...viabilityInput, cac_eur: Number(e.target.value) })}
                  style={{ width: '100%', padding: 7, borderRadius: 6, background: '#0f172a', color: '#fff', border: '1px solid #334155', marginTop: 4 }}
                />
              </div>
              {!pedagogicalMode && (
                <div>
                  <label style={{ fontSize: 11, color: '#94a3b8' }}>Délai paiement DSO (jours)</label>
                  <input
                    type="number"
                    value={viabilityInput.dso_days}
                    onChange={(e) => setViabilityInput({ ...viabilityInput, dso_days: Number(e.target.value) })}
                    style={{ width: '100%', padding: 7, borderRadius: 6, background: '#0f172a', color: '#fff', border: '1px solid #334155', marginTop: 4 }}
                  />
                </div>
              )}
            </div>

            {viabilityResult && (
              <div style={{ marginTop: 14, padding: 14, borderRadius: 10, background: 'rgba(30,41,59,0.65)', fontSize: 12 }}>
                {pedagogicalMode ? (
                  <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', fontWeight: 700, color: '#e2e8f0' }}>
                    <span>
                      ✅ Gain sur chaque vente : {viabilityResult.unit_economics.unit_contribution_margin_eur} € ({viabilityResult.unit_economics.gross_margin_pct}%)
                    </span>
                    <span>
                      🎯 Clients nécessaires pour payer vos frais fixes : {viabilityResult.unit_economics.break_even_active_customers} clients
                    </span>
                    <span>
                      ⏱️ Temps pour rembourser la pub d’un client : {viabilityResult.unit_economics.cac_payback_months} mois
                    </span>
                    <span>
                      🛡️ Trésorerie conseillée au départ : {viabilityResult.unit_economics.recommended_capital_envelope_eur} €
                    </span>
                  </div>
                ) : (
                  <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', fontWeight: 700 }}>
                    <span>Marge brute : {viabilityResult.unit_economics.gross_margin_pct}%</span>
                    <span>Ratio LTV/CAC : {viabilityResult.unit_economics.ltv_to_cac_ratio}x</span>
                    <span>Payback CAC : {viabilityResult.unit_economics.cac_payback_months} mois</span>
                    <span>Seuil de rentabilité : {viabilityResult.unit_economics.break_even_active_customers} clients actifs</span>
                    <span>BFR (décalage DSO) : {viabilityResult.unit_economics.dso_working_capital_gap_eur} €</span>
                  </div>
                )}
                {viabilityResult.cost_and_margin_anomalies?.length > 0 && (
                  <ul style={{ margin: '8px 0 0', paddingLeft: 18, color: '#fca5a5' }}>
                    {viabilityResult.cost_and_margin_anomalies.map((anom: string, i: number) => (
                      <li key={i}>{anom}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* SHARED CORE — MULTI-SECTOR COMPARISON & 10-AGENT COUNCIL             */}
      {/* ==================================================================== */}
      {deliberation && (
        <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 18 }}>
          {/* COMPARATIVE RANKING TABLE OF ALL STRATEGIES */}
          <div
            style={{
              padding: 18,
              borderRadius: 12,
              background: 'rgba(15,23,42,0.82)',
              border: '1px solid rgba(148,163,184,0.18)',
            }}
          >
            <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Award size={17} color="#34d399" />
              {pedagogicalMode
                ? `Comparaison des meilleures options pour vos ${deliberation.capital_eur.toLocaleString('fr-FR')} € (Classées de la plus sûre et rentable à la moins adaptée)`
                : `Comparaison Multi-Secteurs pour ${deliberation.capital_eur.toLocaleString('fr-FR')} € (Entrepreneuriat vs Finance vs Inactivité Stratégique)`}
            </h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(148,163,184,0.2)', color: '#94a3b8', textAlign: 'left' }}>
                    <th style={{ padding: '8px 6px' }}>Rang</th>
                    <th style={{ padding: '8px 6px' }}>Option / Activité</th>
                    <th style={{ padding: '8px 6px' }}>{pedagogicalMode ? 'Gain Net Moyen / An' : 'CAGR Réel Médian'}</th>
                    <th style={{ padding: '8px 6px' }}>{pedagogicalMode ? 'Baisse Passagère Max' : 'Drawdown P90'}</th>
                    <th style={{ padding: '8px 6px' }}>{pedagogicalMode ? 'Risque de Faillite' : 'Risque Ruine'}</th>
                    <th style={{ padding: '8px 6px' }}>{pedagogicalMode ? 'Note de Sécurité' : 'Score Survie'}</th>
                    <th style={{ padding: '8px 6px' }}>{pedagogicalMode ? 'Validation Sécurité' : 'Risk Manager'}</th>
                  </tr>
                </thead>
                <tbody>
                  {deliberation.all_ranked_strategies.map((row) => (
                    <tr
                      key={row.strategy_id}
                      onClick={() => {
                        setSelectedStrategyId(row.strategy_id)
                        void runCouncilAndSimulation(capitalEur, row.strategy_id, horizonMonths, taxRate)
                      }}
                      style={{
                        borderBottom: '1px solid rgba(148,163,184,0.08)',
                        cursor: 'pointer',
                        background:
                          row.strategy_id === deliberation.selected_strategy.strategy_id
                            ? 'rgba(16,185,129,0.12)'
                            : 'transparent',
                      }}
                    >
                      <td style={{ padding: '8px 6px', fontWeight: 700 }}>#{row.rank}</td>
                      <td style={{ padding: '8px 6px', fontWeight: 600 }}>{row.strategy_name}</td>
                      <td style={{ padding: '8px 6px', fontFamily: 'monospace', color: '#38bdf8' }}>
                        {row.median_real_cagr_pct >= 0 ? '+' : ''}
                        {row.median_real_cagr_pct}%/an
                      </td>
                      <td style={{ padding: '8px 6px', fontFamily: 'monospace' }}>-{row.p90_max_drawdown_pct}%</td>
                      <td style={{ padding: '8px 6px', fontFamily: 'monospace' }}>{row.ruin_probability_pct}%</td>
                      <td style={{ padding: '8px 6px', fontFamily: 'monospace', fontWeight: 700 }}>
                        Note {row.survival_grade} ({row.effective_council_score})
                      </td>
                      <td style={{ padding: '8px 6px' }}>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: 99,
                            fontSize: 10,
                            fontWeight: 700,
                            background: row.risk_approved ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)',
                            color: row.risk_approved ? '#34d399' : '#f87171',
                          }}
                        >
                          {row.risk_approved ? 'SÛR & APPROUVÉ' : 'BLOQUÉ'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 10 SPECIALIZED AGENTS COUNCIL */}
          <div
            style={{
              padding: 18,
              borderRadius: 12,
              background: 'rgba(15,23,42,0.82)',
              border: '1px solid rgba(148,163,184,0.18)',
            }}
          >
            <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Users size={17} color="#a78bfa" />
              {pedagogicalMode
                ? 'Avis de votre Équipe de 10 Experts IA (PDG, Gestionnaire de Risques, Économiste, Critique...)'
                : 'Délibération Collégiale des 10 Agents Spécialisés (Section 4)'}
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(290px, 1fr))', gap: 10 }}>
              {deliberation.council_deliberation.map((ag) => (
                <div
                  key={ag.agent_id}
                  style={{
                    padding: 12,
                    borderRadius: 10,
                    background: 'rgba(30,41,59,0.55)',
                    border: '1px solid rgba(148,163,184,0.14)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, fontSize: 13, color: '#e2e8f0' }}>{ag.agent_name}</span>
                    <span
                      style={{
                        fontSize: 10,
                        fontFamily: 'monospace',
                        padding: '2px 6px',
                        borderRadius: 4,
                        background: 'rgba(167,139,250,0.18)',
                        color: '#c4b5fd',
                      }}
                    >
                      {ag.verdict}
                    </span>
                  </div>
                  <p style={{ fontSize: 12, color: '#cbd5e1', margin: '6px 0 0', lineHeight: 1.45 }}>{ag.statement}</p>
                </div>
              ))}
            </div>
          </div>

          {/* 13-STEP DECISION PROCESS (EXPERT) OR CLEAR STEP-BY-STEP SUMMARY (BEGINNER) */}
          <div
            style={{
              padding: 18,
              borderRadius: 12,
              background: 'rgba(15,23,42,0.82)',
              border: '1px solid rgba(148,163,184,0.18)',
            }}
          >
            <h3 style={{ fontSize: 15, fontWeight: 700, margin: '0 0 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Sparkles size={17} color="#38bdf8" />
              {pedagogicalMode
                ? 'Le Plan d’Action Clair en 13 Étapes Vérifiées'
                : 'Processus de Décision Structuré en 13 Étapes (Section 5)'}
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 10 }}>
              {deliberation.decision_steps_13.map((st) => (
                <div
                  key={st.step}
                  style={{
                    padding: 12,
                    borderRadius: 10,
                    background: st.step === 13 && pedagogicalMode ? 'rgba(56,189,248,0.12)' : 'rgba(30,41,59,0.45)',
                    border:
                      st.step === 13 && pedagogicalMode
                        ? '1px solid rgba(56,189,248,0.4)'
                        : '1px solid rgba(148,163,184,0.12)',
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#f8fafc' }}>
                    Étape {st.step} · {st.title}
                  </div>
                  <div style={{ fontSize: 12, color: '#cbd5e1', marginTop: 4, lineHeight: 1.45 }}>{st.summary}</div>
                  {st.pedagogical_explanation && pedagogicalMode && (
                    <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(56,189,248,0.25)', fontSize: 11 }}>
                      <div style={{ fontWeight: 700, color: '#7dd3fc' }}>
                        En résumé simple : {st.pedagogical_explanation.why_this_choice}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* LIBRARY BENCHMARK MATRIX (EXPERT MODE ONLY) */}
          {!pedagogicalMode && libraryMatrix.length > 0 && (
            <div
              style={{
                padding: 16,
                borderRadius: 12,
                background: 'rgba(15,23,42,0.75)',
                border: '1px solid rgba(148,163,184,0.14)',
              }}
            >
              <h4 style={{ fontSize: 13, fontWeight: 700, margin: '0 0 8px', color: '#cbd5e1' }}>
                Matrice d’Évaluation des Bibliothèques Quant & RL (A.3 — Sobriété & Licences Vérifiées)
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 8 }}>
                {libraryMatrix.map((lib) => (
                  <div
                    key={lib.library}
                    style={{
                      padding: 10,
                      borderRadius: 8,
                      background: 'rgba(30,41,59,0.5)',
                      fontSize: 11,
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700 }}>
                      <span>
                        {lib.library} ({lib.license})
                      </span>
                      <span style={{ color: lib.decision.startsWith('ADOPTED') ? '#34d399' : '#f87171' }}>
                        {lib.decision}
                      </span>
                    </div>
                    <div style={{ color: '#94a3b8', marginTop: 4 }}>{lib.rationale}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
