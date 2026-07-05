import { Suspense, useMemo, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'

type Vec3 = [number, number, number]

type Atom = {
  element: 'H' | 'C' | 'O' | 'N'
  pos: Vec3
}

type Bond = { from: number; to: number; order: 1 | 2 | 3 }

type Molecule = {
  id: string
  label: string
  formula: string
  atoms: Atom[]
  bonds: Bond[]
}

const CPK: Record<Atom['element'], string> = {
  H: '#f5f5f5',
  C: '#2a2a2a',
  O: '#ef4444',
  N: '#3b82f6',
}

const RADIUS: Record<Atom['element'], number> = {
  H: 0.28,
  C: 0.42,
  O: 0.4,
  N: 0.4,
}

const MOLECULES: Molecule[] = [
  {
    id: 'water',
    label: 'Eau',
    formula: 'H₂O',
    atoms: [
      { element: 'O', pos: [0, 0, 0] },
      { element: 'H', pos: [0.76, 0.58, 0] },
      { element: 'H', pos: [-0.76, 0.58, 0] },
    ],
    bonds: [
      { from: 0, to: 1, order: 1 },
      { from: 0, to: 2, order: 1 },
    ],
  },
  {
    id: 'methane',
    label: 'Méthane',
    formula: 'CH₄',
    atoms: [
      { element: 'C', pos: [0, 0, 0] },
      { element: 'H', pos: [0.63, 0.63, 0.63] },
      { element: 'H', pos: [-0.63, -0.63, 0.63] },
      { element: 'H', pos: [-0.63, 0.63, -0.63] },
      { element: 'H', pos: [0.63, -0.63, -0.63] },
    ],
    bonds: [
      { from: 0, to: 1, order: 1 },
      { from: 0, to: 2, order: 1 },
      { from: 0, to: 3, order: 1 },
      { from: 0, to: 4, order: 1 },
    ],
  },
  {
    id: 'co2',
    label: 'Dioxyde de carbone',
    formula: 'CO₂',
    atoms: [
      { element: 'C', pos: [0, 0, 0] },
      { element: 'O', pos: [1.16, 0, 0] },
      { element: 'O', pos: [-1.16, 0, 0] },
    ],
    bonds: [
      { from: 0, to: 1, order: 2 },
      { from: 0, to: 2, order: 2 },
    ],
  },
  {
    id: 'ammonia',
    label: 'Ammoniac',
    formula: 'NH₃',
    atoms: [
      { element: 'N', pos: [0, 0, 0] },
      { element: 'H', pos: [0.94, 0.32, 0] },
      { element: 'H', pos: [-0.47, 0.32, 0.82] },
      { element: 'H', pos: [-0.47, 0.32, -0.82] },
    ],
    bonds: [
      { from: 0, to: 1, order: 1 },
      { from: 0, to: 2, order: 1 },
      { from: 0, to: 3, order: 1 },
    ],
  },
  {
    id: 'ethanol',
    label: 'Éthanol',
    formula: 'C₂H₆O',
    atoms: [
      { element: 'C', pos: [-1.2, 0, 0] },
      { element: 'C', pos: [0, 0.5, 0] },
      { element: 'O', pos: [1.0, -0.4, 0] },
      { element: 'H', pos: [-1.7, -0.9, 0] },
      { element: 'H', pos: [-1.7, 0.7, 0.8] },
      { element: 'H', pos: [-1.7, 0.7, -0.8] },
      { element: 'H', pos: [0.2, 1.1, 0.8] },
      { element: 'H', pos: [0.2, 1.1, -0.8] },
      { element: 'H', pos: [1.7, 0.0, 0] },
    ],
    bonds: [
      { from: 0, to: 1, order: 1 },
      { from: 1, to: 2, order: 1 },
      { from: 0, to: 3, order: 1 },
      { from: 0, to: 4, order: 1 },
      { from: 0, to: 5, order: 1 },
      { from: 1, to: 6, order: 1 },
      { from: 1, to: 7, order: 1 },
      { from: 2, to: 8, order: 1 },
    ],
  },
]

function BondCylinder({
  from,
  to,
  order,
}: {
  from: Vec3
  to: Vec3
  order: 1 | 2 | 3
}) {
  const fx = from[0]
  const fy = from[1]
  const fz = from[2]
  const tx = to[0]
  const ty = to[1]
  const tz = to[2]
  const midX = (fx + tx) / 2
  const midY = (fy + ty) / 2
  const midZ = (fz + tz) / 2
  const dx = tx - fx
  const dy = ty - fy
  const dz = tz - fz
  const length = Math.sqrt(dx * dx + dy * dy + dz * dz)

  const rotation = useMemo<Vec3>(() => {
    const axisLen = Math.sqrt(dx * dx + dz * dz)
    const rotX = Math.atan2(axisLen, dy)
    const rotY = 0
    const rotZ = -Math.atan2(dz, dx) - Math.PI / 2
    return [rotX, rotY, rotZ]
  }, [dx, dy, dz])

  const offsets: number[] = order === 1 ? [0] : order === 2 ? [-0.12, 0.12] : [-0.18, 0, 0.18]

  return (
    <>
      {offsets.map((off, i) => (
        <mesh key={i} position={[midX, midY, midZ]} rotation={rotation}>
          <cylinderGeometry args={[0.06, 0.06, length, 16, 1]} />
          <meshStandardMaterial color="#94a3b8" metalness={0.3} roughness={0.4} />
          {off !== 0 && <group position={[off, 0, 0]} />}
        </mesh>
      ))}
    </>
  )
}

function Scene({ molecule }: { molecule: Molecule }) {
  return (
    <>
      <ambientLight intensity={0.55} />
      <directionalLight position={[5, 5, 5]} intensity={1.1} />
      <directionalLight position={[-5, -2, -5]} intensity={0.4} color="#67e8f9" />
      {molecule.atoms.map((atom, idx) => (
        <mesh key={idx} position={atom.pos}>
          <sphereGeometry args={[RADIUS[atom.element], 24, 24]} />
          <meshStandardMaterial
            color={CPK[atom.element]}
            metalness={0.2}
            roughness={0.3}
            emissive={CPK[atom.element]}
            emissiveIntensity={0.05}
          />
        </mesh>
      ))}
      {molecule.bonds.map((bond, idx) => (
        <BondCylinder
          key={idx}
          from={molecule.atoms[bond.from].pos}
          to={molecule.atoms[bond.to].pos}
          order={bond.order}
        />
      ))}
      <OrbitControls enablePan={false} autoRotate autoRotateSpeed={1.2} />
    </>
  )
}

export default function Molecule3D() {
  const [current, setCurrent] = useState(MOLECULES[0].id)
  const molecule = MOLECULES.find((m) => m.id === current) ?? MOLECULES[0]
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {MOLECULES.map((m) => (
          <button
            key={m.id}
            onClick={() => setCurrent(m.id)}
            className={`btn-pill text-[11px] ${current === m.id ? 'is-active' : ''}`}
          >
            {m.label} · {m.formula}
          </button>
        ))}
      </div>
      <div className="h-[300px] rounded-2xl border border-white/10 bg-aurora-panel/50 overflow-hidden">
        <Canvas camera={{ position: [0, 2.5, 4.5], fov: 45 }}>
          <Suspense fallback={null}>
            <Scene molecule={molecule} />
          </Suspense>
        </Canvas>
      </div>
      <div className="text-[11px] text-aurora-text-dim">
        Glisse pour tourner · atome = sphère (code couleur CPK) · liaisons simples / doubles en
        cylindres
      </div>
    </div>
  )
}
