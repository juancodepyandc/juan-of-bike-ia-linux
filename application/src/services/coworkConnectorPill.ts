// ---------------------------------------------------------------------------
// coworkConnectorPill — pure helpers for the CoworkOverlay connector hint
// pill (v82m0).
//
// Extracted from CoworkOverlay.tsx so node --test can unit-test the parser
// without pulling React, framer-motion, lucide-react, etc. The component
// re-exports `extractConnectorHintFromEventDetail` and
// `summariseConnectorHint` from this module.
//
// The pill surfaces `payload.connector_hint` (set by
// `coworkPlanParser.buildCardIterationAction`) on info events whose
// detail JSON describes a `browser.extract_structured(card_iteration)`
// action. Pure read — the executor is unchanged.
// ---------------------------------------------------------------------------

import type { CoworkActionEvent } from './coworkTypes'

/**
 * Read the connector_hint string out of an event's detail JSON.
 *
 * Returns null when :
 *   - event has no detail, or detail is non-JSON
 *   - event is not an `info` event with actionKind='browser'
 *   - the action is not browser.extract_structured(card_iteration)
 *   - payload.connector_hint is missing / not a string / empty
 *
 * Pure : no side effects, no DOM, no global state.
 */
export function extractConnectorHintFromEventDetail(event: CoworkActionEvent): string | null {
  if (!event.detail) return null
  // Action emission events carry the action JSON ; result events
  // (`success` / `error`) carry the executor output instead.
  if (event.actionKind !== 'browser') return null
  if (event.kind !== 'info') return null
  let parsed: unknown
  try { parsed = JSON.parse(event.detail) } catch { return null }
  if (!parsed || typeof parsed !== 'object') return null
  const a = parsed as { kind?: string; operation?: string; payload?: unknown }
  if (a.kind !== 'browser') return null
  if (a.operation !== 'extract_structured') return null
  const payload = a.payload && typeof a.payload === 'object' ? a.payload as Record<string, unknown> : null
  if (!payload) return null
  if (payload.mode !== 'card_iteration') return null
  const hint = payload.connector_hint
  return typeof hint === 'string' && hint.trim() ? hint : null
}

/**
 * Shorten a connector_hint reasoning string into a 1-line pill label.
 *
 * Recognises the three branches emitted by `buildConnectorHintReasoning` :
 *   - dedicated connector : "...on <Label>...opt-in to <id> connector..."
 *     → "<Label> detected — connector available"
 *   - known host without connector : "...on <Label>..."
 *     → "<Label> detected — generic extraction"
 *   - generic / unknown host
 *     → "social_feed (generic)"
 */
export function summariseConnectorHint(hint: string): string {
  const optIn = /opt-in to (\w[\w_-]*)/i.exec(hint)
  const onHost = /on ([A-Z][\w.+-]*)/.exec(hint)
  if (optIn && onHost) return `${onHost[1]} detected — connector available`
  if (optIn) return `connector ${optIn[1]} available`
  if (onHost) return `${onHost[1]} detected — generic extraction`
  return 'social_feed (generic)'
}

/**
 * v82m1 — extract the connector id and human label from a connector_hint
 * reasoning string. Returns null when the hint describes a generic /
 * extension-only / unknown-host page (no dedicated connector to navigate to).
 *
 * Mirrors the parsing branches of `summariseConnectorHint` :
 *   - "...on <Label>...opt-in to <id> connector..." → { id, label }
 *   - any other branch (no opt-in match) → null
 *
 * Used by the CoworkOverlay pill click handler : when this returns non-null,
 * the pill becomes clickable (cursor:pointer) and opens an opt-in dialog
 * that navigates to the connector settings panel on confirmation. When it
 * returns null, the pill stays a passive label (cursor:default).
 *
 * Pure : no side effects, no DOM, no global state.
 */
export function extractConnectorTargetFromHint(hint: string): { id: string; label: string } | null {
  if (!hint || typeof hint !== 'string') return null
  const optIn = /opt-in to (\w[\w_-]*)/i.exec(hint)
  if (!optIn) return null
  const onHost = /on ([A-Z][\w.+-]*)/.exec(hint)
  return {
    id: optIn[1],
    label: onHost ? onHost[1] : optIn[1],
  }
}
