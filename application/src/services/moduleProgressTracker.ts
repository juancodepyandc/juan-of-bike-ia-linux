/**
 * moduleProgressTracker.ts — Unified progress synchronizer and smooth progress engine.
 *
 * Provides:
 *   - Monotonic progress guarantee (progress never jumps backward)
 *   - Smooth progressive interpolation (avoids frozen progress like stuck at 12% then jumping to 92%)
 *   - Unified stage mapping across all 10 modules
 *   - Parsing for structured PROGRESS events from Python and TypeScript pipelines
 */

import {
  type MacroStageDefinition,
  type ModuleName,
  type SubStageDefinition,
  MODULE_PIPELINE_STAGES,
  getCanonicalModuleName,
} from "./modulePipelineStages.ts"

export interface StructuredProgressEvent {
  module: ModuleName
  project?: string
  stage: "analyse" | "realisation" | "verification" | "finalisation"
  stageLabel: string
  subStage?: string
  subStageLabel?: string
  pct: number
  detail: string
  step?: number
  totalSteps?: number
  elapsedSeconds?: number
  estimatedRemainingSeconds?: number
  timestamp: number
}

export interface ProgressState {
  module: ModuleName
  projectName: string
  currentPct: number
  targetPct: number
  stageKey: "analyse" | "realisation" | "verification" | "finalisation"
  stageLabel: string
  subStageKey: string
  subStageLabel: string
  detail: string
  status: "idle" | "running" | "done" | "error"
  startTime: number
  lastUpdateTime: number
  elapsedSeconds: number
  estimatedRemainingSeconds: number | null
  stages: MacroStageDefinition[]
}

/**
 * Parses raw PROGRESS lines (either structured JSON or legacy colon-separated) into StructuredProgressEvent.
 */
export function parseProgressLine(
  raw: string,
  defaultModule: ModuleName = "code",
): StructuredProgressEvent | null {
  if (!raw || typeof raw !== "string") return null
  const line = raw.trim()
  if (!line.startsWith("PROGRESS:")) return null

  const content = line.slice("PROGRESS:".length).trim()
  if (content.startsWith("{") && content.endsWith("}")) {
    try {
      const parsed = JSON.parse(content)
      const moduleName = getCanonicalModuleName(parsed.module || defaultModule)
      const stages = MODULE_PIPELINE_STAGES[moduleName] || MODULE_PIPELINE_STAGES.code
      const stageKey = (parsed.stage || "analyse").toLowerCase()
      const matchedStage = stages.find((s) => s.key === stageKey) || stages[0]

      return {
        module: moduleName,
        project: parsed.project || "projet",
        stage: matchedStage.key,
        stageLabel: parsed.stage_label || matchedStage.label,
        subStage: parsed.sub_stage || "init",
        subStageLabel: parsed.sub_stage_label || parsed.sub_stage || "",
        pct: typeof parsed.pct === "number" ? Math.max(0, Math.min(100, parsed.pct)) : matchedStage.pctStart,
        detail: parsed.detail || "",
        step: parsed.step,
        totalSteps: parsed.total_steps,
        elapsedSeconds: parsed.elapsed_s,
        timestamp: parsed.ts ? parsed.ts * 1000 : Date.now(),
      }
    } catch {
      // Fallback to legacy parsing if JSON parse fails
    }
  }

  // Legacy format: PROGRESS:<stage>:<detail> or PROGRESS:<pct>:<stage>:<detail>
  const parts = content.split(":")
  const moduleName = getCanonicalModuleName(defaultModule)
  const stages = MODULE_PIPELINE_STAGES[moduleName] || MODULE_PIPELINE_STAGES.code

  if (parts.length >= 2) {
    let pct: number | null = null
    let stageStr = parts[0].trim().toLowerCase()
    let detailStr = parts.slice(1).join(":").trim()

    // If first part is a number (e.g. PROGRESS:45:mesh:generating)
    const maybeNum = parseFloat(stageStr)
    if (!isNaN(maybeNum) && maybeNum >= 0 && maybeNum <= 100) {
      pct = maybeNum
      stageStr = parts[1]?.trim().toLowerCase() || "realisation"
      detailStr = parts.slice(2).join(":").trim()
    }

    let matchedStage = stages.find((s) => s.key === stageStr || s.label.toLowerCase().includes(stageStr))
    if (!matchedStage) {
      if (pct !== null) {
        matchedStage = stages.find((s) => s.pctStart <= pct! && pct! <= s.pctEnd) || stages[0]
      } else {
        matchedStage = stages[0]
      }
    }

    const finalPct = pct !== null ? pct : matchedStage.pctStart

    return {
      module: moduleName,
      stage: matchedStage.key,
      stageLabel: matchedStage.label,
      subStage: stageStr,
      subStageLabel: stageStr,
      pct: finalPct,
      detail: detailStr,
      timestamp: Date.now(),
    }
  }

  return null
}

export class ModuleProgressEngine {
  private state: ProgressState
  private subscribers: Set<(state: ProgressState) => void> = new Set()
  private heartbeatTimer: any = null

  constructor(moduleName: string, projectName: string = "projet") {
    const canonical = getCanonicalModuleName(moduleName)
    const stages = MODULE_PIPELINE_STAGES[canonical] || MODULE_PIPELINE_STAGES.code
    const now = Date.now()

    this.state = {
      module: canonical,
      projectName,
      currentPct: 0,
      targetPct: 0,
      stageKey: stages[0].key,
      stageLabel: stages[0].label,
      subStageKey: "init",
      subStageLabel: "Initialisation",
      detail: "Initialisation...",
      status: "idle",
      startTime: now,
      lastUpdateTime: now,
      elapsedSeconds: 0,
      estimatedRemainingSeconds: null,
      stages,
    }
  }

  public getState(): ProgressState {
    return { ...this.state }
  }

  public subscribe(cb: (state: ProgressState) => void): () => void {
    this.subscribers.add(cb)
    cb(this.getState())
    return () => this.subscribers.delete(cb)
  }

  private notify() {
    const snapshot = this.getState()
    this.subscribers.forEach((cb) => {
      try {
        cb(snapshot)
      } catch (err) {
        console.warn("[ModuleProgressEngine] Subscriber error:", err)
      }
    })
  }

  public start(detail: string = "Démarrage de la tâche..."): void {
    this.state.status = "running"
    this.state.startTime = Date.now()
    this.state.lastUpdateTime = this.state.startTime
    this.state.currentPct = 0
    this.state.targetPct = 5
    this.state.detail = detail
    this.startHeartbeat()
    this.notify()
  }

  public update(event: Partial<StructuredProgressEvent>): void {
    const now = Date.now()
    this.state.lastUpdateTime = now
    this.state.elapsedSeconds = Math.max(0, (now - this.state.startTime) / 1000)

    if (event.pct !== undefined && typeof event.pct === "number") {
      // Monotonic guarantee: never regress unless explicitly reset
      this.state.targetPct = Math.max(this.state.currentPct, Math.min(100, event.pct))
      this.state.currentPct = this.state.targetPct
    }

    if (event.detail) {
      this.state.detail = event.detail
    }

    if (event.stage) {
      const matched = this.state.stages.find((s) => s.key === event.stage)
      if (matched) {
        this.state.stageKey = matched.key
        this.state.stageLabel = event.stageLabel || matched.label
      }
    } else if (event.pct !== undefined) {
      const matched = this.state.stages.find((s) => s.pctStart <= event.pct! && event.pct! <= s.pctEnd)
      if (matched) {
        this.state.stageKey = matched.key
        this.state.stageLabel = matched.label
      }
    }

    if (event.subStage) {
      this.state.subStageKey = event.subStage
      this.state.subStageLabel = event.subStageLabel || event.subStage
    }

    // Estimate remaining time based on progress velocity
    if (this.state.currentPct > 10 && this.state.elapsedSeconds > 2) {
      const remainingPct = 100 - this.state.currentPct
      const secondsPerPct = this.state.elapsedSeconds / this.state.currentPct
      this.state.estimatedRemainingSeconds = Math.max(1, Math.round(remainingPct * secondsPerPct))
    }

    this.notify()
  }

  public setPhase(detail: string, pct: number, subStage?: string): void {
    this.update({ detail, pct, subStage })
  }

  public complete(detail: string = "Tâche terminée avec succès."): void {
    this.stopHeartbeat()
    this.state.status = "done"
    this.state.currentPct = 100
    this.state.targetPct = 100
    this.state.stageKey = "finalisation"
    this.state.stageLabel = "Livraison"
    this.state.detail = detail
    this.state.estimatedRemainingSeconds = 0
    this.notify()
  }

  public fail(errorMessage: string): void {
    this.stopHeartbeat()
    this.state.status = "error"
    this.state.detail = errorMessage
    this.notify()
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    // Small interpolation heartbeat every 800ms during running tasks
    this.heartbeatTimer = setInterval(() => {
      if (this.state.status !== "running") {
        this.stopHeartbeat()
        return
      }
      const now = Date.now()
      this.state.elapsedSeconds = Math.max(0, (now - this.state.startTime) / 1000)

      // If currentPct is far from stage boundary, slowly nudge progress by 0.2% up to ceiling
      const currentStage = this.state.stages.find((s) => s.key === this.state.stageKey)
      const stageCeiling = currentStage ? currentStage.pctEnd - 1.0 : 90.0

      if (this.state.currentPct < stageCeiling && now - this.state.lastUpdateTime > 2000) {
        this.state.currentPct = Math.min(stageCeiling, +(this.state.currentPct + 0.15).toFixed(2))
        this.notify()
      }
    }, 800)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }
}
