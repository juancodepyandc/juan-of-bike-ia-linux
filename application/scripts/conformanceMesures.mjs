/**
 * Mesures comportementales inter-modules.
 *
 * Contrainte de conception : chaque mesure n'appelle QUE des fonctions deja
 * exportees AVANT correction. C'est ce qui permet de faire tourner le meme
 * banc sur les DEUX etats du code et de comparer des NOMBRES, au lieu de
 * constater qu'un fichier ne se charge plus.
 *
 * Chaque mesure rend un entier « nombre de defauts » : 0 = conforme.
 */
const cacheBust = `?t=${Date.now()}${Math.random()}`
const charge = (chemin) => import(new URL(`../${chemin}${cacheBust}`, import.meta.url).href)

export async function mesure() {
  const out = []
  const ajoute = (module, quoi, defauts, detail) => out.push({ module, quoi, defauts, detail })

  // --- 1. VOIX -------------------------------------------------------------
  {
    const { phonemizeWord } = await charge('src/services/voiceFrPhonemizer.ts')
    const corpus = [
      ['petit', 'pəti'], ['beaucoup', 'boku'], ['grand', 'ɡʁɑ̃'],
      ['parlez', 'paʁle'], ['bonne', 'bɔn'], ['homme', 'ɔm'], ['fille', 'fij'],
      ['travail', 'tʁavaj'], ['bonjour', 'bɔ̃ʒuʁ'], ['femme', 'fam'],
      ['monsieur', 'məsjø'], ['table', 'tabl'], ['chat', 'ʃa'], ['nous', 'nu'],
      ['est', 'ɛ'], ['pied', 'pje'], ['comment', 'kɔmɑ̃'],
    ]
    const cls = (s) => s.replace(/ɔ(?!̃)/g, 'o').replace(/ɑ(?!̃)/g, 'a')
    const faux = corpus.filter(([m, a]) => cls(phonemizeWord(m).join('')) !== cls(a))
    ajoute('voix', 'prononciation francaise', faux.length,
      `${corpus.length - faux.length}/${corpus.length} mots justes`)
  }

  // --- 2. VIDEO / sous-titres ---------------------------------------------
  {
    const { exportSrt } = await charge('src/services/videoSubtitleExport.ts')
    let d = 0
    const details = []
    if (/,\d{3}[.\d]/.test(exportSrt([{ startMs: 1500.5, endMs: 3200.75, text: 'x' }]))) {
      d += 1; details.push('temps fractionnaire malforme')
    }
    if (exportSrt([{ startMs: -500, endMs: 1000, text: 'x' }]).includes('-1:')) {
      d += 1; details.push('temps negatif malforme')
    }
    const fleche = exportSrt([{ startMs: 0, endMs: 1000, text: 'de 10 --> 100' }])
    if ((fleche.match(/-->/g) ?? []).length > 1) { d += 1; details.push('fleche non neutralisee') }
    const vide = exportSrt([
      { startMs: 0, endMs: 1000, text: ['a', '', 'b'].join(String.fromCharCode(10)) },
      { startMs: 1000, endMs: 2000, text: 'c' },
    ])
    if (vide.split(/\n\s*\n/).filter((b) => b.trim()).length !== 2) {
      d += 1; details.push('ligne vide scinde la replique')
    }
    ajoute('video', 'conformite SRT', d, details.join(' ; ') || 'les 4 entrees piegeuses passent')
  }

  // --- 3. VIDEO / tempo ----------------------------------------------------
  {
    const { detectBpm, syntheticBeatSignal } = await charge('src/services/videoTempoDetector.ts')
    const tempos = [60, 72, 90, 100, 110, 120, 128, 140, 150, 160, 174]
    const ecarts = tempos.map((v) => Math.abs(detectBpm(syntheticBeatSignal(v, 10, 44100), 44100).bpm - v))
    const hors = ecarts.filter((e) => e > 2).length
    const moyen = ecarts.reduce((a, b) => a + b, 0) / ecarts.length
    ajoute('video', 'detection de tempo', hors,
      `ecart moyen ${moyen.toFixed(2)} BPM sur ${tempos.length} tempos`)
  }

  // --- 4. CYBER ------------------------------------------------------------
  {
    const { railFence, toBase64 } = await charge('src/services/cyber/cryptoService.ts')
    let ko = 0
    for (let len = 1; len <= 40; len += 1) {
      let s = ''
      for (let j = 0; j < len; j += 1) s += (j % 3 === 0 ? '🙂' : 'a')
      for (let r = 2; r <= 8; r += 1) if (railFence(railFence(s, r), r, true) !== s) ko += 1
    }
    let leve = 0
    try { toBase64('salut 🙂'.slice(0, 7)) } catch { leve = 1 }
    ajoute('cyber', 'haie + base64', ko + leve,
      `${ko}/280 aller-retours casses hors BMP ; base64 ${leve ? 'LEVE UNE EXCEPTION' : 'ne leve pas'}`)
  }

  // --- 5. COWORK -----------------------------------------------------------
  {
    const { isInsideWorkspace } = await charge('src/services/coworkSafety.ts')
    const racine = '/home/juan/AuroraIA/workspace'
    const NUL = String.fromCharCode(0)
    const LF = String.fromCharCode(10)
    const CR = String.fromCharCode(13)
    const pieges = [
      `${racine}${NUL}/../../etc/passwd`,
      `${racine}/a${NUL}b`,
      `${racine}/a${LF}rm -rf /`,
      `${racine}/a${CR}b`,
    ]
    const passes = pieges.filter((p) => isInsideWorkspace(p, racine) === true).length
    ajoute('cowork', 'cloture du bac a sable', passes,
      `${passes}/${pieges.length} chemins a caractere de controle acceptes a tort`)
  }

  // --- 6. CODE -------------------------------------------------------------
  {
    const { containsPictographicEmoji } = await charge('src/services/codeCompositionGate.ts')
    const doitDetecter = [
      '🇫🇷', '▶️', '⭐', '⌚', '⏰',
      '1️⃣', '🚀', '📊',
    ]
    const rates = doitDetecter.filter((g) => !containsPictographicEmoji(g)).length
    const legitimes = [
      '// © 2026', 'Aurora®', '12 € — soldes', '±3 °C',
      '→', '«»', 'Aurora™',
    ]
    const fauxPositifs = legitimes.filter((s) => containsPictographicEmoji(s)).length
    ajoute('code', "detection des traces d'IA", rates + fauxPositifs,
      `${rates} emoji manque(s), ${fauxPositifs} faux positif(s) sur la typographie`)
  }

  // --- 7. IMAGE ------------------------------------------------------------
  {
    const { bestAspectRatio } = await charge('src/services/imageAspectRecommender.ts')
    const attendus = [
      ['affiche de film', '2:3'], ['banniere pour un site web', '21:9'],
      ['paysage de montagne panoramique', '21:9'], ['couverture de livre', '2:3'],
      ['miniature youtube', '16:9'], ['portrait de femme', '2:3'],
    ]
    const faux = attendus.filter(([s, r]) => bestAspectRatio(s).ratio !== r)
    ajoute('image', 'vocabulaire des formats', faux.length,
      faux.map(([s, r]) => `« ${s} » rend ${bestAspectRatio(s).ratio} au lieu de ${r}`).join(' ; ')
      || `${attendus.length}/${attendus.length} formats justes`)
  }

  // --- 8. CONVERSATION -----------------------------------------------------
  {
    const { analyzeSentiment } = await charge('src/services/conversationSentiment.ts')
    const detresse = [
      'catastrophe totale, rien ne marche', 'c est un desastre complet',
      'ras le bol de ces plantages', 'ce truc est inutilisable',
      'j en ai marre, c est un cauchemar', 'c est lamentable',
    ]
    const rates = detresse.filter((t) => analyzeSentiment(t).score >= 0).length
    ajoute('conversation', 'sentiment', rates,
      `${rates}/${detresse.length} phrases de detresse non reconnues comme negatives`)
  }

  // --- 9. APPRENTISSAGE ----------------------------------------------------
  {
    const { fuzzInterval } = await charge('src/services/learning/spacedRepetition.ts')
    let min = Infinity
    let max = -Infinity
    for (let i = 0; i < 5000; i += 1) {
      const f = fuzzInterval(1000, `carte-${i}`) / 1000
      min = Math.min(min, f); max = Math.max(max, f)
    }
    // Le module annonce +/-5 % : l'amplitude doit atteindre au moins +/-4 %.
    const conforme = max >= 1.04 && min <= 0.96
    ajoute('apprentissage', "brouillage d'intervalle", conforme ? 0 : 1,
      `amplitude mesuree [${min.toFixed(4)} ; ${max.toFixed(4)}] pour +/-5 % annonces`)
  }

  // --- 10. 3D / atlas de textures ------------------------------------------
  {
    const { packAtlas } = await charge('src/services/threeDTextureAtlas.ts')
    let chevauchants = 0
    let jeux = 0
    for (const tailles of [
      Array.from({ length: 12 }, (_, i) => ({ id: `t${i}`, width: 64 + (i % 4) * 64, height: 64 + (i % 3) * 64 })),
      Array.from({ length: 20 }, (_, i) => ({ id: `t${i}`, width: 37 + i * 13, height: 53 + i * 7 })),
      Array.from({ length: 14 }, (_, i) => ({ id: `t${i}`, width: 16 + i * 8, height: 512 - i * 16 })),
    ]) {
      jeux += 1
      const r = packAtlas(tailles)
      for (let i = 0; i < r.slots.length; i += 1) {
        for (let j = i + 1; j < r.slots.length; j += 1) {
          const a = r.slots[i]
          const b = r.slots[j]
          if (a.x < b.x + b.width && b.x < a.x + a.width
            && a.y < b.y + b.height && b.y < a.y + a.height) chevauchants += 1
        }
      }
    }
    ajoute('3D', 'atlas de textures', chevauchants,
      `${chevauchants} paire(s) de cases se chevauchent sur ${jeux} jeux de tailles variees`)
  }

  // --- 11. 3D / validateur glTF --------------------------------------------
  {
    const { validateGltfJson } = await charge('src/services/threeDGltfValidator.ts')
    const base = () => ({
      asset: { version: '2.0' }, scene: 0, scenes: [{ nodes: [0] }], nodes: [{ mesh: 0 }],
      meshes: [{ primitives: [{ attributes: { POSITION: 0 }, indices: 1, material: 0 }] }],
      materials: [{ pbrMetallicRoughness: { baseColorFactor: [1, 1, 1, 1] } }],
      accessors: [
        { bufferView: 0, componentType: 5126, count: 3, type: 'VEC3' },
        { bufferView: 1, componentType: 5123, count: 3, type: 'SCALAR' },
      ],
      bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: 36 }, { buffer: 0, byteOffset: 36, byteLength: 6 }],
      buffers: [{ byteLength: 42 }],
    })
    const violations = [
      (g) => { g.meshes[0].primitives[0].attributes.POSITION = 99 },
      (g) => { g.accessors[0].bufferView = 99 },
      (g) => { g.bufferViews[0].buffer = 99 },
      (g) => { g.bufferViews[0].byteLength = 99999 },
      (g) => { g.scenes[0].nodes = [99] },
      (g) => { g.nodes = [{ children: [1] }, { children: [0] }] },
      (g) => { g.animations = [{ channels: [{ sampler: 0, target: { node: 0, path: 'couleur' } }], samplers: [{ input: 0, output: 1 }] }] },
    ]
    let laissees = 0
    for (const casse of violations) {
      const g = base()
      casse(g)
      const r = validateGltfJson(g)
      if (!(r.hasBlocker || r.issues.some((i) => i.severity === 'error' || i.severity === 'block'))) laissees += 1
    }
    const conforme = validateGltfJson(base())
    ajoute('3D', 'validateur glTF 2.0', laissees + (conforme.valid ? 0 : 1),
      `${laissees}/${violations.length} violations non detectees ; asset conforme ${conforme.valid ? 'accepte' : 'REFUSE A TORT'}`)
  }

  // --- 12. 3D / quaternions ------------------------------------------------
  {
    const { sampleAnimation } = await charge('src/services/threeDRigRetarget.ts')
    const rotY = (a) => [0, Math.sin(a / 2), 0, Math.cos(a / 2)]
    const anim = (duration, loop, frames) => ({
      name: 't', duration, loop, frames: frames.map((f) => ({ t: f.t, rotations: { hips: f.q } })),
    })
    const cas = [
      [anim(0, true, [{ t: 0, q: rotY(0) }, { t: 0, q: rotY(1) }]), 0.5],
      [anim(2, false, [{ t: 0, q: rotY(0) }, { t: 2, q: rotY(1) }]), NaN],
      [anim(2, true, [{ t: 0, q: rotY(0) }, { t: 2, q: rotY(1) }]), Infinity],
      [anim(NaN, true, [{ t: 0, q: rotY(0) }, { t: 2, q: rotY(1) }]), 1],
    ]
    let nan = 0
    for (const [a, t] of cas) {
      const q = sampleAnimation(a, 'hips', t)
      if (!q.every(Number.isFinite)) nan += 1
    }
    ajoute('3D', 'echantillonnage de rotation', nan,
      `${nan}/${cas.length} cas degeneres rendent un quaternion NaN (le maillage disparait)`)
  }

  // --- 13. CODE / analyse de source ----------------------------------------
  {
    const { readImports, readModuleExports } = await charge('src/services/codeImportExportShape.ts')
    const leurres = [
      "// import Faux from 'faux'",
      "/* import Bidon from 'bidon' */",
      'const s = "import Chaine from \'chaine\'"',
      "import Vrai from 'vrai'",
    ].join('\n')
    const fantomesImport = readImports(leurres).map((i) => i.specifier).filter((x) => x !== 'vrai').length
    const exLeurres = [
      '// export const faux = 1',
      '/* export function bidon() {} */',
      'export const vrai = 3',
    ].join('\n')
    const e = readModuleExports(exLeurres)
    const fantomesExport = [...e.named].filter((x) => x !== 'vrai').length
    ajoute('code', 'analyse de source', fantomesImport + fantomesExport,
      `${fantomesImport} import(s) fantome(s), ${fantomesExport} export(s) fantome(s)`)
  }

  // --- 14. CODE / livrable non altere --------------------------------------
  {
    const { sanitizeGeneratedFileContent, tryParseJson } = await charge('src/services/codeGeneratedFileSanitizer.ts')
    let defauts = 0
    const details = []
    const readme = '# Projet\n\nInstallation :\n\n```bash\nnpm install\n```'
    if (sanitizeGeneratedFileContent('README.md', readme) !== readme) {
      defauts += 1; details.push('README ampute de sa cloture')
    }
    const jsonAltere = tryParseJson('{"note":"un, deux, }","a":1,}')
    if (!jsonAltere || jsonAltere.note !== 'un, deux, }') {
      defauts += 1; details.push('contenu de chaine JSON altere par la reparation')
    }
    ajoute('code', 'livrable non altere', defauts, details.join(' ; ') || 'README et JSON rendus intacts')
  }

  return out
}
