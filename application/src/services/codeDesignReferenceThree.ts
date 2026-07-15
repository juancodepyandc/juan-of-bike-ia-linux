/** Premium Three.js reference used as 3D design-level exemplar. */

/**
 * v76: starter Three.js complet — single-file ESM via CDN, scene cinematique
 * (5 lights, RoomEnvironment, post-processing UnrealBloom), 9 instances cubes
 * physiques en grille avec rotation animee delta-time, OrbitControls damping,
 * raycaster hover emissif, fog atmospherique. Le LLM reproduit ce niveau au
 * lieu d un cube isole tournant en MeshBasicMaterial.
 */
export const THREE_D_SCENE_REFERENCE = String.raw`<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Scene 3D Premium</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body { width: 100%; height: 100%; overflow: hidden; background: #07090f; font-family: 'Inter', system-ui, sans-serif; color: #f5f7fa; }
    canvas { display: block; }
    .hud { position: fixed; top: 1.25rem; left: 1.25rem; padding: 0.85rem 1.1rem; backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); background: rgba(15, 22, 36, 0.55); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; box-shadow: 0 12px 40px -16px rgba(0,0,0,0.6); }
    .hud h1 { font-size: 0.95rem; font-weight: 600; letter-spacing: 0.04em; }
    .hud p { font-size: 0.72rem; color: rgba(245,247,250,0.6); margin-top: 0.25rem; letter-spacing: 0.02em; }
    .hud span { color: #74e8ff; font-weight: 600; }
  </style>
</head>
<body>
  <div class="hud">
    <h1>Scene 3D <span>Aurora</span></h1>
    <p>Glissez pour orbiter — molette pour zoomer — clic pour highlight</p>
  </div>
  <script type="importmap">
    {
      "imports": {
        "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
        "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
      }
    }
  </script>
  <script type="module">
    import * as THREE from 'three'
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js'
    import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js'
    import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js'
    import { RenderPass } from 'three/addons/postprocessing/RenderPass.js'
    import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js'
    import { OutputPass } from 'three/addons/postprocessing/OutputPass.js'

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x070912)
    scene.fog = new THREE.FogExp2(0x070912, 0.022)

    const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.1, 200)
    camera.position.set(7, 5, 9)

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' })
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2))
    renderer.setSize(innerWidth, innerHeight)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.15
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFSoftShadowMap
    document.body.appendChild(renderer.domElement)

    const pmrem = new THREE.PMREMGenerator(renderer)
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture

    const hemi = new THREE.HemisphereLight(0xa3c8ff, 0xff8a3d, 0.45)
    scene.add(hemi)
    const key = new THREE.DirectionalLight(0xfff2cf, 1.8)
    key.position.set(8, 12, 6); key.castShadow = true
    key.shadow.mapSize.set(2048, 2048); key.shadow.bias = -0.0001
    key.shadow.camera.left = -12; key.shadow.camera.right = 12; key.shadow.camera.top = 12; key.shadow.camera.bottom = -12
    scene.add(key)
    const fillTeal = new THREE.PointLight(0x74e8ff, 18, 22, 2)
    fillTeal.position.set(-5, 4, -3); scene.add(fillTeal)
    const fillMagenta = new THREE.PointLight(0xff5fae, 14, 18, 2)
    fillMagenta.position.set(4, 2, -5); scene.add(fillMagenta)
    const accent = new THREE.SpotLight(0xfff5e6, 24, 30, Math.PI / 6, 0.4, 1.5)
    accent.position.set(0, 14, 0); accent.target.position.set(0, 0, 0)
    accent.castShadow = true; accent.shadow.mapSize.set(1024, 1024)
    scene.add(accent); scene.add(accent.target)

    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(60, 60),
      new THREE.MeshPhysicalMaterial({ color: 0x0e1424, roughness: 0.42, metalness: 0.18, clearcoat: 0.18, clearcoatRoughness: 0.6 }),
    )
    ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; scene.add(ground)

    const geometry = new THREE.IcosahedronGeometry(0.65, 0)
    const palette = [0x74e8ff, 0xff5fae, 0xa78bfa, 0xfacc15, 0x34d399]
    const meshes = []
    for (let i = 0; i < 9; i++) {
      const mat = new THREE.MeshPhysicalMaterial({
        color: palette[i % palette.length],
        roughness: 0.18,
        metalness: 0.55,
        clearcoat: 0.85,
        clearcoatRoughness: 0.05,
        emissive: 0x000000,
        emissiveIntensity: 0,
      })
      const mesh = new THREE.Mesh(geometry, mat)
      const col = i % 3, row = Math.floor(i / 3)
      mesh.position.set((col - 1) * 2.4, 1 + Math.sin(i * 1.7) * 0.4, (row - 1) * 2.4)
      mesh.castShadow = true; mesh.receiveShadow = true
      mesh.userData.baseColor = mat.color.clone()
      mesh.userData.spinSpeed = 0.4 + Math.random() * 0.6
      scene.add(mesh); meshes.push(mesh)
    }

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true; controls.dampingFactor = 0.06
    controls.autoRotate = true; controls.autoRotateSpeed = 0.6
    controls.target.set(0, 1, 0)
    renderer.domElement.addEventListener('pointerdown', () => { controls.autoRotate = false })

    const composer = new EffectComposer(renderer)
    composer.addPass(new RenderPass(scene, camera))
    composer.addPass(new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.65, 0.6, 0.85))
    composer.addPass(new OutputPass())

    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2(99, 99)
    addEventListener('pointermove', (e) => { pointer.x = (e.clientX / innerWidth) * 2 - 1; pointer.y = -(e.clientY / innerHeight) * 2 + 1 })

    addEventListener('resize', () => {
      camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix()
      renderer.setSize(innerWidth, innerHeight); composer.setSize(innerWidth, innerHeight)
    })

    const clock = new THREE.Clock()
    function loop() {
      const dt = clock.getDelta()
      const t = clock.getElapsedTime()
      meshes.forEach((m, idx) => {
        m.rotation.y += dt * m.userData.spinSpeed
        m.rotation.x += dt * m.userData.spinSpeed * 0.7
        m.position.y = 1 + Math.sin(t * 1.4 + idx * 0.7) * 0.35
      })
      raycaster.setFromCamera(pointer, camera)
      const hits = raycaster.intersectObjects(meshes)
      meshes.forEach((m) => { m.material.emissive.set(0x000000); m.material.emissiveIntensity = 0 })
      if (hits[0]) { hits[0].object.material.emissive.copy(hits[0].object.userData.baseColor); hits[0].object.material.emissiveIntensity = 0.9 }
      controls.update()
      composer.render()
      requestAnimationFrame(loop)
    }
    loop()
  </script>
</body>
</html>`
