// ---------------------------------------------------------------------------
// codeSystemPromptProductShapes — procedural 3D product prompt recipes.
// ---------------------------------------------------------------------------

import type { BrandProfile } from './codeIntent.ts'

// Generate Three.js recipe per productShape: rotating 3D brand product with texture mapping.
export function describeProductShapeHint(
  shape: NonNullable<NonNullable<BrandProfile['productShape']>>,
  brandName: string,
  primaryColor: string,
): string | null {
  const fallback = `- Construis un objet 3D recognoscible pour ${brandName} via Three.js (CDN jsdelivr 0.160). Texture optionnelle depuis PLACEHOLDER_SUBJECT_IMG_1.`
  const baseImports = '`import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"; import { OrbitControls } from "https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/controls/OrbitControls.js";`'
  const lighting = '- Eclairage PBR: HemisphereLight(0xffffff,0x222222,0.6) + DirectionalLight(0xffffff,1.6, position(5,8,5), castShadow:true) + PointLight accent couleur primaire (intensity 0.7).'
  const composer = '- WebGLRenderer({antialias:true,alpha:true}), pixelRatio min(devicePixelRatio,2), outputColorSpace=SRGBColorSpace, toneMapping=ACESFilmicToneMapping.'
  const orbitAuto = '- OrbitControls(enableDamping:true, dampingFactor:0.06, autoRotate:true, autoRotateSpeed:1.2). Camera PerspectiveCamera(45 fov), distance ~3-5 unites, regard centre.'
  const lib = '- ' + baseImports
  // Fresnel halo shader bound to productShape in caller — no per-recipe reminder needed.

  switch (shape) {
    case 'can':
      return [
        `- Hero 3D pour ${brandName}: une CANETTE en CylinderGeometry (radius 0.5, height 1.5, radialSegments 64).`,
        lib,
        '- 3 materials: top/bottom MeshPhysicalMaterial (couleur primaire metallise, metalness:0.85, roughness:0.25), label cylindre lateral MeshStandardMaterial avec map = TextureLoader().load(PLACEHOLDER_SUBJECT_IMG_1).',
        '- Pour mapper la label correctement: clone la geometry, mark groups (top, bottom, side), assign materials par index.',
        `- Bevel sur les bords (top/bottom edges) via SubtractGeometry ou simple capsule fillet (rayon 0.05) pour eviter aretes vives.`,
        `- Reflection environment: scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment()).texture pour reflets metalliques.`,
        composer,
        lighting,
        orbitAuto,
        `- Ambiance: la canette ${brandName} flotte au centre, fond gradient ${primaryColor} → noir, particles bulles (Points + sin float) montent en arriere-plan.`,
      ].join('\n')
    case 'bottle':
      return [
        `- Hero 3D pour ${brandName}: une BOUTEILLE faite en LatheGeometry (silhouette dessinee point par point) ou CapsuleGeometry stretched.`,
        lib,
        '- LatheGeometry est preferable: definis 8-12 points (x,y) pour le profil — base large, retrecit au col, goulot etroit. radialSegments 32+.',
        '- Material: MeshPhysicalMaterial(transmission:0.9, ior:1.45, thickness:0.5, roughness:0.05, attenuationColor: brand primary, attenuationDistance:0.5) pour effet verre.',
        '- Label: PlaneGeometry incurvee enroulee autour du corps avec MeshStandardMaterial map = PLACEHOLDER_SUBJECT_IMG_1 (utilise CylinderGeometry interieur OU shader UV-mapped).',
        '- Bouchon: CylinderGeometry petite hauteur sur le top, couleur secondaire metallise.',
        composer,
        lighting,
        orbitAuto,
        `- Ambiance: bouteille ${brandName} sur fond ${primaryColor} estompe, condensation simulees via NoiseTexture sur le glass material, gouttes en SphereGeometry tiny dispersees (instancied).`,
      ].join('\n')
    case 'phone':
      return [
        `- Hero 3D pour ${brandName}: un SMARTPHONE en BoxGeometry rounded (BoxGeometry(0.7, 1.45, 0.08)) avec CSG bevel ou simple double box (corps + ecran).`,
        lib,
        '- 2 materials: corps MeshPhysicalMaterial(metalness:0.85, roughness:0.18, color:0x222) ou couleur titanium si Apple, ecran face avant MeshBasicMaterial map=PLACEHOLDER_SUBJECT_IMG_1.',
        '- Pour le ecran: PlaneGeometry(0.66, 1.41) collee a z=0.041 du corps avec material screen.',
        '- Camera: 3 cylindres minuscules sur le dos (camera array iPhone Pro / Galaxy).',
        composer,
        lighting,
        orbitAuto,
        `- Ambiance: phone ${brandName} flottant, environment subtle, fond noir mat avec gradient radial primaire au centre.`,
      ].join('\n')
    case 'tablet':
      return [
        `- Hero 3D pour ${brandName}: TABLETTE en BoxGeometry(1.7, 2.2, 0.08) avec ecran PlaneGeometry texturee PLACEHOLDER_SUBJECT_IMG_1.`,
        lib,
        '- Material corps MeshPhysicalMaterial argent/silver (metalness:0.9, roughness:0.2). Ecran MeshBasicMaterial map=image.',
        composer, lighting, orbitAuto,
        `- Ambiance: tablette ${brandName} en perspective 3/4, lumiere studio depuis haut-droite.`,
      ].join('\n')
    case 'laptop':
      return [
        `- Hero 3D pour ${brandName}: LAPTOP en 2 BoxGeometry articulees (base + ecran) avec un Group + ecran ouvert a 110 degres.`,
        lib,
        '- Base BoxGeometry(2, 0.08, 1.4), ecran BoxGeometry(2, 1.3, 0.04) translate.y=base.height/2, rotation.x=Math.PI*0.6 (110deg).',
        '- Ecran face: PlaneGeometry texturee PLACEHOLDER_SUBJECT_IMG_1.',
        '- Material aluminium MeshPhysicalMaterial(color:0xc0c0c0, metalness:0.95, roughness:0.15).',
        composer, lighting, orbitAuto,
        `- Ambiance: laptop ${brandName} flottant, fond gradient gris fonce. Apple style.`,
      ].join('\n')
    case 'shoe':
      return [
        `- Hero 3D pour ${brandName}: une SNEAKER procedurale via ExtrudeGeometry depuis Shape (semelle silhouette dessinee).`,
        lib,
        '- Shape: ovale allonge stylise (toe rond, talon pointu). ExtrudeSettings: depth:0.6, bevelEnabled:true, bevelThickness:0.04.',
        '- Body sneaker: scale Y pour donner du volume, plusieurs Mesh empiles (semelle blanche + corps couleur brand + accents).',
        '- Texture optional: PLACEHOLDER_SUBJECT_IMG_1 sur PlaneGeometry pour le swoosh/logo lateral.',
        composer, lighting, orbitAuto,
        `- Ambiance: sneaker ${brandName} flottante en angle 3/4, fond gradient noir, leger flare lumineux.`,
      ].join('\n')
    case 'car':
      return [
        `- Hero 3D pour ${brandName}: VOITURE composee de Box + Cylinder primitives (silhouette stylisee, pas un GLB exact).`,
        lib,
        '- Body: BoxGeometry(2.2, 0.5, 1) chassis, BoxGeometry(1.4, 0.4, 0.95) habitacle au-dessus (centre).',
        '- Roues: 4 CylinderGeometry(0.3, 0.3, 0.18, 32), rotation.z=Math.PI/2, positions aux 4 coins.',
        '- Phares: 2 SphereGeometry(0.08) MeshBasicMaterial blanc emissif a l avant.',
        '- Material body MeshPhysicalMaterial(color:brand primary, metalness:0.7, roughness:0.25, clearcoat:0.6, clearcoatRoughness:0.15) pour vernis auto.',
        '- Vitres: BoxGeometry(1.3, 0.35, 0.92) au-dessus habitacle, MeshPhysicalMaterial(transmission:0.9, color:0x0a0a0a).',
        composer, lighting, orbitAuto,
        `- Ambiance: voiture ${brandName} sur sol ground (PlaneGeometry 50x50 receveur d ombres), fond gradient sombre, lumiere studio multipoint.`,
      ].join('\n')
    case 'watch':
      return [
        `- Hero 3D pour ${brandName}: MONTRE = CylinderGeometry slim (radius 0.6, height 0.18) pour le boitier + RingGeometry pour la lunette + cadran texture.`,
        lib,
        '- Boitier: CylinderGeometry MeshPhysicalMaterial gold/silver (metalness:0.95, roughness:0.12).',
        '- Cadran: PlaneGeometry circulaire(radius 0.5) avec MeshStandardMaterial map=PLACEHOLDER_SUBJECT_IMG_1.',
        '- Bracelet: PlaneGeometry curvee (CatmullRomCurve3) ou simple BoxGeometry segments empiles.',
        '- Aiguilles: 2-3 BoxGeometry tres fines au centre (avec rotation animee).',
        composer, lighting, orbitAuto,
        `- Ambiance: montre ${brandName} en plan rapproche 3/4, fond noir profond, leger spot lumineux qui revele le luxe.`,
      ].join('\n')
    case 'bag':
      return [
        `- Hero 3D pour ${brandName}: SAC LUXE = BoxGeometry rounded (1.4, 1, 0.5) + 2 CylinderGeometry handles arques (TorusGeometry partiel).`,
        lib,
        '- Body: BoxGeometry rounded edges (CSG ou bevel), MeshStandardMaterial map=PLACEHOLDER_SUBJECT_IMG_1 (le monogram texture du brand).',
        '- Handles: 2 TorusGeometry(0.2, 0.025, 16, 32) en haut, couleur or/argent metallise.',
        '- Fermoir: BoxGeometry petit accent dore au centre devant.',
        composer, lighting, orbitAuto,
        `- Ambiance: sac ${brandName} sur podium (CylinderGeometry plat), fond degrade ${primaryColor}, spotlights theatre fashion.`,
      ].join('\n')
    case 'headphones':
      return [
        `- Hero 3D pour ${brandName}: CASQUE AUDIO = TorusGeometry (arc bandeau) + 2 CylinderGeometry (oreillettes).`,
        lib,
        '- Bandeau: TorusGeometry(0.5, 0.05, 16, 64, Math.PI) demi-tor.',
        '- Oreillettes: 2 CylinderGeometry(0.25, 0.25, 0.2, 32) aux extremites du bandeau.',
        '- Material MeshPhysicalMaterial(color: brand primary, metalness:0.4, roughness:0.5, clearcoat:0.3).',
        composer, lighting, orbitAuto,
        `- Ambiance: casque ${brandName} flottant, lumieres concert (lumieres colorees primaire + secondaire), reflets noisette.`,
      ].join('\n')
    case 'controller':
      return [
        `- Hero 3D pour ${brandName}: MANETTE GAMING = forme custom via plusieurs Box + Sphere (silhouette DualSense / Xbox).`,
        lib,
        '- Body central: BoxGeometry rounded(1.6, 0.8, 0.5) + 2 grips lateraux Cylinder(0.3, 0.3, 0.6) places en bas-gauche/droite.',
        '- Boutons: 4 SphereGeometry(0.06) couleur primaire/secondaire en croix sur la droite.',
        '- Joysticks: 2 CylinderGeometry(0.08, 0.08, 0.1) + sphere top (0.08).',
        '- Trigger: 2 BoxGeometry petits sur le top.',
        '- Material body MeshPhysicalMaterial blanc/noir glossy.',
        composer, lighting, orbitAuto,
        `- Ambiance: controller ${brandName} flottant, fond gradient sombre tech, leger glow primary sous le LED.`,
      ].join('\n')
    case 'console':
      return [
        `- Hero 3D pour ${brandName}: CONSOLE = BoxGeometry slab (3, 0.5, 1.2) avec details proeminents (Switch screen, PS5 disc slot, Xbox vent).`,
        lib,
        '- Body principal MeshPhysicalMaterial blanc/noir glossy.',
        '- Si Switch: 2 BoxGeometry detachables (Joy-Con) sur les cotes, ecran central PlaneGeometry texturee.',
        '- Logo: emboss subtle ou texture sur top.',
        composer, lighting, orbitAuto,
        `- Ambiance: console ${brandName} flottante en perspective, fond ${primaryColor} radial, glow neon underline.`,
      ].join('\n')
    case 'card':
      return [
        `- Hero 3D pour ${brandName}: CARTE BANCAIRE = BoxGeometry flat(2.4, 1.5, 0.04) avec gradient primaire shader.`,
        lib,
        '- Material front: ShaderMaterial avec uv-mapped gradient primaire→secondaire animated, plus map texture optionnelle PLACEHOLDER_SUBJECT_IMG_1 (logo brand au coin).',
        '- Embossing chip: petit BoxGeometry dore (0.25 x 0.18 x 0.005) translate.z=0.022.',
        '- Numeros embosses: optionnel via TextGeometry avec font fetched from cdn.',
        composer, lighting, orbitAuto,
        `- Ambiance: carte ${brandName} flottante en angle 35deg, fond gradient ${primaryColor} → noir, reflets metalliques iridescents.`,
      ].join('\n')
    case 'cup':
      return [
        `- Hero 3D pour ${brandName}: GOBELET / MUG = CylinderGeometry tapered (top radius > bottom radius) + anse optionnelle TorusGeometry.`,
        lib,
        '- CylinderGeometry(0.5, 0.4, 1.2, 64) pour le corps tapered.',
        '- Material extérieur MeshStandardMaterial map=PLACEHOLDER_SUBJECT_IMG_1 (logo siren / brand).',
        '- Cafe interieur: Mesh CylinderGeometry interne (radius 0.45, height 0.05) MeshStandardMaterial brun cafe (chocolate).',
        '- Vapeur: Particle system (Points) au-dessus du gobelet, opacity 0.3, mouvement up.',
        composer, lighting, orbitAuto,
        `- Ambiance: gobelet ${brandName} avec vapeur cafe qui monte, fond gradient warm chaleureux.`,
      ].join('\n')
    case 'logo':
      return [
        `- Hero 3D pour ${brandName}: LOGO en relief = ExtrudeGeometry depuis Shape SVG du logo (charge via SVGLoader).`,
        lib,
        '- Si SVG du logo dispo (ou reconstruct via Path): ExtrudeSettings depth:0.2, bevelEnabled:true.',
        '- Material MeshPhysicalMaterial(color:primary, metalness:0.8, roughness:0.15, clearcoat:0.6).',
        '- Alternativement: TextGeometry(brandName, font, size:1, height:0.2) charge depuis https://threejs.org/examples/fonts/helvetiker_bold.typeface.json.',
        composer, lighting, orbitAuto,
        `- Ambiance: logo ${brandName} flotte au centre, particles thematiques en arriere (etoiles, traits, geometric), fond ${primaryColor} radial.`,
      ].join('\n')
    case 'building':
      return [
        `- Hero 3D pour ${brandName}: SCENE BATIMENT = BoxGeometry composees (corps + toit + cheminee + fenetres).`,
        lib,
        '- Corps: BoxGeometry(2, 1.5, 1.5).',
        '- Toit: ConeGeometry ou BoxGeometry rotated (slope 30deg), couleur primaire.',
        '- Fenetres: 4-6 PlaneGeometry orange/jaune emissives sur les faces.',
        '- Sol: PlaneGeometry receveur ombres (verdure subtle).',
        composer, lighting, orbitAuto,
        `- Ambiance: maison ${brandName} accueillante, soleil couchant lumiere chaude, scene paysage.`,
      ].join('\n')
    default:
      return fallback
  }
}
