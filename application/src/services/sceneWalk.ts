// Visite à pied d'une scène générée (intérieur, ville, paysage) : un marcheur à hauteur d'homme, qui bute
// sur les murs et glisse le long, suit le sol (marches ≤ 35 cm, pentes douces), tombe sous la gravité,
// ouvre les portes en approchant (vantaux livrés pivotant sur leur gonds, `angle_ouverture_rad` dans les
// extras glTF) et peut passer en vol libre pour les grands espaces.
//
// Logique pure three.js, sans React, pour être testée en Node (scripts/test-scene-walk.mjs). Les rayons
// utilisent three-mesh-bvh : une forêt de 600 000 triangles reste fluide.
import { Box3, Euler, Mesh, Object3D, Quaternion, Raycaster, Vector3 } from 'three'
import type { BufferGeometry, Intersection, Material } from 'three'
import { acceleratedRaycast, computeBoundsTree } from 'three-mesh-bvh'

export const MARCHE = {
  yeux: 1.62,
  rayon: 0.28,
  /** marche franchissable : escaliers et bordures oui, table basse et lit non */
  pas: 0.35,
  marche: 1.5,
  course: 4.2,
  vol: 14,
  saut: 4.2,
  gravite: 9.81,
  /** une surface dont la normale monte au-dessus de ce cosinus est un sol (pente < 53°), pas un mur */
  sol: 0.6,
  /** distance (m) à laquelle une porte s'ouvre */
  porte: 1.9,
}

export interface Depart { x: number; y?: number; z: number; direction?: [number, number] }

export interface Commandes {
  avant: boolean
  arriere: boolean
  gauche: boolean
  droite: boolean
  courir: boolean
  monter: boolean
  descendre: boolean
  sauter: boolean
}

interface Porte { noeud: Object3D; repos: Quaternion; ouverte: Quaternion; ouverture: number; meshes: Set<Mesh> }

const HAUT = new Vector3(0, 1, 0)
const BAS = new Vector3(0, -1, 0)

function materiaux(m: Mesh): Material[] {
  return Array.isArray(m.material) ? m.material : [m.material]
}

/** L'eau se traverse (on marche au fond) ; tout le reste est solide. */
function traversable(m: Mesh): boolean {
  return materiaux(m).some((mat) => /(^|_)eau(_|$)/.test(mat?.name || ''))
}

/** Le point de départ écrit par le moteur de scènes dans les extras de la scène glTF. */
export function lireDepart(racine: Object3D | null): Depart | null {
  const donnees = (racine?.userData ?? {}) as { extras?: { depart?: Depart }; depart?: Depart }
  const depart = donnees.extras?.depart ?? donnees.depart
  return depart && Number.isFinite(depart.x) && Number.isFinite(depart.z) ? depart : null
}

export class Marcheur {
  pieds = new Vector3()
  vy = 0
  auSol = false
  vol = false
  lacet = 0
  tangage = 0
  readonly boite = new Box3()
  private solides: Mesh[] = []
  private portes: Porte[] = []
  private readonly rayon = new Raycaster()

  readonly racine: Object3D

  constructor(racine: Object3D) {
    this.racine = racine
    ;(this.rayon as Raycaster & { firstHitOnly?: boolean }).firstHitOnly = true
    this.preparer()
  }

  /** Arbres de recherche sur chaque maillage, portes et objets traversables repérés. */
  preparer(): void {
    this.racine.updateMatrixWorld(true)
    const portes: Porte[] = []
    this.racine.traverse((objet) => {
      if (/^porte_/.test(objet.name) && objet.children.length) {
        const angle = Number((objet.userData as { angle_ouverture_rad?: number }).angle_ouverture_rad ?? Math.PI / 2)
        const repos = objet.quaternion.clone()
        const ouverte = repos.clone().multiply(new Quaternion().setFromAxisAngle(HAUT, angle))
        const meshes = new Set<Mesh>()
        objet.traverse((o) => { if ((o as Mesh).isMesh) meshes.add(o as Mesh) })
        portes.push({ noeud: objet, repos, ouverte, ouverture: 0, meshes })
      }
    })
    const dansUnePorte = new Set<Mesh>(portes.flatMap((p) => [...p.meshes]))
    const solides: Mesh[] = []
    this.racine.traverse((objet) => {
      const m = objet as Mesh
      if (!m.isMesh) return
      const g = m.geometry as BufferGeometry & { boundsTree?: unknown }
      if (!g.boundsTree) computeBoundsTree.call(g)
      m.raycast = acceleratedRaycast
      if (!traversable(m) && !dansUnePorte.has(m)) solides.push(m)
    })
    this.solides = solides
    this.portes = portes
    this.boite.setFromObject(this.racine)
  }

  get nombrePortes(): number { return this.portes.length }

  private tirer(origine: Vector3, direction: Vector3, distance: number): Intersection | undefined {
    this.rayon.set(origine, direction)
    this.rayon.near = 0
    this.rayon.far = distance
    return this.rayon.intersectObjects(this.solides, false)[0]
  }

  /** Hauteur du sol sous (x, z) en partant de `depuis` ; null s'il n'y a rien dessous. */
  solSous(x: number, z: number, depuis: number): number | null {
    const touche = this.tirer(new Vector3(x, depuis, z), BAS, depuis - this.boite.min.y + 60)
    return touche ? touche.point.y : null
  }

  /** Place le marcheur au départ du moteur (repère du modèle), ou au centre, posé sur le sol. */
  placer(depart: Depart | null): void {
    let x: number, z: number, depuis: number
    if (depart) {
      const monde = this.racine.localToWorld(new Vector3(depart.x, depart.y ?? 0, depart.z))
      x = monde.x
      z = monde.z
      depuis = monde.y + 2.0
      const [dx, dz] = depart.direction ?? [0, -1]
      const directionMonde = this.racine.localToWorld(new Vector3(depart.x + dx, depart.y ?? 0, depart.z + dz)).sub(monde)
      this.lacet = Math.atan2(-directionMonde.x, -directionMonde.z)
    } else {
      const centre = this.boite.getCenter(new Vector3())
      x = centre.x
      z = centre.z
      depuis = this.boite.max.y + 1
    }
    const sol = this.solSous(x, z, depuis)
    this.pieds.set(x, sol ?? this.boite.min.y, z)
    this.vy = 0
    this.auSol = sol !== null
    this.tangage = 0
  }

  tourner(dx: number, dy: number, sensibilite = 0.0022): void {
    this.lacet -= dx * sensibilite
    this.tangage = Math.max(-1.45, Math.min(1.45, this.tangage - dy * sensibilite))
  }

  oeil(): Vector3 {
    return this.pieds.clone().add(new Vector3(0, MARCHE.yeux, 0))
  }

  orientation(): Quaternion {
    return new Quaternion().setFromEuler(new Euler(this.tangage, this.lacet, 0, 'YXZ'))
  }

  /** Déplacement horizontal voulu, raccourci et glissé le long des murs (rayons aux genoux, à la taille, à la
   *  tête) ; itératif et borné, pour qu'un angle de pièce ne fasse jamais boucler la glissade. */
  private glisser(deplacement: Vector3): Vector3 {
    const total = new Vector3()
    let d = deplacement.clone()
    for (let essai = 0; essai < 4 && d.lengthSq() > 1e-12; essai += 1) {
      const longueur = d.length()
      const direction = d.clone().divideScalar(longueur)
      const base = this.pieds.clone().add(total)
      let mur: Intersection | undefined
      let normaleMur = new Vector3()
      // le rayon le plus bas passe AU-DESSUS de la plus haute marche franchissable, sinon il la prend pour un mur
      for (const h of [MARCHE.pas + 0.05, 0.95, 1.5]) {
        const touche = this.tirer(new Vector3(base.x, base.y + h, base.z), direction, longueur + MARCHE.rayon)
        if (!touche || !touche.face) continue
        const normale = touche.face.normal.clone().transformDirection(touche.object.matrixWorld)
        if (Math.abs(normale.y) >= MARCHE.sol) continue           // un sol en pente se gravit, ce n'est pas un mur
        if (!mur || touche.distance < mur.distance) {
          mur = touche
          normaleMur = normale
        }
      }
      if (!mur) {
        total.add(d)
        break
      }
      normaleMur.y = 0
      if (normaleMur.lengthSq() < 1e-8) break
      normaleMur.normalize()
      if (normaleMur.dot(direction) > 0) normaleMur.negate()
      const libre = Math.max(0, mur.distance - MARCHE.rayon)
      const avance = direction.clone().multiplyScalar(Math.min(longueur, libre))
      total.add(avance)
      const reste = d.clone().sub(avance)
      reste.addScaledVector(normaleMur, -reste.dot(normaleMur))    // on garde la composante le long du mur
      d = reste
    }
    return total
  }

  pas(dt: number, c: Commandes): void {
    const t = Math.min(Math.max(dt, 0), 0.05)
    const avant = new Vector3(-Math.sin(this.lacet), 0, -Math.cos(this.lacet))
    const droite = new Vector3(Math.cos(this.lacet), 0, -Math.sin(this.lacet))
    const voulu = new Vector3()
    if (c.avant) voulu.add(avant)
    if (c.arriere) voulu.sub(avant)
    if (c.droite) voulu.add(droite)
    if (c.gauche) voulu.sub(droite)
    if (this.vol) {
      if (voulu.lengthSq() > 0) voulu.normalize().multiplyScalar(MARCHE.vol * (c.courir ? 3 : 1) * t)
      this.pieds.add(voulu)
      if (c.monter) this.pieds.y += MARCHE.vol * t
      if (c.descendre) this.pieds.y -= MARCHE.vol * t
      this.ouvrirPortes(t)
      return
    }
    if (voulu.lengthSq() > 0) voulu.normalize().multiplyScalar((c.courir ? MARCHE.course : MARCHE.marche) * t)
    this.pieds.add(this.glisser(voulu))
    // sol : on cherche depuis la hauteur d'une marche ; on colle aux descentes douces quand on marchait
    const sol = this.solSous(this.pieds.x, this.pieds.z, this.pieds.y + MARCHE.pas)
    if (c.sauter && this.auSol) {
      this.vy = MARCHE.saut
      this.auSol = false
    }
    if (sol !== null && this.vy <= 0 && sol >= this.pieds.y - (this.auSol ? 0.3 : 0.02)) {
      this.pieds.y = sol
      this.vy = 0
      this.auSol = true
    } else {
      this.vy -= MARCHE.gravite * t
      this.pieds.y += this.vy * t
      this.auSol = false
      if (sol !== null && this.pieds.y <= sol) {
        this.pieds.y = sol
        this.vy = 0
        this.auSol = true
      }
    }
    if (this.pieds.y < this.boite.min.y - 30) this.placer(null)    // tombé hors du monde : on revient au centre
    this.ouvrirPortes(t)
  }

  /** Les portes proches s'ouvrent, les autres se referment ; leurs vantaux ne bloquent jamais le passage. */
  ouvrirPortes(dt: number): void {
    const oeil = this.oeil()
    for (const p of this.portes) {
      const position = p.noeud.getWorldPosition(new Vector3())
      const distance = Math.hypot(position.x - oeil.x, position.z - oeil.z)
      const cible = distance < MARCHE.porte && Math.abs(position.y - this.pieds.y) < 2.5 ? 1 : 0
      p.ouverture += (cible - p.ouverture) * Math.min(1, dt * 3)
      p.noeud.quaternion.slerpQuaternions(p.repos, p.ouverte, p.ouverture)
    }
  }

  /** Ouverture moyenne des portes (0 = toutes fermées) : pour les tests et l'interface. */
  ouvertures(): number[] {
    return this.portes.map((p) => p.ouverture)
  }
}
