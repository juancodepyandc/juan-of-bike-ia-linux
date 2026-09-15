import { useMemo, useState } from 'react'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Eye,
  Lock,
  Network,
  Share2,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Zap,
} from 'lucide-react'
import {
  computeBlastRadius,
  ENTERPRISE_SYSTEMIC_GRAPH,
  type AttackPath,
  type GraphNode,
} from '../../services/cyber/attackGraphEngine.ts'

const ACCENT = '#F43F5E'
const OK = '#4ADE80'
const WARN = '#F59E0B'
const BLUE = '#60A5FA'

export default function AttackGraphLab() {
  const [selectedNodeId, setSelectedNodeId] = useState<string>('dmz-web')
  const [activePathId, setActivePathId] = useState<string | null>(null)

  const graph = ENTERPRISE_SYSTEMIC_GRAPH

  const selectedNode = useMemo(() => {
    return graph.nodes.find((n) => n.id === selectedNodeId) ?? graph.nodes[0]!
  }, [graph.nodes, selectedNodeId])

  const blastRadius = useMemo(() => {
    return computeBlastRadius(selectedNodeId, graph)
  }, [selectedNodeId, graph])

  const activePath = useMemo<AttackPath | null>(() => {
    if (!activePathId) return null
    return graph.attackPaths.find((p) => p.id === activePathId) ?? null
  }, [activePathId, graph.attackPaths])

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-sky-500/20 text-sky-400 border border-sky-500/30">
              <Share2 size={16} />
            </span>
            <h2 className="text-white text-[16px] font-bold">Graphe d'Attaque Systémique & Connexions</h2>
          </div>
          <p className="text-[12px] text-white/60 mt-1 max-w-2xl">
            Modélisation des chemins de pivot, calcul du rayon d'impact (Blast Radius), et identification des goulets d'étranglement défensifs (Chokepoints).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono px-2.5 py-1 rounded bg-black/40 border border-white/10 text-white/70">
            {graph.nodes.length} Nœuds · {graph.edges.length} Liens · {graph.attackPaths.length} Chemins Critiques
          </span>
        </div>
      </div>

      {/* Main Grid: SVG Graph on Left, Node & Blast Radius Details on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Interactive SVG Network Map */}
        <div className="lg:col-span-8 space-y-3">
          <div className="rounded-xl border border-white/10 bg-black/40 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono uppercase text-white/50 flex items-center gap-1.5">
                <Network size={13} className="text-sky-400" /> Cartographie des flux & Dépendances
              </span>
              <div className="flex items-center gap-2 text-[10px] font-mono">
                <span className="flex items-center gap-1 text-rose-300">
                  <span className="h-2 w-2 rounded-full bg-rose-500" /> Cible Sélectionnée
                </span>
                <span className="flex items-center gap-1 text-amber-300">
                  <span className="h-2 w-2 rounded-full bg-amber-500" /> Blast Radius
                </span>
              </div>
            </div>

            {/* SVG Visualizer Canvas */}
            <div className="relative w-full h-[380px] rounded-lg bg-black/60 border border-white/5 overflow-hidden">
              <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                {/* Edges */}
                {graph.edges.map((edge) => {
                  const src = graph.nodes.find((n) => n.id === edge.source)
                  const dst = graph.nodes.find((n) => n.id === edge.target)
                  if (!src || !dst) return null

                  const isPathActive =
                    activePath &&
                    activePath.steps.includes(edge.source) &&
                    activePath.steps.includes(edge.target)

                  return (
                    <g key={edge.id}>
                      <line
                        x1={`${src.x}%`}
                        y1={`${src.y}%`}
                        x2={`${dst.x}%`}
                        y2={`${dst.y}%`}
                        stroke={isPathActive ? ACCENT : edge.isBlockedByFirewall ? '#334155' : '#475569'}
                        strokeWidth={isPathActive ? '1.5' : '0.8'}
                        strokeDasharray={edge.isBlockedByFirewall ? '2 2' : undefined}
                      />
                      {/* Port Label */}
                      <text
                        x={`${(src.x + dst.x) / 2}%`}
                        y={`${(src.y + dst.y) / 2 - 1}%`}
                        fill="#94a3b8"
                        fontSize="2.5"
                        fontFamily="monospace"
                        textAnchor="middle"
                      >
                        :{edge.port}
                      </text>
                    </g>
                  )
                })}

                {/* Nodes */}
                {graph.nodes.map((node) => {
                  const isSelected = node.id === selectedNodeId
                  const isReachable = blastRadius.reachableNodes.includes(node.id)
                  const isChokepoint = activePath?.chokepointNodeId === node.id

                  let nodeFill = '#1e293b'
                  let nodeStroke = '#64748b'
                  if (isSelected) {
                    nodeFill = '#f43f5e'
                    nodeStroke = '#ffffff'
                  } else if (isReachable) {
                    nodeFill = '#f59e0b'
                    nodeStroke = '#fef08a'
                  } else if (node.type === 'crown-jewel') {
                    nodeFill = '#a855f7'
                    nodeStroke = '#d8b4fe'
                  }

                  return (
                    <g
                      key={node.id}
                      onClick={() => setSelectedNodeId(node.id)}
                      className="cursor-pointer transition-transform hover:scale-110"
                    >
                      <circle
                        cx={`${node.x}%`}
                        cy={`${node.y}%`}
                        r={isSelected ? '3.8' : '3'}
                        fill={nodeFill}
                        stroke={nodeStroke}
                        strokeWidth="0.8"
                      />
                      {isChokepoint && (
                        <circle
                          cx={`${node.x}%`}
                          cy={`${node.y}%`}
                          r="5.5"
                          fill="none"
                          stroke={OK}
                          strokeWidth="0.7"
                          strokeDasharray="1.5 1.5"
                        />
                      )}
                      <text
                        x={`${node.x}%`}
                        y={`${node.y + 5}%`}
                        fill="#f8fafc"
                        fontSize="2.8"
                        fontWeight={isSelected ? 'bold' : 'normal'}
                        textAnchor="middle"
                        fontFamily="sans-serif"
                      >
                        {node.name.split(' ')[0]}
                      </text>
                    </g>
                  )
                })}
              </svg>
            </div>

            {/* Attack Paths Selection Bar */}
            <div className="space-y-1.5 pt-1">
              <span className="text-[11px] font-mono text-white/50">Chemins d'Attaque Détectés :</span>
              <div className="flex flex-wrap gap-2">
                {graph.attackPaths.map((p) => {
                  const active = p.id === activePathId
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setActivePathId(active ? null : p.id)}
                      className={`px-3 py-1.5 rounded-lg text-[11px] font-mono border transition-all cursor-pointer ${
                        active
                          ? 'border-rose-500 bg-rose-500/20 text-rose-200 shadow-md'
                          : 'border-white/10 bg-white/5 text-white/70 hover:bg-white/10'
                      }`}
                    >
                      {p.name} · Impact {p.impactScore}/100
                    </button>
                  )
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Node Details & Blast Radius Calculation */}
        <div className="lg:col-span-4 space-y-3">
          {/* Selected Node Inspector */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono uppercase text-rose-400 font-bold">Nœud Sélectionné</span>
              <span className="text-[10px] font-mono text-white/50">Criticité {selectedNode.criticality}/5</span>
            </div>
            <h3 className="text-[15px] font-bold text-white">{selectedNode.name}</h3>
            <div className="text-[11px] font-mono text-white/60 space-y-1">
              <div>IP : <span className="text-white/90">{selectedNode.ip}</span></div>
              <div>OS : <span className="text-white/90">{selectedNode.os}</span></div>
            </div>

            {/* Vulnerabilities */}
            <div className="space-y-1 pt-1">
              <div className="text-[10.5px] font-mono uppercase text-white/50">Vulnérabilités Identifiées</div>
              {selectedNode.vulnerabilities.length > 0 ? (
                selectedNode.vulnerabilities.map((v, i) => (
                  <div key={i} className="text-[11px] font-mono p-1.5 rounded bg-rose-500/10 border border-rose-500/20 text-rose-200">
                    {v}
                  </div>
                ))
              ) : (
                <div className="text-[11px] font-mono text-white/40">Aucune vulnérabilité directe</div>
              )}
            </div>

            {/* Defense Controls */}
            <div className="space-y-1 pt-1">
              <div className="text-[10.5px] font-mono uppercase text-white/50">Contrôles Défensifs en Place</div>
              {selectedNode.defenseControls.map((d, i) => (
                <div key={i} className="text-[11px] font-mono p-1.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-emerald-200 flex items-center gap-1.5">
                  <ShieldCheck size={12} /> {d}
                </div>
              ))}
            </div>
          </div>

          {/* Blast Radius Calculation Box */}
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[12px] font-semibold text-amber-300 uppercase tracking-wider flex items-center gap-1.5">
                <AlertTriangle size={14} /> Rayon d'Impact (Blast Radius)
              </span>
              <span className="text-[12px] font-mono font-bold text-amber-400">{blastRadius.totalImpact}/100</span>
            </div>
            <p className="text-[11px] text-white/70 leading-relaxed">
              Si ce nœud est compromis, l'attaquant peut atteindre <b>{blastRadius.reachableNodes.length}</b> nœud(s) additionnel(s) par pivot direct sans franchir de pare-feu bloquant.
            </p>

            {blastRadius.highRiskAssets.length > 0 && (
              <div className="pt-1 space-y-1">
                <div className="text-[10px] font-mono uppercase text-rose-400 font-bold">Actifs Critiques Exposés :</div>
                {blastRadius.highRiskAssets.map((asset, i) => (
                  <div key={i} className="text-[11px] font-mono text-rose-200 bg-rose-950/40 p-1.5 rounded border border-rose-500/30">
                    ⚠️ {asset}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
