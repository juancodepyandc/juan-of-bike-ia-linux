/**
 * InlineModelViewer — un modèle 3D qui tourne dans la bulle de chat.
 *
 * Écrit en Three.js nu plutôt qu'avec react-three-fiber : une conversation
 * peut contenir dix modèles, et un navigateur ne tolère qu'une quinzaine de
 * contextes WebGL avant de tuer les plus anciens sans prévenir. Ici le
 * contexte n'est créé qu'à l'entrée dans le viewport (IntersectionObserver)
 * et il est explicitement rendu au démontage — géométries, matériaux,
 * textures et `forceContextLoss()` compris.
 *
 * La boucle d'animation s'arrête aussi quand l'onglet passe en arrière-plan :
 * dix modèles qui tournent à 60 fps derrière une autre fenêtre, c'est un
 * ventilateur qui hurle pour rien.
 */
import { useEffect, useRef, useState } from 'react'

type Props = {
  url: string
  height?: number
  /** Rotation automatique lente tant que l'utilisateur ne touche à rien. */
  autoRotate?: boolean
}

type Status = 'idle' | 'loading' | 'ready' | 'error'

export default function InlineModelViewer({ url, height = 260, autoRotate = true }: Props) {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const [visible, setVisible] = useState(false)
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState('')

  // Chargement paresseux : tant que la bulle n'est pas à l'écran, aucun
  // octet de GLB n'est téléchargé et aucun contexte WebGL n'est ouvert.
  useEffect(() => {
    const host = hostRef.current
    if (!host || visible) return
    if (typeof IntersectionObserver === 'undefined') { setVisible(true); return }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        setVisible(true)
        observer.disconnect()
      }
    }, { rootMargin: '200px' })
    observer.observe(host)
    return () => observer.disconnect()
  }, [visible])

  useEffect(() => {
    if (!visible) return
    const host = hostRef.current
    if (!host) return

    let disposed = false
    let frame = 0
    let cleanup: (() => void) | null = null

    setStatus('loading')

    void (async () => {
      try {
        const THREE = await import('three')
        const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js')
        const { OrbitControls } = await import('three/examples/jsm/controls/OrbitControls.js')
        const { RoomEnvironment } = await import('three/examples/jsm/environments/RoomEnvironment.js')
        if (disposed) return

        const width = host.clientWidth || 400
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'low-power' })
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
        renderer.setSize(width, height)
        renderer.toneMapping = THREE.ACESFilmicToneMapping
        renderer.toneMappingExposure = 1.05
        host.appendChild(renderer.domElement)
        renderer.domElement.style.borderRadius = '12px'
        renderer.domElement.style.display = 'block'

        const scene = new THREE.Scene()
        const camera = new THREE.PerspectiveCamera(42, width / height, 0.01, 1000)

        // Éclairage : un GLB PBR sans environnement rend noir. RoomEnvironment
        // est embarqué dans three, donc il marche hors ligne.
        const pmrem = new THREE.PMREMGenerator(renderer)
        const envScene = new RoomEnvironment()
        const envMap = pmrem.fromScene(envScene, 0.04).texture
        scene.environment = envMap
        scene.add(new THREE.AmbientLight(0xffffff, 0.35))
        const key = new THREE.DirectionalLight(0xffffff, 1.6)
        key.position.set(3, 5, 4)
        scene.add(key)

        const controls = new OrbitControls(camera, renderer.domElement)
        controls.enableDamping = true
        controls.dampingFactor = 0.08
        controls.autoRotate = autoRotate
        controls.autoRotateSpeed = 1.1
        controls.addEventListener('start', () => { controls.autoRotate = false })

        const loader = new GLTFLoader()
        const gltf = await loader.loadAsync(url)
        if (disposed) return
        const model = gltf.scene

        // Recadrage : les GLB arrivent à toutes les échelles et à toutes les
        // origines. On normalise pour que le sujet remplisse le cadre.
        const box = new THREE.Box3().setFromObject(model)
        const size = box.getSize(new THREE.Vector3())
        const center = box.getCenter(new THREE.Vector3())
        const maxDim = Math.max(size.x, size.y, size.z) || 1
        model.position.sub(center)
        const scale = 1.6 / maxDim
        model.scale.setScalar(scale)
        scene.add(model)

        camera.position.set(0, 0.35, 3.1)
        controls.target.set(0, 0, 0)
        controls.update()

        setStatus('ready')

        let running = true
        const onVisibility = () => { running = document.visibilityState !== 'hidden' }
        document.addEventListener('visibilitychange', onVisibility)

        const tick = () => {
          frame = requestAnimationFrame(tick)
          if (!running) return
          controls.update()
          renderer.render(scene, camera)
        }
        tick()

        const onResize = () => {
          const w = host.clientWidth || width
          camera.aspect = w / height
          camera.updateProjectionMatrix()
          renderer.setSize(w, height)
        }
        const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(onResize) : null
        observer?.observe(host)

        cleanup = () => {
          cancelAnimationFrame(frame)
          document.removeEventListener('visibilitychange', onVisibility)
          observer?.disconnect()
          controls.dispose()
          // Libération explicite : sans ça, faire défiler une longue
          // conversation finit par saturer la mémoire GPU.
          scene.traverse((object) => {
            const mesh = object as { geometry?: { dispose?: () => void }; material?: unknown }
            mesh.geometry?.dispose?.()
            const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material]
            for (const material of materials) {
              if (!material || typeof material !== 'object') continue
              for (const value of Object.values(material as Record<string, unknown>)) {
                if (value && typeof value === 'object' && 'isTexture' in value) {
                  (value as unknown as { dispose?: () => void }).dispose?.()
                }
              }
              ;(material as { dispose?: () => void }).dispose?.()
            }
          })
          envMap.dispose()
          pmrem.dispose()
          renderer.dispose()
          renderer.forceContextLoss()
          renderer.domElement.remove()
        }
      } catch (err) {
        if (disposed) return
        setStatus('error')
        setError(err instanceof Error ? err.message : String(err))
      }
    })()

    return () => {
      disposed = true
      cancelAnimationFrame(frame)
      cleanup?.()
    }
  }, [visible, url, height, autoRotate])

  return (
    <div
      ref={hostRef}
      style={{
        position: 'relative',
        width: '100%',
        height,
        borderRadius: 12,
        overflow: 'hidden',
        border: '1px solid rgba(255,255,255,.09)',
        background: 'radial-gradient(circle at 50% 30%,rgba(139,92,246,.12),rgba(10,15,30,.85))',
      }}
    >
      {status !== 'ready' && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 11,
          fontFamily: "'Cascadia Code',Consolas,monospace",
          color: status === 'error' ? '#F87171' : '#8B93A7',
          textAlign: 'center',
          padding: 12,
        }}>
          {status === 'error'
            ? `Modèle illisible : ${error.slice(0, 120)}`
            : status === 'loading' ? 'Chargement du modèle 3D…' : 'Modèle 3D'}
        </div>
      )}
      {status === 'ready' && (
        <span style={{
          position: 'absolute',
          bottom: 8,
          left: 10,
          fontSize: 9.5,
          letterSpacing: '.14em',
          textTransform: 'uppercase',
          fontFamily: "'Cascadia Code',Consolas,monospace",
          color: '#8B93A7',
          pointerEvents: 'none',
        }}>
          glisser pour tourner · molette pour zoomer
        </span>
      )}
    </div>
  )
}
