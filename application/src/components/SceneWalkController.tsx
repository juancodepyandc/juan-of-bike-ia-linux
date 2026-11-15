// Contrôleur « Se balader » du viewer 3D : la caméra devient les yeux d'un marcheur (src/services/sceneWalk.ts).
// Clic dans la vue : la souris pilote le regard ; ZQSD (AZERTY) ou WASD (QWERTY) et les flèches : marcher —
// on lit les touches PHYSIQUES (`event.code`), donc les deux claviers marchent ; Maj : courir ; Espace :
// sauter (ou monter en vol) ; C / Ctrl : descendre en vol ; F : vol libre ; Échap : rendre la souris.
// Les touches ne sont lues que pendant la visite (après un clic dans la vue), jamais pendant une saisie.
// Sans capture de la souris (refusée par certains navigateurs et WebView, et dans le panneau de test du
// 15/11/2026), la visite marche quand même : on regarde en glissant la souris, Échap arrête.
import { useEffect, useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import type { Object3D, PerspectiveCamera } from 'three'
import { Marcheur, lireDepart } from '../services/sceneWalk'

export interface SceneWalkState {
  captured: boolean
  /** visite active : clavier lu ; regard à la souris capturée, ou en glissant si la capture est refusée */
  active: boolean
  flying: boolean
  doors: number
}

export function SceneWalkController({ modelRoot, onState }: { modelRoot: Object3D | null; onState?: (state: SceneWalkState) => void }) {
  const { camera, gl } = useThree()
  const walker = useRef<Marcheur | null>(null)
  const keys = useRef(new Set<string>())
  const stateRef = useRef<SceneWalkState>({ captured: false, active: false, flying: false, doors: 0 })
  const active = useRef(false)
  const dragging = useRef(false)

  const report = (patch: Partial<SceneWalkState>) => {
    stateRef.current = { ...stateRef.current, ...patch }
    onState?.(stateRef.current)
  }

  useEffect(() => {
    if (!modelRoot) return
    const w = new Marcheur(modelRoot)
    w.placer(lireDepart(modelRoot))
    walker.current = w
    const perspective = camera as PerspectiveCamera
    const size = w.boite.getSize(w.pieds.clone()).length()
    perspective.near = 0.05
    perspective.far = Math.max(600, size * 2.5)
    perspective.fov = 72
    perspective.updateProjectionMatrix()
    camera.position.copy(w.oeil())
    camera.quaternion.copy(w.orientation())
    report({ doors: w.nombrePortes })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modelRoot, camera])

  useEffect(() => {
    const el = gl.domElement
    const captured = () => document.pointerLockElement === el
    const setActive = (value: boolean) => {
      active.current = value
      if (!value) {
        keys.current.clear()
        dragging.current = false
      }
      report({ active: value, captured: captured() })
    }
    const onClick = () => {
      setActive(true)
      if (!captured()) {
        try {
          const demande = el.requestPointerLock?.() as unknown
          if (demande && typeof (demande as Promise<void>).catch === 'function') (demande as Promise<void>).catch(() => undefined)
        } catch { /* capture refusée : on regarde en glissant */ }
      }
    }
    const onDocumentDown = (event: MouseEvent) => { if (event.target !== el && active.current && !captured()) setActive(false) }
    const onCanvasDown = (event: MouseEvent) => { if (event.button === 0) dragging.current = true }
    const onUpMouse = () => { dragging.current = false }
    const onMove = (event: MouseEvent) => {
      if (captured() || (active.current && dragging.current)) walker.current?.tourner(event.movementX, event.movementY)
    }
    const onKey = (event: KeyboardEvent, down: boolean) => {
      if (!captured() && !active.current) return
      if (down && event.code === 'Escape' && !captured()) {
        setActive(false)
        return
      }
      if (down && event.code === 'KeyF' && walker.current) {
        walker.current.vol = !walker.current.vol
        report({ flying: walker.current.vol })
      }
      if (down) keys.current.add(event.code)
      else keys.current.delete(event.code)
      event.preventDefault()
    }
    const onDown = (event: KeyboardEvent) => onKey(event, true)
    const onUp = (event: KeyboardEvent) => onKey(event, false)
    const onLock = () => {
      // la souris rendue (Échap) arrête la visite ; capturée, elle la (re)lance
      setActive(captured())
    }
    const onBlur = () => setActive(false)
    el.addEventListener('click', onClick)
    el.addEventListener('mousedown', onCanvasDown)
    document.addEventListener('mousedown', onDocumentDown)
    window.addEventListener('mouseup', onUpMouse)
    window.addEventListener('blur', onBlur)
    document.addEventListener('mousemove', onMove)
    window.addEventListener('keydown', onDown)
    window.addEventListener('keyup', onUp)
    document.addEventListener('pointerlockchange', onLock)
    return () => {
      el.removeEventListener('click', onClick)
      el.removeEventListener('mousedown', onCanvasDown)
      document.removeEventListener('mousedown', onDocumentDown)
      window.removeEventListener('mouseup', onUpMouse)
      window.removeEventListener('blur', onBlur)
      document.removeEventListener('mousemove', onMove)
      window.removeEventListener('keydown', onDown)
      window.removeEventListener('keyup', onUp)
      document.removeEventListener('pointerlockchange', onLock)
      if (captured()) document.exitPointerLock()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gl])

  useFrame((_, delta) => {
    const w = walker.current
    if (!w) return
    const k = keys.current
    w.pas(delta, {
      avant: k.has('KeyW') || k.has('ArrowUp'),
      arriere: k.has('KeyS') || k.has('ArrowDown'),
      gauche: k.has('KeyA') || k.has('ArrowLeft'),
      droite: k.has('KeyD') || k.has('ArrowRight'),
      courir: k.has('ShiftLeft') || k.has('ShiftRight'),
      monter: k.has('Space'),
      descendre: k.has('KeyC') || k.has('ControlLeft') || k.has('ControlRight'),
      sauter: k.has('Space'),
    })
    camera.position.copy(w.oeil())
    camera.quaternion.copy(w.orientation())
  })

  return null
}
