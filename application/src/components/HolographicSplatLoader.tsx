import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  Box,
  CheckCircle2,
  Clock,
  Cpu,
  Layers,
  Minimize2,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Wrench,
} from 'lucide-react';
import {
  computeLiveMissionTiming,
  computeSubAgentsForProgress,
  formatDurationShort,
  generateHolographicSplats,
  LiveEngineeringTelemetryInput,
  readPersistedThreeDMission,
} from '../services/threeDSubAgentsOrchestrator';

export interface HolographicSplatLoaderProps {
  active?: boolean;
  prompt: string;
  progressPercent?: number;
  phasePercent?: number;
  phaseDetail?: string;
  phaseLabel?: string;
  startedAtMs?: number;
  serverElapsedSeconds?: number | null;
  serverRemainingSeconds?: number | null;
  stlCount?: number;
  verifiedCriteriaCount?: number;
  totalCriteriaCount?: number;
  referenceImageUrl?: string | null;
  mode?: 'visual_3d' | 'engineering_cad' | 'mesh_3d';
  compact?: boolean;
  liveTelemetry?: LiveEngineeringTelemetryInput;
  onMinimize?: () => void;
  onStop?: () => void;
}

export const HolographicSplatLoader: React.FC<HolographicSplatLoaderProps> = ({
  prompt,
  progressPercent,
  phasePercent = 0,
  phaseDetail = '',
  phaseLabel = '',
  startedAtMs,
  serverElapsedSeconds = null,
  serverRemainingSeconds = null,
  stlCount,
  verifiedCriteriaCount,
  totalCriteriaCount,
  mode = 'visual_3d',
  compact = false,
  liveTelemetry,
  onMinimize,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [nowTick, setNowTick] = useState<number>(() => Date.now());
  const [viewMode, setViewMode] = useState<'splats' | 'kinematics' | 'blueprint'>('splats');
  const [selectedAgentIdx, setSelectedAgentIdx] = useState<number | null>(null);
  const [cameraYaw, setCameraYaw] = useState<number>(0.45);
  const [cameraPitch, setCameraPitch] = useState<number>(0.22);
  const isDraggingRef = useRef(false);
  const lastMouseRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  const persisted = useMemo(() => readPersistedThreeDMission(), [nowTick]);
  const effectivePrompt = (prompt || persisted?.rawPrompt || 'Projet 3D & Assemblage').trim();
  const effectiveStartedAt = startedAtMs || persisted?.startedAtMs || Date.now();
  const resolvedInputPct = progressPercent ?? phasePercent ?? 0;
  const rawPct = resolvedInputPct > 0 ? resolvedInputPct : persisted?.progressPercent || 6;
  const resolvedPhaseText = phaseDetail || phaseLabel || persisted?.phaseDetail || '';
  const mergedTelemetry = useMemo<LiveEngineeringTelemetryInput | undefined>(
    () =>
      liveTelemetry || {
        stlCount: stlCount ?? persisted?.stlCount,
        verifiedCount: verifiedCriteriaCount ?? persisted?.verifiedCriteriaCount,
        criteriaCount: totalCriteriaCount ?? persisted?.totalCriteriaCount,
      },
    [liveTelemetry, stlCount, verifiedCriteriaCount, totalCriteriaCount, persisted],
  );

  // Horloge locale 1s infigeable
  useEffect(() => {
    const id = window.setInterval(() => {
      setNowTick(Date.now());
    }, 1000);
    return () => window.clearInterval(id);
  }, []);

  const timing = useMemo(
    () =>
      computeLiveMissionTiming(
        effectiveStartedAt,
        rawPct,
        mode === 'engineering_cad' ? 210 : 165,
        serverElapsedSeconds,
        serverRemainingSeconds,
      ),
    [effectiveStartedAt, rawPct, mode, serverElapsedSeconds, serverRemainingSeconds, nowTick],
  );

  const subAgents = useMemo(
    () =>
      computeSubAgentsForProgress(
        effectivePrompt,
        timing.effectivePercent,
        resolvedPhaseText,
        mode,
        mergedTelemetry,
      ),
    [effectivePrompt, timing.effectivePercent, resolvedPhaseText, mode, mergedTelemetry],
  );

  const activeAgentIndex = useMemo(() => {
    const idx = subAgents.findIndex((a) => a.status === 'running');
    if (idx >= 0) return idx;
    const doneCount = subAgents.filter((a) => a.status === 'done').length;
    return Math.min(subAgents.length - 1, Math.max(0, doneCount - 1));
  }, [subAgents]);

  const displayedAgent = subAgents[selectedAgentIdx ?? activeAgentIndex] || subAgents[0];

  const livePartsSignature = useMemo(() => {
    const pts = liveTelemetry?.parts || [];
    return pts.map((p) => `${p.id}:${p.dimensions_mm?.join('x') || ''}:${p.sample_points_mm?.length || 0}`).join('|');
  }, [liveTelemetry?.parts]);

  const splats = useMemo(
    () =>
      generateHolographicSplats(
        effectivePrompt,
        compact ? 850 : 1500,
        liveTelemetry?.parts,
        liveTelemetry?.joints,
        liveTelemetry?.usableBedMm || [220, 220, 250],
      ),
    [effectivePrompt, compact, livePartsSignature, liveTelemetry?.joints?.length],
  );

  const hasRealStlGeometry = Boolean(liveTelemetry?.parts && liveTelemetry.parts.length > 0);

  // Boucle de rendu 60 FPS du nuage de Splats Gaussiens 3D & Squelette Cinématique
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let rafId = 0;
    let startTime = performance.now();

    const render = (now: number) => {
      const dt = (now - startTime) * 0.001;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = canvas.getBoundingClientRect();
      const width = Math.max(240, Math.floor(rect.width));
      const height = Math.max(180, Math.floor(rect.height));

      if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
        canvas.width = width * dpr;
        canvas.height = height * dpr;
      }

      ctx.save();
      ctx.scale(dpr, dpr);

      // Fond studio CAO profond
      const bgGrad = ctx.createRadialGradient(
        width * 0.5,
        height * 0.48,
        10,
        width * 0.5,
        height * 0.5,
        Math.max(width, height) * 0.72,
      );
      bgGrad.addColorStop(0, '#0f172a');
      bgGrad.addColorStop(0.55, '#070b14');
      bgGrad.addColorStop(1, '#030509');
      ctx.fillStyle = bgGrad;
      ctx.fillRect(0, 0, width, height);

      const cx = width * 0.5;
      const cy = height * 0.52;
      const scale = Math.min(width, height) * 0.44;

      const autoYaw = isDraggingRef.current ? cameraYaw : cameraYaw + dt * 0.35;
      const cosY = Math.cos(autoYaw);
      const sinY = Math.sin(autoYaw);
      const cosP = Math.cos(cameraPitch);
      const sinP = Math.sin(cameraPitch);

      const project = (x: number, y: number, z: number) => {
        const x1 = x * cosY - z * sinY;
        const z1 = x * sinY + z * cosY;
        const y2 = y * cosP - z1 * sinP;
        const z2 = y * sinP + z1 * cosP;
        const fov = 2.6 / Math.max(0.8, 2.6 + z2);
        return {
          sx: cx + x1 * scale * fov,
          sy: cy + y2 * scale * fov,
          depth: z2,
          fov,
        };
      };

      // Plateau millimétré CAO 3D
      ctx.lineWidth = 1;
      const gridY = 0.68;
      for (let g = -6; g <= 6; g++) {
        const t = g * 0.16;
        const p1 = project(t, gridY, -0.96);
        const p2 = project(t, gridY, 0.96);
        ctx.strokeStyle = g === 0 ? 'rgba(56, 189, 248, 0.32)' : 'rgba(56, 189, 248, 0.09)';
        ctx.beginPath();
        ctx.moveTo(p1.sx, p1.sy);
        ctx.lineTo(p2.sx, p2.sy);
        ctx.stroke();

        const q1 = project(-0.96, gridY, t);
        const q2 = project(0.96, gridY, t);
        ctx.beginPath();
        ctx.moveTo(q1.sx, q1.sy);
        ctx.lineTo(q2.sx, q2.sy);
        ctx.stroke();
      }

      // Plan de balayage laser de solidification lié à la progression réelle
      const scanNorm = (timing.effectivePercent % 100) / 100;
      const scanWave = Math.sin(dt * 1.9) * 0.52;
      const solidifyThresholdY = 0.72 - scanNorm * 1.44;

      // 1. Projection & tri en profondeur des Splats Gaussiens 3D
      const projectedSplats: Array<{
        sx: number;
        sy: number;
        depth: number;
        fov: number;
        rx: number;
        ry: number;
        color: [number, number, number];
        alpha: number;
        isJointNode?: boolean;
        partLabel?: string;
        solidified: boolean;
      }> = [];

      const jointNodes: Array<{
        sx: number;
        sy: number;
        depth: number;
        group: number;
        label?: string;
        color: [number, number, number];
      }> = [];

      for (let i = 0; i < splats.length; i++) {
        const sp = splats[i];
        // Légère respiration d'assemblage éclaté -> assemblé au fur et à mesure que la progression tend vers 100 %
        const assemblyConvergence = Math.max(0, 1 - timing.effectivePercent / 100) * 0.12;
        const pulse = 1 + Math.sin(dt * 1.8 + sp.group * 1.1) * assemblyConvergence;

        const px = sp.x * pulse;
        const py = sp.y * pulse;
        const pz = sp.z * pulse;

        const proj = project(px, py, pz);
        const distToScan = Math.abs(py - scanWave);
        const scanBoost = distToScan < 0.09 ? (1 - distToScan / 0.09) * 0.5 : 0;
        const solidified = py >= solidifyThresholdY;

        if (sp.isJointNode) {
          jointNodes.push({
            sx: proj.sx,
            sy: proj.sy,
            depth: proj.depth,
            group: sp.group,
            label: sp.partLabel,
            color: sp.color,
          });
        }

        projectedSplats.push({
          sx: proj.sx,
          sy: proj.sy,
          depth: proj.depth,
          fov: proj.fov,
          rx: sp.rx * scale * proj.fov * (solidified ? 1.1 : 0.88),
          ry: sp.ry * scale * proj.fov * (solidified ? 1.1 : 0.88),
          color: sp.color,
          alpha: Math.min(1, sp.alpha * (solidified ? 0.92 : 0.42) + scanBoost),
          isJointNode: sp.isJointNode,
          partLabel: sp.partLabel,
          solidified,
        });
      }

      projectedSplats.sort((a, b) => b.depth - a.depth);

      // 2. Rendu des Splats Gaussiens anisotropes
      if (viewMode === 'splats' || viewMode === 'kinematics') {
        for (let i = 0; i < projectedSplats.length; i++) {
          const p = projectedSplats[i];
          if (viewMode === 'kinematics' && !p.isJointNode && i % 3 !== 0) continue;

          const [r, g, b] = p.color;
          const radius = Math.max(1.5, Math.max(p.rx, p.ry));

          if (p.isJointNode) {
            ctx.fillStyle = `rgba(255, 255, 255, 0.95)`;
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, Math.max(3.5, radius * 0.55), 0, Math.PI * 2);
            ctx.fill();

            ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.9)`;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, Math.max(7, radius * 1.15), 0, Math.PI * 2);
            ctx.stroke();
          } else {
            ctx.fillStyle = p.solidified
              ? `rgba(${r}, ${g}, ${b}, ${p.alpha.toFixed(3)})`
              : `rgba(${Math.min(255, r + 35)}, ${Math.min(255, g + 45)}, 255, ${(p.alpha * 0.58).toFixed(3)})`;
            ctx.beginPath();
            ctx.ellipse(
              p.sx,
              p.sy,
              Math.max(1.3, p.rx),
              Math.max(1.0, p.ry),
              (i % 7) * 0.45,
              0,
              Math.PI * 2,
            );
            ctx.fill();
          }
        }
      }

      // 3. Mode Blueprint / Squelette : Liaisons inter-pièces et étiquettes dimensionnelles réelles
      if (viewMode === 'kinematics' || viewMode === 'blueprint') {
        ctx.lineWidth = 1.4;
        for (let i = 0; i < jointNodes.length; i++) {
          const a = jointNodes[i];
          for (let j = i + 1; j < jointNodes.length; j++) {
            const b = jointNodes[j];
            const dist = Math.hypot(a.sx - b.sx, a.sy - b.sy);
            if (dist < scale * 0.85) {
              ctx.strokeStyle =
                viewMode === 'blueprint' ? 'rgba(52, 211, 153, 0.48)' : 'rgba(56, 189, 248, 0.42)';
              ctx.beginPath();
              ctx.moveTo(a.sx, a.sy);
              ctx.lineTo(b.sx, b.sy);
              ctx.stroke();
            }
          }
        }

        // Étiquettes des vraies pièces / articulations
        ctx.font = '600 10px ui-monospace, SFMono-Regular, Menlo, monospace';
        jointNodes.slice(0, 8).forEach((node) => {
          if (!node.label) return;
          ctx.fillStyle = 'rgba(15, 23, 42, 0.82)';
          const w = ctx.measureText(node.label).width + 10;
          ctx.fillRect(node.sx + 8, node.sy - 10, w, 16);
          ctx.strokeStyle = `rgba(${node.color[0]}, ${node.color[1]}, ${node.color[2]}, 0.65)`;
          ctx.strokeRect(node.sx + 8, node.sy - 10, w, 16);
          ctx.fillStyle = '#e2e8f0';
          ctx.fillText(node.label, node.sx + 13, node.sy + 1);
        });
      }

      // 4. Anneau laser de scan CAO
      const scanP1 = project(-0.68, scanWave, -0.68);
      const scanP2 = project(0.68, scanWave, -0.68);
      const scanP3 = project(0.68, scanWave, 0.68);
      const scanP4 = project(-0.68, scanWave, 0.68);

      ctx.strokeStyle = 'rgba(56, 189, 248, 0.55)';
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(scanP1.sx, scanP1.sy);
      ctx.lineTo(scanP2.sx, scanP2.sy);
      ctx.lineTo(scanP3.sx, scanP3.sy);
      ctx.lineTo(scanP4.sx, scanP4.sy);
      ctx.closePath();
      ctx.stroke();

      // 5. HUD télémétrique sur le canvas
      ctx.font = '600 10px ui-monospace, SFMono-Regular, Menlo, monospace';
      ctx.fillStyle = 'rgba(148, 163, 184, 0.88)';
      ctx.fillText(
        hasRealStlGeometry
          ? `GÉOMÉTRIE STL EN DIRECT : ${liveTelemetry?.parts?.length || 0} PIÈCE(S) · ${splats.length} SPLATS`
          : `SYNTHÈSE VOLUMÉTRIQUE : ${splats.length} SPLATS 3D`,
        14,
        22,
      );
      ctx.fillStyle = 'rgba(56, 189, 248, 0.92)';
      ctx.fillText(
        `AGENT ACTIF [${activeAgentIndex + 1}/5] : ${displayedAgent.code} · SOLIDIFICATION ${timing.effectivePercent}%`,
        14,
        36,
      );

      ctx.restore();
      rafId = window.requestAnimationFrame(render);
    };

    rafId = window.requestAnimationFrame(render);
    return () => window.cancelAnimationFrame(rafId);
  }, [splats, viewMode, timing.effectivePercent, activeAgentIndex, displayedAgent.code, cameraYaw, cameraPitch, hasRealStlGeometry, liveTelemetry?.parts?.length]);

  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    isDraggingRef.current = true;
    lastMouseRef.current = { x: e.clientX, y: e.clientY };
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - lastMouseRef.current.x;
    const dy = e.clientY - lastMouseRef.current.y;
    lastMouseRef.current = { x: e.clientX, y: e.clientY };
    setCameraYaw((prev) => prev + dx * 0.008);
    setCameraPitch((prev) => Math.max(-0.85, Math.min(0.85, prev + dy * 0.008)));
  };

  const handlePointerUp = () => {
    isDraggingRef.current = false;
  };

  return (
    <div className="w-full rounded-2xl border border-cyan-500/25 bg-[#070b14]/95 text-slate-100 shadow-[0_20px_70px_rgba(0,0,0,0.75)] overflow-hidden backdrop-blur-xl">
      {/* Barre supérieure : Statut live, Chronomètre infigeable, ETA restant et contrôles */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 border-b border-white/10 bg-gradient-to-r from-cyan-500/10 via-indigo-500/10 to-emerald-500/10">
        <div className="flex items-center gap-3 min-w-0">
          <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-cyan-500/15 border border-cyan-400/35">
            <Sparkles className="w-4 h-4 text-cyan-300 animate-spin" style={{ animationDuration: '5s' }} />
            <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
            </span>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-bold uppercase tracking-wider text-cyan-300">
                {mode === 'engineering_cad'
                  ? 'Orchestration CAO & Assemblage Multi-Agents'
                  : 'Reconstruction Holographique 3D Multi-Agents'}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-400/30">
                Étape {activeAgentIndex + 1} / {subAgents.length}
              </span>
              {hasRealStlGeometry && (
                <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-cyan-500/20 text-cyan-200 border border-cyan-400/40">
                  {liveTelemetry?.parts?.length} STL mesuré(s) en direct
                </span>
              )}
            </div>
            <p className="text-xs text-slate-300 truncate max-w-xl" title={effectivePrompt}>
              {phaseDetail || displayedAgent.currentAction}
            </p>
          </div>
        </div>

        {/* Chronomètre temps réel (jamais figé) + Temps restant estimé + % */}
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-900/90 border border-white/10 text-xs">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-slate-400">Écoulé :</span>
            <span className="font-mono font-bold text-white tabular-nums">
              {formatDurationShort(timing.elapsedSeconds)}
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-900/90 border border-cyan-500/25 text-xs">
            <Activity className="w-3.5 h-3.5 text-amber-300" />
            <span className="text-slate-400">Restant estimé :</span>
            <span className="font-mono font-bold text-amber-200 tabular-nums">
              ~{formatDurationShort(timing.remainingSeconds)}
            </span>
          </div>

          <div className="px-3 py-1.5 rounded-lg bg-cyan-500/20 border border-cyan-400/40 font-mono text-xs font-bold text-cyan-200 tabular-nums">
            {timing.effectivePercent}%
          </div>

          {onMinimize && (
            <button
              type="button"
              onClick={onMinimize}
              title="Réduire en mini-pilule (continue en arrière-plan)"
              className="p-1.5 rounded-lg bg-white/5 hover:bg-white/15 border border-white/10 text-slate-300 hover:text-white transition"
            >
              <Minimize2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Barre de progression continue globale */}
      <div className="h-1.5 w-full bg-slate-900 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-cyan-400 via-indigo-400 to-emerald-400 transition-all duration-500"
          style={{ width: `${timing.effectivePercent}%` }}
        />
      </div>

      {/* Corps principal : Viewport Holographique Gaussian Splatting + Tableau des 5 Sous-Agents */}
      <div className={`grid gap-4 p-4 ${compact ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-12'}`}>
        {/* Colonne Gauche : Viewport 3D Gaussian Splatting interactif */}
        <div className={`${compact ? '' : 'lg:col-span-7'} flex flex-col gap-2.5`}>
          <div className="relative rounded-xl overflow-hidden border border-cyan-500/25 bg-[#050811] select-none">
            <canvas
              ref={canvasRef}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              onPointerLeave={handlePointerUp}
              className={`w-full ${compact ? 'h-56' : 'h-80'} cursor-grab active:cursor-grabbing block`}
            />

            {/* Sélecteur de mode d'inspection holographique */}
            <div className="absolute bottom-3 left-3 right-3 flex flex-wrap items-center justify-between gap-2 pointer-events-auto">
              <div className="flex items-center gap-1 rounded-lg bg-slate-950/85 border border-white/15 p-1 backdrop-blur-md">
                <button
                  type="button"
                  onClick={() => setViewMode('splats')}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition ${
                    viewMode === 'splats'
                      ? 'bg-cyan-500/25 text-cyan-200 border border-cyan-400/40'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Nuage Splats 3D
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('kinematics')}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition ${
                    viewMode === 'kinematics'
                      ? 'bg-indigo-500/25 text-indigo-200 border border-indigo-400/40'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Liaisons & Pièces
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('blueprint')}
                  className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition ${
                    viewMode === 'blueprint'
                      ? 'bg-emerald-500/25 text-emerald-200 border border-emerald-400/40'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Cotes & Repères
                </button>
              </div>

              <button
                type="button"
                onClick={() => {
                  setCameraYaw(0.45);
                  setCameraPitch(0.22);
                }}
                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-950/85 border border-white/15 text-[11px] text-slate-300 hover:text-white"
              >
                <RotateCcw className="w-3 h-3" /> Recadrer 3D
              </button>
            </div>
          </div>

          {/* Bandeau d'assurance de persistance : quitter et reprendre */}
          <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-[11px] text-emerald-200">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>
                <strong>Continuité active :</strong> tu peux changer d’onglet ou quitter cette page ; la génération se
                poursuit sur le serveur et reprendra automatiquement ici ou affichera le modèle final dès ton retour.
              </span>
            </div>
          </div>
        </div>

        {/* Colonne Droite : Division du travail des 5 Sous-Agents Spécialisés */}
        <div className={`${compact ? '' : 'lg:col-span-5'} flex flex-col justify-between gap-3`}>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-cyan-400" />
                Division en 5 Sous-Agents Spécialisés
              </span>
              <span className="text-[11px] text-slate-400">
                {subAgents.filter((a) => a.status === 'done').length}/{subAgents.length} terminés
              </span>
            </div>

            <div className="space-y-2">
              {subAgents.map((agent, idx) => {
                const isSelected = (selectedAgentIdx ?? activeAgentIndex) === idx;
                return (
                  <button
                    key={agent.id}
                    type="button"
                    onClick={() => setSelectedAgentIdx(idx)}
                    className={`w-full text-left p-2.5 rounded-xl border transition ${
                      agent.status === 'running'
                        ? 'bg-cyan-500/12 border-cyan-400/45 shadow-[0_0_20px_rgba(56,189,248,0.12)]'
                        : agent.status === 'done'
                        ? 'bg-emerald-500/10 border-emerald-500/30'
                        : 'bg-slate-900/60 border-white/10 opacity-75 hover:opacity-100'
                    } ${isSelected ? 'ring-1 ring-white/30' : ''}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className="h-2.5 w-2.5 rounded-full shrink-0"
                          style={{
                            backgroundColor:
                              agent.status === 'done'
                                ? '#34d399'
                                : agent.status === 'running'
                                ? agent.color
                                : '#64748b',
                          }}
                        />
                        <span className="font-mono text-[11px] font-bold text-white truncate">{agent.code}</span>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="text-[10px] font-mono text-slate-300 tabular-nums">
                          {agent.progressPercent}%
                        </span>
                        {agent.status === 'done' ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                        ) : agent.status === 'running' ? (
                          <Layers className="w-3.5 h-3.5 text-cyan-300 animate-pulse" />
                        ) : (
                          <Box className="w-3.5 h-3.5 text-slate-500" />
                        )}
                      </div>
                    </div>

                    <div className="mt-1 text-[11px] font-medium text-slate-200">{agent.role}</div>
                    <div className="mt-0.5 text-[11px] text-slate-400 line-clamp-1">{agent.currentAction}</div>

                    {/* Barre de progression propre au sous-agent */}
                    <div className="mt-2 h-1 w-full rounded-full bg-slate-950 overflow-hidden">
                      <div
                        className="h-full transition-all duration-500"
                        style={{
                          width: `${agent.progressPercent}%`,
                          backgroundColor: agent.status === 'done' ? '#34d399' : agent.color,
                        }}
                      />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Détail temps réel du sous-agent inspecté */}
          <div className="p-3 rounded-xl bg-slate-900/90 border border-white/10 space-y-1.5">
            <div className="flex items-center justify-between text-[11px]">
              <span className="font-mono font-bold text-cyan-300 flex items-center gap-1.5">
                <Wrench className="w-3.5 h-3.5" />
                {displayedAgent.code}
              </span>
              <span className="text-slate-400">{displayedAgent.name}</span>
            </div>
            <p className="text-[11px] text-slate-300 leading-relaxed">{displayedAgent.specialty}</p>
            <div className="flex flex-wrap gap-1.5 pt-1">
              {displayedAgent.liveMetrics.map((c, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-[10px] text-slate-300"
                >
                  {c}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HolographicSplatLoader;
