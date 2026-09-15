import type { ChemistryReactionConfig, ReactionKind, SceneEntity, Vec3 } from './types.ts'

export type ReactionRuntime = {
  entityId: string
  config: ChemistryReactionConfig
  temperature: number
  consumedFuel: number
  consumedOxidizer: number
  produced: number
  energyReleased: number
  active: boolean
  origin: Vec3
  products: string[]
  lightIntensity: number
  lastEmittedAt: number
}

export type ReactionEvent = {
  entityId: string
  kind: ReactionKind
  temperature: number
  lightIntensity: number
  smokeColor: string
  flameColor: string
  sparkRate: number
  origin: Vec3
  equation: string
}

const HEAT_LOSS = 0.08
const MIN_TEMP = 20

export class ChemistryEngine {
  private runtimes = new Map<string, ReactionRuntime>()
  private globalThermalGrid = new Map<string, number>()

  sync(entities: SceneEntity[]) {
    const seen = new Set<string>()
    for (const entity of entities) {
      if (entity.type !== 'reaction' || !entity.reaction) continue
      seen.add(entity.id)
      const existing = this.runtimes.get(entity.id)
      if (existing) {
        existing.config = entity.reaction
        existing.origin = [...entity.transform.position]
      } else {
        this.runtimes.set(entity.id, {
          entityId: entity.id,
          config: entity.reaction,
          temperature: MIN_TEMP,
          consumedFuel: 0,
          consumedOxidizer: 0,
          produced: 0,
          energyReleased: 0,
          active: false,
          origin: [...entity.transform.position],
          products: [],
          lightIntensity: 0,
          lastEmittedAt: 0,
        })
      }
    }
    for (const id of Array.from(this.runtimes.keys())) {
      if (!seen.has(id)) this.runtimes.delete(id)
    }
  }

  ignite(entityId: string) {
    const runtime = this.runtimes.get(entityId)
    if (!runtime) return
    runtime.temperature = Math.max(runtime.temperature, runtime.config.ignitionTemperature + 20)
    runtime.active = true
  }

  extinguish(entityId: string) {
    const runtime = this.runtimes.get(entityId)
    if (!runtime) return
    runtime.active = false
    runtime.temperature = MIN_TEMP
    runtime.lightIntensity = 0
  }

  step(dt: number, now: number): ReactionEvent[] {
    const events: ReactionEvent[] = []
    for (const runtime of this.runtimes.values()) {
      if (runtime.config.running && !runtime.active) runtime.active = true
      if (!runtime.config.running && runtime.active && runtime.config.ignitionTemperature > 0) runtime.active = false
      if (!runtime.active) {
        runtime.temperature = Math.max(MIN_TEMP, runtime.temperature - HEAT_LOSS * dt * 60)
        continue
      }
      const cfg = runtime.config
      const remainingFuel = Math.max(0, cfg.fuelMass - runtime.consumedFuel)
      if (remainingFuel <= 0 && cfg.fuelMass > 0) {
        runtime.active = false
        continue
      }
      const burnRate = Math.min(remainingFuel, 0.02 * dt * (runtime.temperature / Math.max(50, cfg.ignitionTemperature)))
      runtime.consumedFuel += burnRate
      runtime.consumedOxidizer += burnRate * (cfg.oxidizerMass / Math.max(0.01, cfg.fuelMass))
      const released = burnRate * cfg.heatRelease
      runtime.energyReleased += released
      runtime.temperature += released * 0.0015
      runtime.temperature = Math.min(3200, runtime.temperature)
      runtime.lightIntensity = Math.min(4, Math.max(0, (runtime.temperature - cfg.ignitionTemperature) / 400))
      if (now - runtime.lastEmittedAt > 0.05) {
        runtime.lastEmittedAt = now
        events.push({
          entityId: runtime.entityId,
          kind: cfg.kind,
          temperature: runtime.temperature,
          lightIntensity: runtime.lightIntensity,
          smokeColor: cfg.smokeColor,
          flameColor: cfg.flameColor,
          sparkRate: cfg.sparkRate,
          origin: runtime.origin,
          equation: cfg.equation,
        })
      }
      this.diffuseThermal(runtime)
    }
    return events
  }

  private diffuseThermal(runtime: ReactionRuntime) {
    const key = `${Math.round(runtime.origin[0])}:${Math.round(runtime.origin[1])}:${Math.round(runtime.origin[2])}`
    const current = this.globalThermalGrid.get(key) ?? MIN_TEMP
    const next = current + (runtime.temperature - current) * 0.1
    this.globalThermalGrid.set(key, next)
  }

  getThermalAt(position: Vec3): number {
    const key = `${Math.round(position[0])}:${Math.round(position[1])}:${Math.round(position[2])}`
    return this.globalThermalGrid.get(key) ?? MIN_TEMP
  }

  getRuntimes(): ReactionRuntime[] {
    return Array.from(this.runtimes.values())
  }

  getRuntime(id: string): ReactionRuntime | undefined {
    return this.runtimes.get(id)
  }

  isReactionActive(id: string): boolean {
    return this.runtimes.get(id)?.active ?? false
  }
}

export function formatBalanceSummary(config: ChemistryReactionConfig, runtime?: ReactionRuntime): string {
  const percentConsumed = runtime && config.fuelMass > 0 ? Math.min(100, Math.round((runtime.consumedFuel / config.fuelMass) * 100)) : 0
  const energy = runtime ? Math.round(runtime.energyReleased * 100) / 100 : 0
  return `${config.equation} | Fuel consomme: ${percentConsumed}% | Energie: ${energy} kJ`
}
