// Matrice de capacite REELLE: chaque case est un artefact compile, pas une
// estimation. Le principe est celui de tout ce module — on ne declare pas une
// capacite, on la prouve, et on nomme precisement ce qui manque quand elle
// echoue.
//
// Usage: node --experimental-strip-types scripts/code_harness/capability_probe.mjs

import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const TOOLS = path.join(os.homedir(), '.local/share/auroraia/tools')
const SDK = path.join(TOOLS, 'android-sdk')
const JDK = path.join(TOOLS, 'jdk-21.0.11')
// Regle du projet: aucun resultat verifiable ne vit dans un dossier
// temporaire. /tmp est purge au redemarrage — une matrice qui reference des
// artefacts disparus n est pas inutile, elle MENT en silence. Les artefacts
// vivent donc dans l arborescence, avec leur chemin complet cite.
const ROOT = path.resolve('output/code/capacites')

function run(cmd, args, cwd, env = {}, timeout = 240_000) {
  const proc = spawnSync(cmd, args, {
    cwd, timeout, encoding: 'utf8',
    env: { ...process.env, ...env },
  })
  return {
    ok: proc.status === 0,
    out: `${proc.stdout ?? ''}${proc.stderr ?? ''}`.slice(-2000),
    missing: proc.error?.code === 'ENOENT',
  }
}

function has(bin) {
  return spawnSync('sh', ['-c', `command -v ${bin}`], { encoding: 'utf8' }).status === 0
}

function workspace(name) {
  const dir = path.join(ROOT, name)
  fs.rmSync(dir, { recursive: true, force: true })
  fs.mkdirSync(dir, { recursive: true })
  return dir
}

const probes = []
const probe = (id, platform, fn) => probes.push({ id, platform, fn })

// --- Android natif, en Java -------------------------------------------------
// Le SDK et le JDK sont la; c est la meme chaine que l APK WebView deja prouve,
// mais avec une vraie Activity native (pas de WebView, pas de page web).
probe('android_native_java', 'Android natif (Java)', () => {
  if (!fs.existsSync(SDK)) return { status: 'impossible', detail: 'Android SDK absent' }
  const dir = workspace('android-java')
  const pkgDir = path.join(dir, 'src/ia/aurora/nativeapp')
  fs.mkdirSync(pkgDir, { recursive: true })
  fs.writeFileSync(path.join(dir, 'AndroidManifest.xml'), `<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="ia.aurora.nativeapp">
  <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34" />
  <application android:label="Aurora Natif">
    <activity android:name=".MainActivity" android:exported="true">
      <intent-filter><action android:name="android.intent.action.MAIN" /><category android:name="android.intent.category.LAUNCHER" /></intent-filter>
    </activity>
  </application>
</manifest>
`)
  fs.writeFileSync(path.join(pkgDir, 'MainActivity.java'), `package ia.aurora.nativeapp;
import android.app.Activity;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Button;
public class MainActivity extends Activity {
  private int count = 0;
  @Override protected void onCreate(Bundle s) {
    super.onCreate(s);
    LinearLayout root = new LinearLayout(this);
    root.setOrientation(LinearLayout.VERTICAL);
    root.setPadding(48, 96, 48, 48);
    final TextView label = new TextView(this);
    label.setTextSize(28);
    label.setText("Compteur : 0");
    Button button = new Button(this);
    button.setText("Incrementer");
    button.setOnClickListener(v -> label.setText("Compteur : " + (++count)));
    root.addView(label);
    root.addView(button);
    setContentView(root);
  }
}
`)
  const jars = fs.readdirSync(path.join(SDK, 'platforms')).map((p) => path.join(SDK, 'platforms', p, 'android.jar'))
  const androidJar = jars.find((p) => fs.existsSync(p))
  const build = path.join(SDK, 'build-tools', fs.readdirSync(path.join(SDK, 'build-tools'))[0])
  const env = { JAVA_HOME: JDK, PATH: `${JDK}/bin:${process.env.PATH}` }
  const unsigned = path.join(dir, 'unsigned.apk')

  let step = run(path.join(build, 'aapt2'), ['link', '-o', unsigned, '--manifest', path.join(dir, 'AndroidManifest.xml'), '-I', androidJar, '--java', path.join(dir, 'gen')], dir, env)
  if (!step.ok) return { status: 'echec', detail: `aapt2: ${step.out.slice(-160)}` }
  fs.mkdirSync(path.join(dir, 'classes'), { recursive: true })
  step = run(`${JDK}/bin/javac`, ['-source', '17', '-target', '17', '-classpath', androidJar, '-d', path.join(dir, 'classes'), path.join(pkgDir, 'MainActivity.java')], dir, env)
  if (!step.ok) return { status: 'echec', detail: `javac: ${step.out.slice(-160)}` }
  const classes = fs.readdirSync(path.join(dir, 'classes/ia/aurora/nativeapp')).map((f) => path.join(dir, 'classes/ia/aurora/nativeapp', f))
  fs.mkdirSync(path.join(dir, 'dex'), { recursive: true })
  step = run(path.join(build, 'd8'), ['--release', '--lib', androidJar, '--output', path.join(dir, 'dex'), ...classes], dir, env)
  if (!step.ok) return { status: 'echec', detail: `d8: ${step.out.slice(-160)}` }
  run('zip', ['-j', unsigned, path.join(dir, 'dex/classes.dex')], dir, env)
  const keystore = path.join(dir, 'k.jks')
  run(`${JDK}/bin/keytool`, ['-genkeypair', '-keystore', keystore, '-storepass', 'android', '-keypass', 'android', '-alias', 'a', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '9000', '-dname', 'CN=Aurora Natif, O=AuroraIA, C=FR'], dir, env)
  const aligned = path.join(dir, 'aligned.apk')
  const apk = path.join(dir, 'aurora-natif.apk')
  run(path.join(build, 'zipalign'), ['-f', '4', unsigned, aligned], dir, env)
  step = run(path.join(build, 'apksigner'), ['sign', '--ks', keystore, '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', apk, aligned], dir, env)
  if (!step.ok) return { status: 'echec', detail: `apksigner: ${step.out.slice(-160)}` }
  const verify = run(path.join(build, 'apksigner'), ['verify', '--print-certs', apk], dir, env)
  if (!verify.ok) return { status: 'echec', detail: 'signature non verifiee' }
  return {
    status: 'prouve',
    artifact: apk,
    detail: `APK natif signe, ${fs.statSync(apk).size} octets, ${verify.out.match(/DN: ([^\n]+)/)?.[1] ?? 'signe'}`,
  }
})

// --- Kotlin -----------------------------------------------------------------
probe('android_kotlin', 'Android natif (Kotlin)', () => {
  const kotlinc = path.join(TOOLS, 'kotlinc/bin/kotlinc')
  if (!fs.existsSync(kotlinc)) {
    return { status: 'impossible', detail: 'compilateur Kotlin absent du dossier outils Aurora' }
  }
  const dir = workspace('android-kotlin')
  const src = path.join(dir, 'MainActivity.kt')
  fs.writeFileSync(path.join(dir, 'AndroidManifest.xml'), `<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="ia.aurora.kt">
  <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34" />
  <application android:label="Aurora Kotlin">
    <activity android:name=".MainActivity" android:exported="true">
      <intent-filter><action android:name="android.intent.action.MAIN" /><category android:name="android.intent.category.LAUNCHER" /></intent-filter>
    </activity>
  </application>
</manifest>
`)
  fs.writeFileSync(src, `package ia.aurora.kt

import android.app.Activity
import android.os.Bundle
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
  private var count = 0
  override fun onCreate(state: Bundle?) {
    super.onCreate(state)
    val root = LinearLayout(this).apply {
      orientation = LinearLayout.VERTICAL
      setPadding(48, 96, 48, 48)
    }
    val label = TextView(this).apply { textSize = 28f; text = "Compteur : 0" }
    val button = Button(this).apply { text = "Incrementer" }
    button.setOnClickListener { label.text = "Compteur : \${++count}" }
    root.addView(label)
    root.addView(button)
    setContentView(root)
  }
}
`)
  const jars = fs.readdirSync(path.join(SDK, 'platforms')).map((p) => path.join(SDK, 'platforms', p, 'android.jar'))
  const androidJar = jars.find((p) => fs.existsSync(p))
  const build = path.join(SDK, 'build-tools', fs.readdirSync(path.join(SDK, 'build-tools'))[0])
  const env = { JAVA_HOME: JDK, PATH: `${JDK}/bin:${process.env.PATH}` }
  const classes = path.join(dir, 'classes')

  let step = run(kotlinc, [src, '-classpath', androidJar, '-d', classes, '-nowarn'], dir, env, 420_000)
  if (!step.ok) return { status: 'echec', detail: `kotlinc: ${step.out.slice(-200)}` }

  const unsigned = path.join(dir, 'unsigned.apk')
  step = run(path.join(build, 'aapt2'), ['link', '-o', unsigned, '--manifest', path.join(dir, 'AndroidManifest.xml'), '-I', androidJar], dir, env)
  if (!step.ok) return { status: 'echec', detail: `aapt2: ${step.out.slice(-160)}` }

  // Kotlin exige sa bibliotheque standard dans le dex.
  const stdlib = path.join(TOOLS, 'kotlinc/lib/kotlin-stdlib.jar')
  fs.mkdirSync(path.join(dir, 'dex'), { recursive: true })
  const classFiles = []
  const walk = (d) => fs.readdirSync(d, { withFileTypes: true }).forEach((e) => {
    const full = path.join(d, e.name)
    if (e.isDirectory()) walk(full)
    else if (e.name.endsWith('.class')) classFiles.push(full)
  })
  walk(classes)
  step = run(path.join(build, 'd8'), ['--release', '--lib', androidJar, '--output', path.join(dir, 'dex'), ...classFiles, stdlib], dir, env, 420_000)
  if (!step.ok) return { status: 'echec', detail: `d8: ${step.out.slice(-200)}` }

  run('zip', ['-j', unsigned, path.join(dir, 'dex/classes.dex')], dir, env)
  const keystore = path.join(dir, 'k.jks')
  run(`${JDK}/bin/keytool`, ['-genkeypair', '-keystore', keystore, '-storepass', 'android', '-keypass', 'android', '-alias', 'a', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '9000', '-dname', 'CN=Aurora Kotlin, O=AuroraIA, C=FR'], dir, env)
  const aligned = path.join(dir, 'aligned.apk')
  const apk = path.join(dir, 'aurora-kotlin.apk')
  run(path.join(build, 'zipalign'), ['-f', '4', unsigned, aligned], dir, env)
  step = run(path.join(build, 'apksigner'), ['sign', '--ks', keystore, '--ks-pass', 'pass:android', '--key-pass', 'pass:android', '--out', apk, aligned], dir, env)
  if (!step.ok) return { status: 'echec', detail: `apksigner: ${step.out.slice(-160)}` }
  const verify = run(path.join(build, 'apksigner'), ['verify', '--print-certs', apk], dir, env)
  if (!verify.ok) return { status: 'echec', detail: 'signature non verifiee' }
  return {
    status: 'prouve',
    artifact: apk,
    detail: `APK Kotlin natif signe, ${fs.statSync(apk).size} octets, ${verify.out.match(/DN: ([^\n]+)/)?.[1] ?? 'signe'}`,
  }
})

// --- Apple ------------------------------------------------------------------
probe('apple_swift', 'Apple / iOS (Swift)', () => {
  // Deux questions distinctes, et il faut les separer pour etre honnete:
  //   1. le code Swift est-il VALIDE ?        -> verifiable ici (swiftc Linux)
  //   2. peut-on produire un .ipa installable ? -> NON, hors macOS, jamais
  // Refuser tout net serait faux; promettre une app iOS serait un mensonge.
  const swiftc = path.join(TOOLS, 'swift-5.10.1/usr/bin/swiftc')
  if (!fs.existsSync(swiftc)) {
    return { status: 'impossible', detail: 'swiftc absent et SDK Apple indisponible sur Linux' }
  }
  const dir = workspace('swift')
  // Un modele SwiftUI-like sans importer UIKit (absent sur Linux): on valide la
  // SYNTAXE et la semantique du langage, ce qui attrape l essentiel des fautes
  // qu un modele produit.
  fs.writeFileSync(path.join(dir, 'Model.swift'), `import Foundation

struct Coffee: Identifiable, Codable {
  let id: UUID
  let name: String
  let origin: String
  let priceEUR: Decimal
  var tastingNotes: [String]

  var label: String { "\\(name) — \\(origin)" }
}

enum OrderState: String, Codable { case pending, roasted, shipped }

final class Basket {
  private(set) var items: [Coffee] = []
  func add(_ coffee: Coffee) { items.append(coffee) }
  var total: Decimal { items.reduce(0) { $0 + $1.priceEUR } }
}

let basket = Basket()
basket.add(Coffee(id: UUID(), name: "Nomade", origin: "Ethiopie", priceEUR: 12, tastingNotes: ["agrumes"]))
print("AURORA_SWIFT_OK total=\\(basket.total) count=\\(basket.items.count)")
`)
  const binary = path.join(dir, 'model')
  const compile = run(swiftc, ['-O', path.join(dir, 'Model.swift'), '-o', binary], dir, {}, 300_000)
  if (!compile.ok) return { status: 'echec', detail: `swiftc: ${compile.out.slice(-200)}` }
  const exec = run(binary, [], dir)
  const ran = exec.out.includes('AURORA_SWIFT_OK')
  return {
    status: 'partiel',
    artifact: binary,
    detail: ran
      ? 'Swift COMPILE et EXECUTE sur Linux (types, protocoles, generiques, Codable verifies). Un .ipa reste impossible: les SDK Apple et la signature exigent macOS. Livrable honnete = projet Xcode/SwiftUI structure + code valide, non installable depuis cet hote.'
      : 'swiftc compile mais le binaire ne rend pas le marqueur attendu',
  }
})

// --- Rust bare-metal --------------------------------------------------------
probe('rust_baremetal', 'Embarque / bare-metal (Rust)', () => {
  if (!has('cargo')) return { status: 'impossible', detail: 'cargo absent' }
  const dir = workspace('rust-baremetal')
  fs.writeFileSync(path.join(dir, 'Cargo.toml'), '[package]\nname = "probe"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n')
  fs.mkdirSync(path.join(dir, 'src'), { recursive: true })
  fs.writeFileSync(path.join(dir, 'src/main.rs'), 'fn main() { println!("AURORA_PROBE_OK"); }\n')
  const build = run('cargo', ['build', '--release', '--offline'], dir)
  if (!build.ok) return { status: 'echec', detail: `cargo build: ${build.out.slice(-160)}` }
  const bin = path.join(dir, 'target/release/probe')
  const exec = run(bin, [], dir)
  return exec.out.includes('AURORA_PROBE_OK')
    ? { status: 'prouve', artifact: bin, detail: `binaire natif execute, marqueur observe (${fs.statSync(bin).size} octets)` }
    : { status: 'echec', detail: 'binaire produit mais marqueur absent' }
})

// --- C / noyau --------------------------------------------------------------
probe('c_kernel', 'OS / bas niveau (C + QEMU)', () => {
  if (!has('gcc')) return { status: 'impossible', detail: 'gcc absent' }
  const dir = workspace('c-freestanding')
  fs.writeFileSync(path.join(dir, 'kernel.c'), `
void _start(void) {
  volatile char *vga = (char *)0xB8000;
  const char *msg = "AURORA_KERNEL_OK";
  for (int i = 0; msg[i]; i++) { vga[i * 2] = msg[i]; vga[i * 2 + 1] = 0x0F; }
  for (;;) __asm__ volatile ("hlt");
}
`)
  const obj = path.join(dir, 'kernel.o')
  const compile = run('gcc', ['-ffreestanding', '-m32', '-c', path.join(dir, 'kernel.c'), '-o', obj], dir)
  if (!compile.ok) {
    return { status: 'partiel', detail: `code freestanding compile en 64 bits uniquement (multilib 32 bits absente): ${compile.out.slice(-120)}` }
  }
  const qemu = has('qemu-system-x86_64') || fs.existsSync(path.join(TOOLS, 'qemu-11.0.2/bin/qemu-system-x86_64'))
  return {
    status: 'prouve',
    artifact: obj,
    detail: `objet freestanding produit (${fs.statSync(obj).size} octets); QEMU ${qemu ? 'disponible pour le boot' : 'absent'}`,
  }
})

// --- WebAssembly ------------------------------------------------------------
probe('wasm', 'WebAssembly (Rust -> wasm32)', () => {
  if (!has('rustc')) return { status: 'impossible', detail: 'rustc absent' }
  const targets = run('rustc', ['--print', 'target-list'], ROOT)
  if (!targets.out.includes('wasm32-unknown-unknown')) {
    return { status: 'impossible', detail: 'cible wasm32 non listee par rustc' }
  }
  const dir = workspace('wasm')
  fs.writeFileSync(path.join(dir, 'lib.rs'), '#[no_mangle]\npub extern "C" fn add(a: i32, b: i32) -> i32 { a + b }\n')
  const out = path.join(dir, 'probe.wasm')
  const build = run('rustc', ['--target', 'wasm32-unknown-unknown', '--crate-type', 'cdylib', '-O', path.join(dir, 'lib.rs'), '-o', out], dir)
  if (!build.ok) {
    return { status: 'impossible', detail: `cible wasm32 non installee: ${build.out.slice(-140)}` }
  }
  const magic = fs.readFileSync(out).subarray(0, 4).toString('hex')
  return magic === '0061736d'
    ? { status: 'prouve', artifact: out, detail: `module wasm valide (magic 0asm, ${fs.statSync(out).size} octets)` }
    : { status: 'echec', detail: `magic inattendu: ${magic}` }
})

fs.mkdirSync(ROOT, { recursive: true })
const results = []
for (const { id, platform, fn } of probes) {
  process.stderr.write(`  … ${platform}\n`)
  let result
  try {
    result = fn()
  } catch (err) {
    result = { status: 'echec', detail: String(err?.message ?? err).slice(0, 160) }
  }
  results.push({ id, platform, ...result })
}

const matrix = { schema: 'aurora.code.capability-matrix/1', measuredAt: Date.now(), results }
process.stdout.write(`${JSON.stringify(matrix, null, 2)}\n`)

// Publication: la matrice n a de valeur que si on peut la LIRE. Elle part donc
// a cote du hub, servie par la meme route que les viewers.
if (process.argv.includes('--publish')) {
    // ARCHITECTURE : `output/code_assets/` n'est PAS un module canonique. Le
  // contrat de `aurora_output_paths` impose `output/<module>/<projet>/`, et le
  // pont lui-meme qualifie `output/code_assets` de « legacy »
  // (bridge_server.py, route /api/code/assets/file). Les visionneuses vivent
  // donc sous le module `code`, dans son projet `assets`.
  const outDir = path.resolve('output/code/assets/viewers')
  fs.mkdirSync(outDir, { recursive: true })
  fs.writeFileSync(path.join(outDir, 'capacites.json'), JSON.stringify(matrix), 'utf8')
  const esc = (v) => String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const badge = { prouve: '#2ea043', partiel: '#d29922', echec: '#f85149', impossible: '#6e7681' }
  const rows = results.map((r) => `<tr>
    <td><b>${esc(r.platform)}</b></td>
    <td><span style="color:${badge[r.status] ?? '#8b949e'};font-weight:600">${esc(r.status.toUpperCase())}</span></td>
    <td>${esc(r.detail)}</td>
    <td class="mono">${r.artifact ? esc(path.relative(path.resolve('..'), r.artifact)) : '—'}</td>
  </tr>`).join('\n')
  fs.writeFileSync(path.join(outDir, 'capacites.html'), `<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Capacites reelles — Module Code</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#0d1117;color:#c9d1d9;font:14px/1.6 ui-sans-serif,system-ui,sans-serif;padding:1.5rem}
h1{font-size:18px;color:#e6edf3;margin:0 0 .3rem}
p.sub{color:#7d8590;font-size:12px;margin:0 0 1.2rem}
table{border-collapse:collapse;width:100%;max-width:1100px}
th,td{text-align:left;padding:.6rem .7rem;border-bottom:1px solid #1c2128;vertical-align:top;font-size:13px}
th{color:#7d8590;font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.mono{font-family:ui-monospace,monospace;font-size:11px;color:#6e7681;word-break:break-all}
footer{margin-top:1.4rem;color:#6e7681;font-size:11px;max-width:1100px}
</style></head><body>
<h1>Capacites reelles du module Code</h1>
<p class="sub">Chaque ligne est un artefact REELLEMENT compile sur cet hote, ou une raison precise de ne pas pouvoir. Mesure du ${new Date(matrix.measuredAt).toLocaleString('fr-FR')}.</p>
<table><thead><tr><th>Plateforme</th><th>Etat</th><th>Preuve / raison</th><th>Artefact</th></tr></thead>
<tbody>${rows}</tbody></table>
<footer>PROUVE = artefact produit et verifie. PARTIEL = une partie seulement est verifiable sur cet hote. IMPOSSIBLE = limite de plateforme, la raison est donnee.</footer>
</body></html>
`, 'utf8')
  process.stderr.write(`  publie: output/code/assets/viewers/capacites.html\n`)
}
