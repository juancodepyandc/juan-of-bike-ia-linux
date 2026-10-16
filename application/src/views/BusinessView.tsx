import { useCallback, useEffect, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  Award,
  BookOpen,
  Briefcase,
  CheckCircle2,
  Cpu,
  DollarSign,
  FlaskConical,
  Lock,
  Play,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
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

const CAPITAL_PRESETS = [100, 1_000, 10_000, 100_000, 1_000_000]

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
  const [error, setError] = useState<string | null>(null)

  const [quotes, setQuotes] = useState<Record<string, MarketQuote>>({})
  const [strategies, setStrategies] = useState<StrategyArchetype[]>([])
  const [paperPortfolio, setPaperPortfolio] = useState<any>(null)
  const [liveGovernance, setLiveGovernance] = useState<any>(null)
  const [computeGovernor, setComputeGovernor] = useState<any>(null)
  const [libraryMatrix, setLibraryMatrix] = useState<any[]>([])

  const [simulation, setSimulation] = useState<SimulationReport | null>(null)
  const [deliberation, setDeliberation] = useState<CouncilDeliberation | null>(null)
  const [trainingReport, setTrainingReport] = useState<any>(null)

  // Live Viability form state
  const [viabilityInput, setViabilityInput] = useState({
    project_name: 'SaaS Automatisation Comptable & Devis PME',
    unit_price_eur: 89,
    unit_variable_cost_eur: 16,
    monthly_fixed_cost_eur: 320,
    cac_eur: 175,
    monthly_churn_rate: 0.035,
    dso_days: 30,
    expected_monthly_new_customers: 8,
  })
  const [viabilityResult, setViabilityResult] = useState<any>(null)

  const bridgeBase = getBridgeUrl()

  const loadOverview = useCallback(async () => {
    try {
      const resp = await fetch(`${bridgeBase}/api/business/overview`)
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      if (data.ok) {
        setQuotes(data.market?.quotes || {})
        setStrategies(data.strategies || [])
        setPaperPortfolio(data.paper_portfolio || null)
        setLiveGovernance(data.live_governance || null)
        setComputeGovernor(data.compute_governor || null)
        setLibraryMatrix(data.library_evaluation_matrix || [])
      }
    } catch (err: any) {
      setError(err?.message || 'Impossible de joindre le moteur Aurora Business Intelligence.')
    }
  }, [bridgeBase])

  const runCouncilAndSimulation = useCallback(
    async (cap: number, stratId: string, horizon: number, tax: number) => {
      setLoading(true)
      setError(null)
      try {
        const [simResp, delibResp] = await Promise.all([
          fetch(`${bridgeBase}/api/business/lab/simulate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              capital_eur: cap,
              strategy_id: stratId,
              horizon_months: horizon,
              num_simulations: 48,
              tax_rate: tax,
            }),
          }),
          fetch(`${bridgeBase}/api/business/council/deliberate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              capital_eur: cap,
              horizon_months: horizon,
              tax_rate: tax,
              mode: section === 'live' ? 'MODE_2_RECOMMENDATION' : 'LAB_SIMULATION',
            }),
          }),
        ])
        const simData = await simResp.json()
        const delibData = await delibResp.json()
        if (simData.ok) setSimulation(simData.simulation)
        if (delibData.ok) setDeliberation(delibData)
        await loadOverview()
      } catch (err: any) {
        setError(err?.message || 'Erreur lors de la simulation économique.')
      } finally {
        setLoading(false)
      }
    },
    [bridgeBase, loadOverview, section],
  )

  useEffect(() => {
    void loadOverview()
    void runCouncilAndSimulation(10_000, 'hybrid_venture_and_etf', 24, 0.25)
  }, [loadOverview, runCouncilAndSimulation])

  const handleSelectCapital = async (amount: number) => {
    const clean = Math.max(10, amount)
    setCapitalEur(clean)
    setCustomCapitalInput(String(clean))
    await fetch(`${bridgeBase}/api/business/lab/portfolio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ initial_capital_eur: clean, strategy_id: selectedStrategyId }),
    })
    await runCouncilAndSimulation(clean, selectedStrategyId, horizonMonths, taxRate)
  }

  const handleTrainPolicy = async () => {
    setTrainingLoading(true)
    setError(null)
    try {
      const resp = await fetch(`${bridgeBase}/api/business/lab/train`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          capital_eur: capitalEur,
          episodes: 60,
          horizon_months: horizonMonths,
          compute_target: computeGovernor?.recommended_execution_target || 'local_vectorized_walk_forward',
        }),
      })
      const data = await resp.json()
      if (data.ok) {
        setTrainingReport(data)
        await loadOverview()
      }
    } catch (err: any) {
      setError(err?.message || 'Erreur pendant l’entraînement RL.')
    } finally {
      setTrainingLoading(false)
    }
  }

  const handleRunViability = async () => {
    try {
      const resp = await fetch(`${bridgeBase}/api/business/live/viability`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...viabilityInput, capital_eur: capitalEur }),
      })
      const data = await resp.json()
      if (data.ok) {
        setViabilityResult(data)
        await loadOverview()
      }
    } catch (err: any) {
      setError(err?.message || 'Erreur lors du calcul de viabilité.')
    }
  }

  const handleUpdateGovernance = async (patch: Record<string, any>) => {
    try {
      const resp = await fetch(`${bridgeBase}/api/business/live/governance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
      const data = await resp.json()
      if (data.ok) setLiveGovernance(data)
    } catch (err: any) {
      setError(err?.message || 'Erreur de mise à jour de gouvernance.')
    }
  }

  const traj = simulation?.baseline_trajectory?.monthly_trajectory || []

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(180deg, #070b14 0%, #0b1220 100%)',
        color: '#e5edf8',
        padding: '24px 28px 96px',
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
          paddingBottom: 20,
          borderBottom: '1px solid rgba(148,163,184,0.16)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span
              style={{
                padding: '4px 10px',
                borderRadius: 99,
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: '0.08em',
                background: section === 'lab' ? 'rgba(16,185,129,0.18)' : 'rgba(245,158,11,0.2)',
                color: section === 'lab' ? '#34d399' : '#fbbf24',
                border: `1px solid ${section === 'lab' ? 'rgba(52,211,153,0.4)' : 'rgba(251,191,36,0.4)'}`,
              }}
            >
              {section === 'lab'
                ? 'SECTION A · BUSINESS LAB (CAPITAL VIRTUEL · 0 € RÉEL)'
                : 'SECTION B · BUSINESS LIVE (OPÉRATIONS & SURVIE CONTRÔLÉE)'}
            </span>
            <span style={{ fontSize: 12, color: '#94a3b8' }}>
              Conseil 10 Agents · Validation Walk-Forward · Droit de Veto Risk Manager
            </span>
          </div>
          <h1 style={{ fontSize: 26, fontWeight: 700, margin: '8px 0 4px', color: '#f8fafc' }}>
            Aurora Autonomous Business Intelligence
          </h1>
          <p style={{ fontSize: 13, color: '#94a3b8', margin: 0 }}>
            Intelligence économique multi-secteurs : entrepreneuriat numérique (SaaS, B2B, e-commerce), allocation financière,
            préservation de la solvabilité et survie opérationnelle.
          </p>
        </div>

        {/* SECTION SWITCHER & PEDAGOGICAL TOGGLE */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setSection('lab')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 16px',
              borderRadius: 10,
              border: section === 'lab' ? '1px solid #34d399' : '1px solid rgba(148,163,184,0.2)',
              background: section === 'lab' ? 'rgba(16,185,129,0.16)' : 'rgba(15,23,42,0.7)',
              color: section === 'lab' ? '#ecfdf5' : '#94a3b8',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <FlaskConical size={16} />
            Section A · Business Lab
          </button>

          <button
            type="button"
            onClick={() => setSection('live')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 16px',
              borderRadius: 10,
              border: section === 'live' ? '1px solid #fbbf24' : '1px solid rgba(148,163,184,0.2)',
              background: section === 'live' ? 'rgba(245,158,11,0.16)' : 'rgba(15,23,42,0.7)',
              color: section === 'live' ? '#fffbeb' : '#94a3b8',
              fontWeight: 600,
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <Briefcase size={16} />
            Section B · Business Live
          </button>

          <button
            type="button"
            onClick={() => setPedagogicalMode((v) => !v)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '10px 14px',
              borderRadius: 10,
              border: pedagogicalMode ? '1px solid #38bdf8' : '1px solid rgba(148,163,184,0.2)',
              background: pedagogicalMode ? 'rgba(56,189,248,0.14)' : 'rgba(15,23,42,0.7)',
              color: pedagogicalMode ? '#e0f2fe' : '#94a3b8',
              fontSize: 12,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <BookOpen size={15} />
            {pedagogicalMode ? 'Mode Débutant : ACTIF' : 'Mode Débutant : OFF'}
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            marginTop: 16,
            padding: '12px 16px',
            borderRadius: 10,
            background: 'rgba(239,68,68,0.15)',
            border: '1px solid rgba(239,68,68,0.4)',
            color: '#fecaca',
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {/* LIVE MARKET & MACRO TICKER STRIP */}
      <div
        style={{
          marginTop: 18,
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(195px, 1fr))',
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
                background: 'rgba(15,23,42,0.75)',
                border: '1px solid rgba(148,163,184,0.14)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11 }}>
                <span style={{ fontWeight: 700, color: '#cbd5e1' }}>{q.symbol}</span>
                <span
                  style={{
                    padding: '1px 6px',
                    borderRadius: 4,
                    fontSize: 9,
                    background:
                      q.data_origin === 'REALTIME_PUBLIC_FEED' ? 'rgba(16,185,129,0.2)' : 'rgba(148,163,184,0.15)',
                    color: q.data_origin === 'REALTIME_PUBLIC_FEED' ? '#34d399' : '#94a3b8',
                  }}
                >
                  {q.data_origin === 'REALTIME_PUBLIC_FEED' ? 'LIVE API' : 'VÉRIFIÉ'}
                </span>
              </div>
              <div style={{ fontSize: 12, color: '#94a3b8', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {q.name}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginTop: 4 }}>
                <span style={{ fontSize: 15, fontWeight: 700, fontFamily: 'monospace' }}>
                  {q.price.toLocaleString('fr-FR')} {q.currency}
                </span>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
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

      {/* ==================================================================== */}
      {/* SECTION A — AURORA BUSINESS LAB                                      */}
      {/* ==================================================================== */}
      {section === 'lab' && (
        <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 20 }}>
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
                  A.1 Capital Virtuel Initial & Paramètres du Simulateur Économique
                </h2>
                <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 0' }}>
                  Choisissez un capital fictif : AuroraIA compare la création d’entreprise (SaaS, B2B, e-commerce),
                  l’investissement financier et la réserve de liquidités. Aucun argent réel ne peut être dépensé.
                </p>
              </div>
              <button
                type="button"
                disabled={loading}
                onClick={() => runCouncilAndSimulation(capitalEur, selectedStrategyId, horizonMonths, taxRate)}
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
                {loading ? 'Simulation en cours...' : 'Simuler & Délibérer (13 étapes)'}
              </button>
            </div>

            {/* CAPITAL PRESETS */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 14, alignItems: 'center' }}>
              {CAPITAL_PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => handleSelectCapital(preset)}
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
                <span style={{ fontSize: 12, color: '#94a3b8' }}>Montant personnalisé (€) :</span>
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
                  onClick={() => handleSelectCapital(Number(customCapitalInput) || 10_000)}
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
                  Appliquer
                </button>
              </div>
            </div>

            {/* STRATEGY & HORIZON CONTROLS */}
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
                  Stratégie testée dans le Simulateur
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
                  Horizon temporel : {horizonMonths} mois ({(horizonMonths / 12).toFixed(1)} ans)
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
            </div>
          </div>

          {/* A.2 & A.4 SIMULATION METRICS, WALK-FORWARD & RISK MANAGER VERDICT */}
          {simulation && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
              <div style={{ padding: 16, borderRadius: 12, background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(148,163,184,0.16)' }}>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>Capital Final Réel Médian (Net d’Inflation & Impôts)</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: '#34d399', marginTop: 4, fontFamily: 'monospace' }}>
                  {simulation.monte_carlo.median_final_real_equity_eur.toLocaleString('fr-FR')} €
                </div>
                <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                  IC 95% : [{simulation.monte_carlo.ci_95_low_equity_eur.toLocaleString('fr-FR')} € ;{' '}
                  {simulation.monte_carlo.ci_95_high_equity_eur.toLocaleString('fr-FR')} €]
                </div>
              </div>

              <div style={{ padding: 16, borderRadius: 12, background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(148,163,184,0.16)' }}>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>CAGR Réel Médian & Ratio de Sortino</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: '#38bdf8', marginTop: 4, fontFamily: 'monospace' }}>
                  {simulation.monte_carlo.median_real_cagr_pct >= 0 ? '+' : ''}
                  {simulation.monte_carlo.median_real_cagr_pct}% / an
                </div>
                <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                  Sortino : {simulation.monte_carlo.median_sortino_ratio} · Walk-Forward Test :{' '}
                  {simulation.walk_forward_validation.unseen_test_real_cagr_pct}%
                </div>
              </div>

              <div style={{ padding: 16, borderRadius: 12, background: 'rgba(15,23,42,0.8)', border: '1px solid rgba(148,163,184,0.16)' }}>
                <div style={{ fontSize: 11, color: '#94a3b8' }}>Probabilité de Ruine & Drawdown P90</div>
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 700,
                    color: simulation.monte_carlo.ruin_probability_pct <= 2.0 ? '#34d399' : '#f87171',
                    marginTop: 4,
                    fontFamily: 'monospace',
                  }}
                >
                  Ruine : {simulation.monte_carlo.ruin_probability_pct}%
                </div>
                <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                  Max Drawdown P90 : -{simulation.monte_carlo.p90_max_drawdown_pct}% · Réserve :{' '}
                  {(simulation.risk_manager_verdict.cash_reserve_ratio * 100).toFixed(0)}%
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
                  Verdict Indépendant Risk Manager
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4 }}>
                  {simulation.risk_manager_verdict.approved ? 'SURVIE VALIDÉE' : 'VETO BLOQUANT'} (Grade{' '}
                  {simulation.reward_evaluation.survival_grade})
                </div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                  Score récompense survie : {simulation.reward_evaluation.total_reward} · Risque :{' '}
                  {simulation.risk_manager_verdict.risk_score_0_100}/100
                </div>
              </div>
            </div>
          )}

          {/* MONTHLY TRAJECTORY & ECONOMIC FRICTIONS */}
          {simulation && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '2fr 1fr',
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
                  Trajectoire Mensuelle Simulée (Nominal vs Réel Ajusté de l’Inflation & Trésorerie Liquide)
                </h3>
                <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 140, padding: '8px 0' }}>
                  {traj.map((pt) => {
                    const maxEq = Math.max(...traj.map((t) => t.nominal_equity_eur), capitalEur * 1.2)
                    const hReal = Math.max(8, Math.round((pt.real_equity_eur / maxEq) * 125))
                    const hCash = Math.max(4, Math.round((pt.liquid_cash_eur / maxEq) * 125))
                    return (
                      <div
                        key={pt.month}
                        title={`Mois ${pt.month} | Réel: ${pt.real_equity_eur} € | Cash: ${pt.liquid_cash_eur} € | MRR: ${pt.mrr_eur} € | DD: -${pt.drawdown_pct}%`}
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

              {/* FRICTIONS BREAKDOWN */}
              <div
                style={{
                  padding: 18,
                  borderRadius: 12,
                  background: 'rgba(15,23,42,0.82)',
                  border: '1px solid rgba(148,163,184,0.16)',
                }}
              >
                <h3 style={{ fontSize: 14, fontWeight: 700, margin: '0 0 12px' }}>
                  Frictions Réelles Modélisées (A.2)
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>Impôts payés (IS/Plus-values) :</span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {simulation.baseline_trajectory.frictions_summary.cumulative_taxes_paid_eur.toLocaleString('fr-FR')} €
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>Commissions, Spreads & Slippage :</span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {simulation.baseline_trajectory.frictions_summary.cumulative_commissions_and_slippage_eur.toLocaleString('fr-FR')} €
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>Défauts de contrepartie / Impayés :</span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {simulation.baseline_trajectory.frictions_summary.cumulative_bad_debt_losses_eur.toLocaleString('fr-FR')} €
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>Délai paiement client (DSO BFR) :</span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {simulation.baseline_trajectory.frictions_summary.dso_payment_delay_days} jours
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>Inflation annuelle appliquée :</span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                      {simulation.baseline_trajectory.frictions_summary.annual_inflation_pct}% / an
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: '#94a3b8' }}>Détection Anti-Martingale :</span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#34d399' }}>
                      {simulation.risk_manager_verdict.martingale_detected ? 'ALERTE MARTINGALE' : 'Sain (0 doublement)'}
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
                  A.3 & Section 6 · Infrastructure d’Entraînement RL & Gouverneur de Quotas Kaggle / Google Colab
                </h3>
                <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 0' }}>
                  Skill actif : <code>kaggle-colab-compute-governor</code> · Notebook reproductible :{' '}
                  <code>notebooks/aurora_business_rl_training.ipynb</code> · Porte de promotion avec rollback automatique.
                </p>
              </div>
              <button
                type="button"
                disabled={trainingLoading}
                onClick={handleTrainPolicy}
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
                {trainingLoading ? 'Entraînement RL en cours...' : 'Lancer Entraînement RL & Validation Walk-Forward'}
              </button>
            </div>

            {computeGovernor && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10, marginTop: 12 }}>
                <div style={{ padding: 12, borderRadius: 8, background: 'rgba(30,41,59,0.6)', fontSize: 12 }}>
                  <div style={{ color: '#94a3b8' }}>Statut API Kaggle & Quotas</div>
                  <div style={{ fontWeight: 700, marginTop: 4 }}>
                    {computeGovernor.kaggle?.credentials_configured
                      ? `Connecté (${computeGovernor.kaggle.username}) · Quota 30h/sem GPU`
                      : 'Clé ~/.kaggle/kaggle.json absente · Repli Local + Export Notebook'}
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
                  Entraînement terminé ({trainingReport.episodes_trained} épisodes en {trainingReport.elapsed_ms} ms) — Meilleure
                  politique apprise : {trainingReport.learned_best_strategy_name}
                </div>
                <div style={{ marginTop: 4, color: '#cbd5e1' }}>
                  Porte de promotion Auditor Agent :{' '}
                  <strong>{trainingReport.promotion_gate?.promoted ? 'PROMU EN PRODUCTION LAB' : 'MAINTIEN VERSION PRÉCÉDENTE (ROLLBACK)'}</strong>{' '}
                  (Reward validation : {trainingReport.promotion_gate?.validation_reward}, Ruine :{' '}
                  {trainingReport.promotion_gate?.ruin_prob_pct}%, Test jamais vu :{' '}
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
        <div style={{ marginTop: 22, display: 'flex', flexDirection: 'column', gap: 20 }}>
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
                  B.1 & B.3 Gouvernance Business Live, Readiness Gate & Arrêt d’Urgence
                </h2>
                <p style={{ fontSize: 12, color: '#94a3b8', margin: '4px 0 0' }}>
                  Aucun paiement, contrat, emprunt ou engagement externe n’est exécuté sans validation humaine explicite.
                </p>
              </div>

              <button
                type="button"
                onClick={() =>
                  handleUpdateGovernance({
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
                  ? 'ARRÊT D’URGENCE ACTIF (Cliquer pour réarmer)'
                  : 'ARRÊT D’URGENCE IMMÉDIAT (KILL-SWITCH)'}
              </button>
            </div>

            {/* 4 MODES D'ACTIVATION */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 10, marginTop: 14 }}>
              {[
                { id: 'MODE_1_OBSERVATION', label: 'Mode 1 · Observation', desc: 'Lecture seule, veille marché & détection d’écarts' },
                { id: 'MODE_2_RECOMMENDATION', label: 'Mode 2 · Recommandation', desc: 'Propositions chiffrées 13 étapes sans exécution' },
                { id: 'MODE_3_ASSISTED', label: 'Mode 3 · Exécution Assistée', desc: 'Prépare les plans d’action soumis à signature humaine' },
                { id: 'MODE_4_SUPERVISED_AUTONOMOUS', label: 'Mode 4 · Autonomie Supervisée', desc: 'Veille & tests bornés sous plafonds de survie' },
              ].map((m) => {
                const active = liveGovernance?.governance?.operational_mode === m.id
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => handleUpdateGovernance({ operational_mode: m.id })}
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

          {/* B.2 ÉTUDE DE VIABILITÉ OPÉRATIONNELLE & DÉTECTION D'ANOMALIES */}
          <div
            style={{
              padding: 20,
              borderRadius: 14,
              background: 'rgba(15,23,42,0.82)',
              border: '1px solid rgba(148,163,184,0.2)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                <Activity size={17} color="#fbbf24" />
                B.2 Calculateur d’Économie Unitaire (LTV/CAC, DSO, Point Mort) & Détecteur d’Anomalies de Coûts
              </h3>
              <button
                type="button"
                onClick={handleRunViability}
                style={{
                  padding: '8px 16px',
                  borderRadius: 8,
                  background: '#fbbf24',
                  color: '#451a03',
                  fontWeight: 700,
                  fontSize: 12,
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                Analyser la Viabilité & les Risques
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 10, marginTop: 12 }}>
              <div>
                <label style={{ fontSize: 11, color: '#94a3b8' }}>Prix unitaire / mois (€)</label>
                <input
                  type="number"
                  value={viabilityInput.unit_price_eur}
                  onChange={(e) => setViabilityInput({ ...viabilityInput, unit_price_eur: Number(e.target.value) })}
                  style={{ width: '100%', padding: 7, borderRadius: 6, background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: '#94a3b8' }}>Coût variable unitaire (€)</label>
                <input
                  type="number"
                  value={viabilityInput.unit_variable_cost_eur}
                  onChange={(e) => setViabilityInput({ ...viabilityInput, unit_variable_cost_eur: Number(e.target.value) })}
                  style={{ width: '100%', padding: 7, borderRadius: 6, background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: '#94a3b8' }}>Coûts fixes / mois (€)</label>
                <input
                  type="number"
                  value={viabilityInput.monthly_fixed_cost_eur}
                  onChange={(e) => setViabilityInput({ ...viabilityInput, monthly_fixed_cost_eur: Number(e.target.value) })}
                  style={{ width: '100%', padding: 7, borderRadius: 6, background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: '#94a3b8' }}>CAC par client (€)</label>
                <input
                  type="number"
                  value={viabilityInput.cac_eur}
                  onChange={(e) => setViabilityInput({ ...viabilityInput, cac_eur: Number(e.target.value) })}
                  style={{ width: '100%', padding: 7, borderRadius: 6, background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
                />
              </div>
              <div>
                <label style={{ fontSize: 11, color: '#94a3b8' }}>Délai paiement DSO (jours)</label>
                <input
                  type="number"
                  value={viabilityInput.dso_days}
                  onChange={(e) => setViabilityInput({ ...viabilityInput, dso_days: Number(e.target.value) })}
                  style={{ width: '100%', padding: 7, borderRadius: 6, background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
                />
              </div>
            </div>

            {viabilityResult && (
              <div style={{ marginTop: 14, padding: 14, borderRadius: 10, background: 'rgba(30,41,59,0.65)', fontSize: 12 }}>
                <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', fontWeight: 700 }}>
                  <span>Marge brute : {viabilityResult.unit_economics.gross_margin_pct}%</span>
                  <span>Ratio LTV/CAC : {viabilityResult.unit_economics.ltv_to_cac_ratio}x</span>
                  <span>Payback CAC : {viabilityResult.unit_economics.cac_payback_months} mois</span>
                  <span>Seuil de rentabilité : {viabilityResult.unit_economics.break_even_active_customers} clients actifs</span>
                  <span>BFR (décalage DSO) : {viabilityResult.unit_economics.dso_working_capital_gap_eur} €</span>
                </div>
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
      {/* SHARED CORE — 10-AGENT COUNCIL & 13-STEP DECISION REPORT             */}
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
              Comparaison Multi-Secteurs pour {deliberation.capital_eur.toLocaleString('fr-FR')} € (Entrepreneuriat vs Finance vs Inactivité Stratégique)
            </h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(148,163,184,0.2)', color: '#94a3b8', textAlign: 'left' }}>
                    <th style={{ padding: '8px 6px' }}>Rang</th>
                    <th style={{ padding: '8px 6px' }}>Stratégie / Modèle Économique</th>
                    <th style={{ padding: '8px 6px' }}>Catégorie</th>
                    <th style={{ padding: '8px 6px' }}>CAGR Réel Médian</th>
                    <th style={{ padding: '8px 6px' }}>Drawdown P90</th>
                    <th style={{ padding: '8px 6px' }}>Risque Ruine</th>
                    <th style={{ padding: '8px 6px' }}>Score Survie</th>
                    <th style={{ padding: '8px 6px' }}>Risk Manager</th>
                  </tr>
                </thead>
                <tbody>
                  {deliberation.all_ranked_strategies.map((row) => (
                    <tr
                      key={row.strategy_id}
                      style={{
                        borderBottom: '1px solid rgba(148,163,184,0.08)',
                        background:
                          row.strategy_id === deliberation.selected_strategy.strategy_id
                            ? 'rgba(16,185,129,0.1)'
                            : 'transparent',
                      }}
                    >
                      <td style={{ padding: '8px 6px', fontWeight: 700 }}>#{row.rank}</td>
                      <td style={{ padding: '8px 6px', fontWeight: 600 }}>{row.strategy_name}</td>
                      <td style={{ padding: '8px 6px', color: '#94a3b8' }}>{row.category}</td>
                      <td style={{ padding: '8px 6px', fontFamily: 'monospace', color: '#38bdf8' }}>
                        {row.median_real_cagr_pct}%/an
                      </td>
                      <td style={{ padding: '8px 6px', fontFamily: 'monospace' }}>-{row.p90_max_drawdown_pct}%</td>
                      <td style={{ padding: '8px 6px', fontFamily: 'monospace' }}>{row.ruin_probability_pct}%</td>
                      <td style={{ padding: '8px 6px', fontFamily: 'monospace', fontWeight: 700 }}>
                        {row.effective_council_score} ({row.survival_grade})
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
                          {row.risk_approved ? 'APPROUVÉ' : 'VETO'}
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
              Délibération Collégiale des 10 Agents Spécialisés (Section 4)
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

          {/* 13-STEP DECISION PROCESS & BEGINNER PEDAGOGICAL SUMMARY */}
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
              Processus de Décision Structuré en 13 Étapes (Section 5)
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
                        Explication Débutant : {st.pedagogical_explanation.why_this_choice}
                      </div>
                      <ul style={{ margin: '6px 0 0', paddingLeft: 16, color: '#bae6fd' }}>
                        {st.pedagogical_explanation.glossary.map((g) => (
                          <li key={g.term}>
                            <strong>{g.term} :</strong> {g.explanation}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* LIBRARY BENCHMARK MATRIX (SECTION A.3) */}
          {libraryMatrix.length > 0 && (
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
