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

  // --- 2. CYBER ------------------------------------------------------------
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

  // --- 3. COWORK -----------------------------------------------------------
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

  // --- 4. CODE -------------------------------------------------------------
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

  // --- 5. IMAGE ------------------------------------------------------------
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

  // --- 6. CONVERSATION -----------------------------------------------------
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

  // --- 7. APPRENTISSAGE ----------------------------------------------------
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

  // --- 8. 3D / atlas de textures ------------------------------------------
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

  // --- 9. 3D / validateur glTF --------------------------------------------
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

  // --- 10. 3D / quaternions ------------------------------------------------
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

  // --- 11. CODE / analyse de source ----------------------------------------
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

  // --- 12. CODE / livrable non altere --------------------------------------
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

  // --- 13. DESSIN / detection d'intention explicative ----------------------
  {
    const { isExplanatoryDrawing } = await charge('src/services/drawingExplanation.ts')
    const explicatifs = [
      'explique le fonctionnement de ce moteur', 'schema technique du circuit',
      'diagramme de flux du processus', 'comment ca marche, en schema',
    ]
    const artistiques = [
      'dessine un coucher de soleil au pastel', 'crocquis artistique d un portrait',
      'illustre une scene de fete', 'peins un paysage impressionniste',
    ]
    const faux = explicatifs.filter((t) => !isExplanatoryDrawing(t))
    const fauxPositifs = artistiques.filter((t) => isExplanatoryDrawing(t))
    ajoute('dessin', 'detection dessin explicatif', faux.length + fauxPositifs.length,
      `${faux.length} explicatif(s) non reconnu(s), ${fauxPositifs.length} artistique(s) pris(s) pour un schema`)
  }

  // --- 14. DESSIN / lissage geometrique (rdp + beziers) --------------------
  {
    const { rdp, smoothPolyline } = await charge('src/services/drawingCurveSmoothing.ts')
    let defauts = 0
    const details = []
    const carre = []
    for (let i = 0; i <= 100; i += 1) carre.push({ x: Math.round(i * 0.3 * 10) / 10, y: Math.round(i * 0.3 * 10) / 10 })
    const reduit = rdp(carre, 2)
    if (reduit.length > 4) { defauts += 1; details.push(`rdp garde ${reduit.length} points sur une droite`) }
    const path = smoothPolyline(carre, { epsilon: 2 })
    if (!path.path.startsWith('M')) { defauts += 1; details.push('chemin SVG sans commande initiale') }
    if (path.beziers.length === 0) { defauts += 1; details.push('aucune courbe de bezier produite') }
    ajoute('dessin', 'lissage geometrique', defauts, details.join(' ; ') || 'rdp reduit, beziers produits, chemin SVG valide')
  }

  // --- 15. APPRENTISSAGE / reprises dues et ordre ---------------------------
  {
    const { makeNewCard, review, pickDueCards, RATING } = await charge('src/services/learning/spacedRepetition.ts')
    const maintenant = new Date('2026-01-01T00:00:00.000Z')
    const deck = [
      { card: makeNewCard(maintenant), extra: 'a' },
      { card: makeNewCard(maintenant), extra: 'b' },
    ]
    deck[0].card = review(deck[0].card, RATING.Good, maintenant).card
    deck[1].card = review(deck[1].card, RATING.Good, maintenant).card
    const pasDue = new Date('2026-01-01T01:00:00.000Z')
    let faux = 0
    if (pickDueCards(deck, pasDue, Infinity).length !== 0) faux += 1
    const plusTard = new Date('2031-01-01T00:00:00.000Z')
    const dues = pickDueCards(deck, plusTard, Infinity)
    if (dues.length !== 2) faux += 1
    ajoute('apprentissage', 'planification des reprises', faux,
      `${faux === 0 ? 'aucune carte due avant terme, toutes recalees ensuite' : `${faux} anomalie(s)`}`)
  }

  // --- 16. IMAGE / classification des edits ---------------------------------
  {
    const { classifyImageEditRequest } = await charge('src/services/imageConversationContract.ts')
    const cas = [
      ['remplace l arriere-plan par une plage', '', 'decorChange'],
      ['ajoute un chat noir sur ce canape', '', 'addedCharacter'],
      ['change ma tenue en robe rouge', 'ref.jpg', 'humanPhotoEdit'],
      ['le bras autour de son epaule, en amis', 'ref.jpg', 'socialInteraction'],
    ]
    const erreurs = []
    for (const [p, r, attendu] of cas) {
      const d = classifyImageEditRequest(p, r === 'ref.jpg')
      const touches = Object.entries(d).filter(([, v]) => v).map(([k]) => k)
      if (!touches.includes(attendu)) erreurs.push(`« ${p} » : ${touches.join('+') || 'rien'} au lieu de ${attendu}`)
    }
    ajoute('image', 'classification des edits', erreurs.length,
      erreurs.join(' ; ') || `${cas.length}/${cas.length} demandes d'edition classees`)
  }

  // --- 17. VOIX / liaisons et prosodie -------------------------------------
  {
    const { detectLiaison, phonemizeSentence } = await charge('src/services/voiceFrPhonemizer.ts')
    const { generateSsml } = await charge('src/services/voiceProsody.ts')
    let ko = 0
    const attents = [
      ['les', 'enfants'], ['des', 'amis'], ['nous', 'avons'], ['un', 'arbre'],
    ]
    for (const [a, b] of attents) if (detectLiaison(a, b) === '') ko += 1
    const interdit = [
      ['les', 'héros'], ['les', 'huit'], ['la', 'haine'],
    ]
    for (const [a, b] of interdit) if (detectLiaison(a, b) !== '') ko += 1
    const ssml = generateSsml('Bonjour ! Comment allez-vous ?', 1.0)
    if (!ssml.includes('<speak>') || !ssml.includes('</speak>')) ko += 1
    const fantomes = phonemizeSentence('bonjour').filter((s) => /[0-9]/.test(s)).length
    ajoute('voix', 'liaisons + prosodie', ko + fantomes,
      `${ko} liaison(s) fausse(s) ; ${fantomes} chiffre(s) evocant des sons dans la phonetisation`)
  }

  // --- 18. CONVERSATION / routage d'intention -------------------------------
  {
    const { routeIntent } = await charge('src/services/intentRouter.ts')
    const cas = [
      ['genere moi un jeu de plateforme', 'code'],
      ['dessine un paysage', 'image'],
      ['resume la scene en 3d', '3d'],
      ['exploite la faille xss', 'cyber'],
      ['hash ce mot de passe', 'cyber'],
      ['analyse ce malware', 'cyber'],
    ]
    const faux = []
    for (const [texte, attendu] of cas) {
      let r
      try { r = routeIntent(texte) } catch { r = null }
      const module = (r && r.moduleId) || (typeof r === 'string' ? r : null)
      if (!module || !String(module).toLowerCase().includes(attendu.toLowerCase().slice(0, 3))) {
        faux.push(`« ${texte} » -> ${module ?? 'aucun'}`)
      }
    }
    ajoute('conversation', 'routage d intention', faux.length,
      faux.join(' ; ') || `${cas.length}/${cas.length} intentions routees vers le bon module`)
  }

  // --- 19. COWORK / format des rendus d'extraction ---------------------------
  {
    const { formatYieldPct, colorToneForUnderExtractionRate, renderDeltaSparkline } = await charge('src/services/coworkExtractionStats.ts')
    let ko = 0
    if (!/^[0-9]+([.,][0-9])?%$/.test(formatYieldPct(0.1234))) ko += 1
    const r = colorToneForUnderExtractionRate(0)
    if (!r) ko += 1
    const line = renderDeltaSparkline([1, 2, 3, 4])
    if (!line || typeof line !== 'string') ko += 1
    ajoute('cowork', 'rendus d extraction', ko,
      ko === 0 ? 'pourcentage, jauge et sparkline formatables' : `${ko} rendu(s) en echec`)
  }

  // --- 20. MÉMOIRE / store, rappel et élagage -------------------------------
  {
    const { createMemoryStore, addMemory, retrieve, prune, MEMORY_STORE_VERSION } = await charge('src/services/conversationMemory.ts')
    let defauts = 0
    const details = []
    let store = createMemoryStore()
    if (!store || store.version !== MEMORY_STORE_VERSION) { defauts += 1; details.push('version du store inattendue') }
    const base = new Date('2026-01-01T00:00:00.000Z')
    store = addMemory(store, { kind: 'fact', text: 'Le serveur tourne sur le port 3001', importance: 0.9 }, base)
    store = addMemory(store, { kind: 'fact', text: 'Le serveur tourne sur le port 3001', importance: 0.9 }, base)
    if (store.entries.length !== 1) { defauts += 1; details.push(`duplicata non fusionne (${store.entries.length} entrees)`) }
    const found = retrieve(store, 'port serveur', base, { limit: 5 })
    if (found.length !== 1) { defauts += 1; details.push('rappel BM25 ne retrouve pas la memoire') }
    const vieux = addMemory(createMemoryStore(), { kind: 'fact', text: 'ancient', importance: 0.1 }, new Date('1990-01-01T00:00:00.000Z'))
    const elague = prune(vieux, { maxAgeDays: 1, now: base })
    if (elague.entries.length !== 0) { defauts += 1; details.push('elagage par age n a rien retire') }
    ajoute('memoire', 'store + rappel + elagage', defauts, details.join(' ; ') || 'dedoublonnage, BM25 et elagage operants')
  }

  // --- 21. APPRENTISSAGE / validation et notation d'exercices ---------------
  {
    const { validateExercise, scoreAttempt } = await charge('src/services/learning/exerciseFormats.ts')
    let defauts = 0
    const details = []
    const mauvais = validateExercise({ id: '', prompt: 'a', timeBudgetMin: 300, kind: 'qcm', multiAnswer: false, options: [], question: '' })
    if (mauvais.length === 0) { defauts += 1; details.push('exercice invalide accepte') }
    const bon = validateExercise({ id: 'e1', prompt: 'Quelle est la capital ?', timeBudgetMin: 2, tags: ['geo'], kind: 'qcm', multiAnswer: false, options: [{ id: 'a', text: 'Paris', correct: true }, { id: 'b', text: 'Rome', correct: false }], question: 'Quelle est la capital ?', explanation: '' })
    if (bon.length !== 0) { defauts += 1; details.push(`exercice valide refuse : ${bon.join(',')}`) }
    const malVeille = scoreAttempt({ id: 'e1', prompt: 'q', timeBudgetMin: 2, kind: 'qcm', multiAnswer: false, options: [{ id: 'a', text: 'Paris', correct: true }, { id: 'b', text: 'Rome', correct: false }], question: 'q', explanation: '' }, { kind: 'qcm', selected: ['b'] })
    if (malVeille.ratio01 !== 0) { defauts += 1; details.push('reponse fausse notee > 0') }
    const bonne = scoreAttempt({ id: 'e1', prompt: 'q', timeBudgetMin: 2, kind: 'qcm', multiAnswer: false, options: [{ id: 'a', text: 'Paris', correct: true }, { id: 'b', text: 'Rome', correct: false }], question: 'q', explanation: '' }, { kind: 'qcm', selected: ['a'] })
    if (bonne.ratio01 !== 1) { defauts += 1; details.push('reponse juste notee < 1') }
    ajoute('apprentissage', 'validation + notation', defauts, details.join(' ; ') || 'validite structurelle et notation 0/1 operantes')
  }

  // --- 22. APPRENTISSAGE / mnemotechniques ----------------------------------
  {
    const { generateAcronymMnemonic, generateAuto, chooseStrategy } = await charge('src/services/learning/mnemonicGenerator.ts')
    let defauts = 0
    const details = []
    const liste = ['algebre', 'geometrie', 'probabilite']
    const acro = generateAcronymMnemonic(liste)
    if (acro.strategy !== 'acronyme' || !acro.text || acro.text.length < 5) { defauts += 1; details.push('acronyme non genere') }
    const auto = generateAuto(liste)
    if (!auto || auto.strategy !== 'acronyme' || !auto.text) { defauts += 1; details.push('generateAuto ne produit pas de mnemotechnique') }
    const choix = chooseStrategy(liste)
    if (!choix) { defauts += 1; details.push('choix de strategie vide') }
    ajoute('apprentissage', 'mnemotechniques', defauts, details.join(' ; ') || 'acronyme, auto et strategie generent bien pour 3 items')
  }

  // --- 23. APPRENTISSAGE / pont FSRS-Leitner --------------------------------
  {
    const { leitnerToFsrs, dueNowCount, correctToFsrsRating } = await charge('src/services/learning/fsrsLeitnerBridge.ts')
    let defauts = 0
    const details = []
    const base = new Date('2026-01-01T00:00:00.000Z')
    const baseMs = base.getTime()
    const cartes = [
      { box: 1, streak: 0, dueAt: baseMs - 1000, timesCorrect: 1, timesWrong: 0 },
      { box: 2, streak: 1, dueAt: baseMs + 5000, timesCorrect: 2, timesWrong: 0 },
      { box: 1, streak: 2, dueAt: baseMs - 2000, timesCorrect: 1, timesWrong: 1 },
    ]
    if (dueNowCount(cartes, base) !== 2) { defauts += 1; details.push('dueNowCount mal compte') }
    for (const c of cartes) {
      try {
        const f = leitnerToFsrs(c, base)
        if (!Number.isFinite(new Date(f.due).getTime())) { defauts += 1; details.push(`due NaN pour box ${c.box}`) }
      } catch (e) { defauts += 1; details.push(`conversion caisse box ${c.box} : ${String(e.message).slice(0, 50)}`) }
    }
    if (correctToFsrsRating(true, 5) !== 4) { defauts += 1; details.push('rating Easy attendu apres 5 sans erreur') }
    if (correctToFsrsRating(false, 0) === 4) { defauts += 1; details.push('reponse fausse notee Easy') }
    ajoute('apprentissage', 'pont FSRS-Leitner', defauts, details.join(' ; ') || 'comptage, conversion et rating operants')
  }

  // --- 24. CHARACTER FORGE / contrat d'etapes -------------------------------
  {
    const { FORGE_STEPS, ForgeStepStatus } = await charge('src/services/characterForge.ts')
    const ids = FORGE_STEPS.map((s) => s.id)
    const attendus = ['intent', 'traits', 'rig_plan', 'reference', 'expressions', 'segment', 'assemble', 'publish']
    const manquants = attendus.filter((a) => !ids.includes(a))
    const doublons = new Set(ids).size !== ids.length
    ajoute('character', 'contrat etapes forge', manquants.length + (doublons ? 1 : 0),
      `${manquants.length} etape(s) manquante(s)${doublons ? ' ; id dupliques' : ''} sur ${FORGE_STEPS.length}`)
  }

  // --- 25. 3D / sérialisation du mouvement pour Blender ---------------------
  {
    const { serializeMotionForBlender } = await charge('src/services/motionSerializer.ts')
    let defauts = 0
    const details = []
    const desc = { name: 'marche', duration_seconds: 0.5, loop: true, tokens: ['marche'] }
    try {
      const out = serializeMotionForBlender(desc, { fps: 24 })
      if (!out || typeof out !== 'object') { defauts += 1; details.push('sortie non objet') }
      else {
        if (out.schema !== 'aurora.motion.v1') { defauts += 1; details.push('schema absent') }
        if (!out.fps || out.fps !== 24) { defauts += 1; details.push('fps absent/invalide') }
        if (!Array.isArray(out.primitives)) { defauts += 1; details.push('primitives absent') }
      }
    } catch (e) { defauts += 1; details.push(`exception : ${String(e.message).slice(0, 80)}`) }
    ajoute('3D', 'serialisation mouvement', defauts, details.join(' ; ') || 'payload Blender schema/fps/primitives produit sans exception')
  }

  // --- 26. CYBER / analyse de robustesse d'un mot de passe -----------------
  {
    const { analyzePassword, generatePassword } = await charge('src/services/cyber/passwordAnalyzer.ts')
    let defauts = 0
    const details = []
    const faible = analyzePassword('123456')
    if (!faible || faible.score > 1 || faible.entropy >= 30) { defauts += 1; details.push('mot de passe trivial note trop fort') }
    const fort = analyzePassword('K7!xqR2$lO9#mB4zW1@')
    if (!fort || fort.score < 3 || fort.entropy < 80) { defauts += 1; details.push(`mot de passe fort sous-cote (score ${fort?.score ?? '?'}/4)`) }
    const gen = generatePassword({ lower: true, upper: true, digits: true, symbols: true, length: 16 })
    if (!gen || gen.length !== 16) { defauts += 1; details.push(`generatePassword rend ${gen?.length} caracteres sur 16`) }
    ajoute('cyber', 'analyse + generation MDP', defauts, details.join(' ; ') || 'faible mal note, fort bien note, generateur 16 caracteres')
  }

  // --- 27. CYBER / cout KDF et alerte de fuite ------------------------------
  {
    const { assessKdf } = await charge('src/services/cyber/kdfCostAnalyzer.ts')
    const { checkBreached } = await charge('src/services/cyber/breachChecker.ts')
    let defauts = 0
    const details = []
    const argon = assessKdf({ algorithm: 'argon2id', memoryKib: 65536, timeCost: 3, parallelism: 1 })
    if (!argon || argon.hashesPerSecondAttacker <= 0 || !argon.recommendation) { defauts += 1; details.push('argon2id mal evalue') }
    const fuite = checkBreached('password')
    if (!fuite?.isBreached) { defauts += 1; details.push('mot de passe top-fuite non signale') }
    const sain = checkBreached('K7!xqR2$lO9#mB4zW1@')
    if (sain?.isBreached) { defauts += 1; details.push('mot de passe aleatoire signale comme fuit') }
    ajoute('cyber', 'cout KDF + alerte fuite', defauts, details.join(' ; ') || 'argon2id evalue, fuite reelle detectee, aleatoire sain')
  }

  // --- 28. VOIX / visemes et synthese SSML --------------------------------
  {
    const { textToVisemesRuleBased } = await charge('src/services/voiceFrPhonemizer.ts')
    let defauts = 0
    const details = []
    const visemes = textToVisemesRuleBased('bonjour', 24)
    if (!visemes || visemes.length === 0) { defauts += 1; details.push('aucun viseme produit') }
    else {
      const tps = visemes.filter((v) => Number.isFinite(v.startMs) && Number.isFinite(v.endMs) && v.endMs > v.startMs).length
      if (tps !== visemes.length) { defauts += 1; details.push('trame temporelle invalide') }
    }
    ajoute('voix', 'visemes lipsync', defauts, details.join(' ; ') || `${visemes?.length ?? 0} visemes avec trame temporelle`)
  }

  // --- 29. DESSIN / mise en page vers SVG -----------------------------------
  {
    const { layoutFlowchart, layoutToSvg } = await charge('src/services/drawingAutoLayout.ts')
    let defauts = 0
    const details = []
    const noeuds = [{ id: 'a', label: 'A' }, { id: 'b', label: 'B' }, { id: 'c', label: 'C' }]
    const aretes = [{ from: 'a', to: 'b' }, { from: 'b', to: 'c' }]
    const layout = layoutFlowchart(noeuds, aretes)
    if (!layout || layout.nodes.length !== 3) { defauts += 1; details.push('layout incomplet') }
    else {
      const pos = layout.nodes.find((n) => n.id === 'b')
      if (!pos || typeof pos.x !== 'number' || !Number.isFinite(pos.x)) { defauts += 1; details.push('coordonnees manquantes') }
    }
    const svg = layoutToSvg(layout)
    if (!svg || !svg.viewBox || svg.viewBox.w <= 0) { defauts += 1; details.push('viewBox SVG invalide') }
    if (!svg || svg.elements.length === 0) { defauts += 1; details.push('aucun element SVG') }
    ajoute('dessin', 'layout vers SVG', defauts, details.join(' ; ') || '3 noeuds disposes, viewBox + elements SVG produits')
  }

  // --- 30. CONVERSATION / normalisation des verdicts CITE -------------------
  {
    const { normalizeVerification } = await charge('src/services/conversationVerification.ts')
    let defauts = 0
    const details = []
    const nonFaite = normalizeVerification({ verified: false, reason: 'pas fait' })
    if (!nonFaite || nonFaite.verified !== false) { defauts += 1; details.push('verif absente marquee verifiee') }
    const avecCite = normalizeVerification({ score: 85, confidence: 90, verdict: 'ready', citations: ['doc.pdf p.3'], summary: 'verifie' })
    if (!avecCite || !avecCite.verified) { defauts += 1; details.push('jugement complet rejete') }
    if (!avecCite?.summary || avecCite.summary === 'Verification terminee.') { defauts += 1; details.push('resume perdu') }
    ajoute('conversation', 'verification + citations', defauts, details.join(' ; ') || 'absence vs presence de citation distinguees')
  }

  // --- 31. COWORK / garde-fou des actions agent -----------------------------
  {
    const { validateAction } = await charge('src/services/coworkSafety.ts')
    let defauts = 0
    const details = []
    const ws = '/workspace/projet'
    const danger = validateAction({ kind: 'shell', command: 'rm', args: ['-rf', '/etc/toto'] }, 'desktop', ws, {})
    if (danger.decision !== 'confirm') { defauts += 1; details.push(`rm -rf ${danger.decision}`) }
    const horsWs = validateAction({ kind: 'delete_file', path: '/tmp/fichier.txt' }, 'desktop', ws, {})
    if (horsWs.decision !== 'confirm') { defauts += 1; details.push(`delete hors ws ${horsWs.decision}`) }
    const dansWs = validateAction({ kind: 'read_file', path: `${ws}/main.ts` }, 'desktop', ws, {})
    if (dansWs.decision !== 'allow') { defauts += 1; details.push('lecture workspace refusee a tort') }
    const ctrl = validateAction({ kind: 'write_file', path: `${ws}/../secrets`, content: 'x' }, 'desktop', ws, {})
    if (ctrl.decision !== 'confirm') { defauts += 1; details.push(`chemin hors workspace ${ctrl.decision}`) }
    ajoute('cowork', 'garde-fou de valideAction', defauts, details.join(' ; ') || 'destructif/hors-espace confirme, lecture ws permettent')
  }

  // --- 32. IMAGE / extraction du brief --------------------------------------
  {
    const { parseBrief, buildPromptContractBlock } = await charge('src/services/imagePromptBuilder.ts')
    let defauts = 0
    const details = []
    const b = parseBrief('un chat roux dans un jardin apres la pluie, sans personne, ni grisaille')
    if (!b || !b.subject || !b.subject.includes('chat roux')) { defauts += 1; details.push('sujet non extrait') }
    if (!b || b.negativeHints.length === 0 || !b.negativeHints.some((n) => n.includes('personne'))) { defauts += 1; details.push('interdits non extraits') }
    const bloc = buildPromptContractBlock(b)
    if (!bloc || !bloc.includes('IMAGE PROMPT BUILDER CONTRACT') || !bloc.includes('chat roux')) { defauts += 1; details.push('contrat de prompt incomplet') }
    ajoute('image', 'brief vers contrat', defauts, details.join(' ; ') || 'sujet + interdits isoles, contrat prompt genere')
  }

  // --- 33. CODE / regles statiques de securite ------------------------------
  {
    const { SECURITY_RULES } = await charge('src/services/codeStaticSecurityRules.ts')
    let defauts = 0
    const details = []
    const regleEval = SECURITY_RULES.find((r) => r.pattern.source.includes('eval'))
    if (!regleEval) { defauts += 1; details.push('regle eval absente') }
    else {
      const fichier = { path: 'src/app.ts', language: 'ts', content: 'const fn = eval(userInput)' }
      if (!regleEval.pattern.test(fichier.content) || !regleEval.appliesTo(fichier)) { defauts += 1; details.push('eval non signalment par la regle') }
      const propre = { path: 'src/app.ts', language: 'ts', content: 'const x = JSON.parse(text)' }
      if (regleEval.pattern.test(propre.content)) { defauts += 1; details.push('faux positif sur JSON.parse') }
    }
    ajoute('code', 'regles statiques de securite', defauts, details.join(' ; ') || 'eval bloque selon la regle, JSON.parse exonere')
  }

  // --- 34. CYBER / inspection JWT -------------------------------------------
  {
    const { inspectJwt, summariseJwt } = await charge('src/services/cyber/jwtInspector.ts')
    let defauts = 0
    const details = []
    const token = 'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJyb290In0.c2ln'
    const ins = inspectJwt(token, new Date('2026-01-01'))
    if (!ins || !ins.header || ins.header.alg !== 'none') { defauts += 1; details.push('entete JWT non decode') }
    if (!ins || ins.issues.length === 0) { defauts += 1; details.push('aucun probleme signale') }
    else if (!ins.issues.some((i) => i.severity === 'block')) { defauts += 1; details.push('alg=none non repere') }
    const sum = summariseJwt(ins)
    if (!sum || !sum.includes('none')) { defauts += 1; details.push('resume JWT sans mention alg') }
    ajoute('cyber', 'inspection JWT', defauts, details.join(' ; ') || 'entete none decode + gravite block + resume')
  }

  // --- 35. CYBER / aller-retour binaire -------------------------------------
  {
    const { decodeBinary } = await charge('src/services/cyber/classicalCipherAnalysis.ts')
    const { toBinary } = await charge('src/services/cyber/cryptoService.ts')
    let defauts = 0
    const details = []
    const phrase = 'Aurora se connecte via le tunnel'
    const bin = toBinary(phrase)
    if (!bin || !bin.includes('0') || !bin.includes('1')) { defauts += 1; details.push('encodage binaire vide') }
    if (decodeBinary(bin) !== phrase) { defauts += 1; details.push('aller-retour binaire casse') }
    const faussaire = bin.slice(0, -2) + '1 0'
    if (decodeBinary(faussaire) === phrase && phrase !== decodeBinary(faussaire)) { defauts += 1; details.push('corruption non detectee') }
    ajoute('cyber', 'aller-retour binaire', defauts, details.join(' ; ') || `${phrase.length} caracteres convertis puis restitues`)
  }

  // --- 36. CYBER / audit des hachages ---------------------------------------
  {
    const { auditHash } = await charge('src/services/cyber/hashParameterParser.ts')
    let defauts = 0
    const details = []
    const argon = '$argon2id$v=19$m=65536,t=3,p=1$c29tZXNhbHQ$mZ9LhW1LQV0wQ3pXbDlxdA'
    const bcrypt = '$2b$12$LQ5wM9gO3uN1UH8S5R8TLOxLsY7jU9pVjYrY8mXzZ6XmWqZvL9rCq'
    try {
      const a = auditHash(argon)
      if (!a || a.verdict !== 'recommended') { defauts += 1; details.push('argon2id non recommande a tort') }
      const b = auditHash(bcrypt)
      if (!b || b.verdict !== 'acceptable') { defauts += 1; details.push('bcrypt cost 12 non acceptable') }
    } catch (e) { defauts += 1; details.push(`auditHash : ${String(e.message).slice(0, 60)}`) }
    ajoute('cyber', 'audit des hachages', defauts, details.join(' ; ') || 'argon2id recommende, bcrypt 12 acceptable')
  }

  // --- 37. CYBER / validation politique algorithmique -----------------------
  {
    const { auditJwtVerificationPolicy } = await charge('src/services/cyber/exploitPatchVerifier.ts')
    let defauts = 0
    const details = []
    const sain = auditJwtVerificationPolicy('RS256', ['RS256'], true)
    if (!sain || sain.isAccepted !== true) { defauts += 1; details.push('RS256 accepte refuse a tort') }
    const conf = auditJwtVerificationPolicy('HS256', ['RS256', 'HS256'], true)
    if (!conf || conf.isVulnerableAlgorithmConfusion !== true) { defauts += 1; details.push('confusion RS/HS non detectee') }
    const none = auditJwtVerificationPolicy('none', ['RS256'], false)
    if (!none || none.isVulnerableAlgorithmNone !== true) { defauts += 1; details.push('alg=none non bloque') }
    ajoute('cyber', 'politique algorithmique JWT', defauts, details.join(' ; ') || 'RS256 sain, confusion and none rejetes')
  }

  // --- 38. CYBER / posture quantique ----------------------------------------
  {
    const { auditQuantumReadiness } = await charge('src/services/cyber/postQuantumCryptoAudit.ts')
    let defauts = 0
    const details = []
    const r = auditQuantumReadiness(['RSA-2048', 'Kyber-512'])
    if (!r || !r.status || r.status === 'QUANTUM_READY') { defauts += 1; details.push('RSA-2048 seul juge prepare') }
    if (r && r.evaluatedSuites) {
      const rsa = r.evaluatedSuites.find((s) => s.algorithm === 'RSA-2048')
      if (!rsa || rsa.isQuantumVulnerable !== true) { defauts += 1; details.push('RSA-2048 non marqué vulnerable') }
    }
    ajoute('cyber', 'posture quantique', defauts, details.join(' ; ') || 'RSA vulnerable, verdict non-QM')
  }

  // --- 39. IMAGE / classification directionnelle (voix inverse) -------------
  {
    const { identifyHash } = await charge('src/services/cyber/hashService.ts')
    let defauts = 0
    const details = []
    const md5 = identifyHash('e10adc3949ba59abbe56e057f20f883e')
    if (!md5 || !md5.includes('MD5')) { defauts += 1; details.push('empreinte MD5 non reconnue') }
    const sha = identifyHash('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')
    if (!sha || !sha.some((s) => s.startsWith('SHA-256'))) { defauts += 1; details.push('SHA-256 non reconnue') }
    ajoute('cyber', 'identification d empreintes', defauts, details.join(' ; ') || 'MD5 32g, SHA-256 64g identifiees')
  }

  return out
}
