"""Empaquette un projet web genere dans un VRAI APK Android signe.

Pourquoi ce module existe, et pourquoi il ne touche pas a `simulation_android`:
celui-ci construit une sonde WS12 — une coquille WebView qui pointe le
dev-server pour TESTER le rendu sur telephone. Ce qu il faut ici est different:
un APK installable qui EMBARQUE le projet livre et fonctionne hors ligne, sans
serveur ni reseau.

La chaine est celle qui marche deja sur cette machine (aapt2 -> d8 -> zipalign
-> apksigner, SDK prive sous ~/.local/share/auroraia/tools/android-sdk). La
seule difference: `aapt2 link -A assets/` embarque le site, et l activite charge
`file:///android_asset/www/index.html`.

Limite assumee et VERIFIEE, pas devinee: un projet React Native ne passe pas par
ici. Le construire demande la chaine Gradle RN et ses node_modules, qui ne sont
pas installes. Un projet web (statique, ou SPA deja construite) passe.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from simulation_tooling import TOOL_ROOT, android_sdk_root  # noqa: E402

PACKAGE = "ia.aurora.codeapp"

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{package}">
  <uses-sdk android:minSdkVersion="24" android:targetSdkVersion="34" />
  <application android:label="{label}" android:usesCleartextTraffic="true">
    <activity android:name=".MainActivity" android:exported="true">
      <intent-filter>
        <action android:name="android.intent.action.MAIN" />
        <category android:name="android.intent.category.LAUNCHER" />
      </intent-filter>
    </activity>
  </application>
</manifest>
"""

ACTIVITY = """package ia.aurora.codeapp;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
  @Override
  protected void onCreate(Bundle state) {
    super.onCreate(state);
    WebView view = new WebView(this);
    WebSettings settings = view.getSettings();
    settings.setJavaScriptEnabled(true);
    settings.setDomStorageEnabled(true);
    settings.setAllowFileAccess(true);
    view.setWebViewClient(new WebViewClient());
    view.loadUrl("file:///android_asset/www/index.html");
    setContentView(view);
  }
}
"""

WEB_SUFFIXES = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".svg", ".png",
                ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".ico", ".woff", ".woff2"}


def _run(cmd, cwd, env, timeout=180):
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True,
                          text=True, timeout=timeout, check=False)
    return proc.returncode == 0, f"$ {' '.join(str(c) for c in cmd)}\n{proc.stdout}{proc.stderr}\n"


def _android_env(sdk: Path) -> dict:
    import os
    env = os.environ.copy()
    jdks = sorted(TOOL_ROOT.glob("jdk-*/bin/javac"), reverse=True)
    java_home = jdks[0].parents[1] if jdks else None
    parts = [str(sdk / "platform-tools")]
    if java_home:
        parts.append(str(java_home / "bin"))
        env["JAVA_HOME"] = str(java_home)
    env["ANDROID_HOME"] = env["ANDROID_SDK_ROOT"] = str(sdk)
    env["PATH"] = os.pathsep.join([*parts, env.get("PATH", "")])
    return env


def package_web_apk(project_dir: Path, out_dir: Path, label: str = "Aurora App") -> tuple[Path | None, str]:
    """Construit l APK. Retourne (chemin, journal). `None` = raison dans le journal."""
    sdk = android_sdk_root()
    if not sdk:
        return None, "Android SDK introuvable (attendu sous ~/.local/share/auroraia/tools/android-sdk)"

    # Le builder tourne avec cwd=out_dir: tout chemin relatif casserait aapt2.
    project_dir, out_dir = Path(project_dir).resolve(), Path(out_dir).resolve()
    entry = project_dir / "index.html"
    if not entry.is_file():
        return None, "aucun index.html: seul un projet web deja construit peut etre empaquete"

    env = _android_env(sdk)
    platforms = sorted(sdk.glob("platforms/android-*/android.jar"),
                       key=lambda item: int(item.parent.name.split("-")[-1]))
    builds = sorted((item for item in (sdk / "build-tools").glob("*") if item.is_dir()),
                    key=lambda item: tuple(int(part) for part in item.name.split(".") if part.isdigit()))
    javac = shutil.which("javac", path=env.get("PATH"))
    keytool = shutil.which("keytool", path=env.get("PATH"))
    if not platforms or not builds or not javac or not keytool:
        return None, "plateforme Android, build-tools ou JDK incomplet"

    android_jar, build = platforms[-1], builds[-1]
    out_dir.mkdir(parents=True, exist_ok=True)
    src = out_dir / "src" / "ia" / "aurora" / "codeapp"
    src.mkdir(parents=True, exist_ok=True)
    (src / "MainActivity.java").write_text(ACTIVITY, encoding="utf-8")
    (out_dir / "AndroidManifest.xml").write_text(
        MANIFEST.format(package=PACKAGE, label=label.replace('"', "'")[:40]), encoding="utf-8")

    # Le site entre dans assets/www: l APK devient autonome, sans reseau.
    assets = out_dir / "assets" / "www"
    if assets.exists():
        shutil.rmtree(assets)
    assets.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in sorted(project_dir.rglob("*")):
        if not item.is_file() or item.suffix.lower() not in WEB_SUFFIXES:
            continue
        dest = assets / item.relative_to(project_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest)
        copied += 1
    if copied == 0:
        return None, "aucun fichier web a embarquer"

    classes, dex = out_dir / "classes", out_dir / "dex"
    classes.mkdir(exist_ok=True)
    dex.mkdir(exist_ok=True)
    unsigned, aligned = out_dir / "unsigned.apk", out_dir / "aligned.apk"
    apk = out_dir / "aurora-app.apk"
    keystore = out_dir / "aurora.keystore"

    log = [f"{copied} fichier(s) web embarque(s) dans assets/www\n"]
    steps = [
        [str(build / "aapt2"), "link", "-o", str(unsigned), "--manifest",
         str(out_dir / "AndroidManifest.xml"), "-I", str(android_jar),
         "-A", str(out_dir / "assets"), "--java", str(out_dir / "gen")],
        [javac, "-source", "17", "-target", "17", "-classpath", str(android_jar),
         "-d", str(classes), str(src / "MainActivity.java")],
    ]
    for cmd in steps:
        ok, out = _run(cmd, out_dir, env)
        log.append(out)
        if not ok:
            return None, "".join(log)

    class_files = [str(path) for path in classes.rglob("*.class")]
    ok, out = _run([str(build / "d8"), "--release", "--lib", str(android_jar),
                    "--output", str(dex), *class_files], out_dir, env)
    log.append(out)
    if not ok:
        return None, "".join(log)

    ok, out = _run([shutil.which("zip", path=env.get("PATH")) or "zip", "-j", str(unsigned),
                    str(dex / "classes.dex")], out_dir, env)
    log.append(out)
    if not ok:
        return None, "".join(log)

    if not keystore.is_file():
        ok, out = _run([keytool, "-genkeypair", "-keystore", str(keystore),
                        "-storepass", "android", "-keypass", "android", "-alias", "aurora",
                        "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
                        "-dname", "CN=Aurora Code, O=AuroraIA, C=FR"], out_dir, env)
        log.append(out)
        if not ok:
            return None, "".join(log)

    ok, out = _run([str(build / "zipalign"), "-f", "4", str(unsigned), str(aligned)], out_dir, env)
    log.append(out)
    if not ok:
        return None, "".join(log)

    ok, out = _run([str(build / "apksigner"), "sign", "--ks", str(keystore),
                    "--ks-pass", "pass:android", "--key-pass", "pass:android",
                    "--out", str(apk), str(aligned)], out_dir, env)
    log.append(out)
    if not ok:
        return None, "".join(log)

    ok, out = _run([str(build / "apksigner"), "verify", "--print-certs", str(apk)], out_dir, env)
    log.append(out)
    return (apk if ok else None), "".join(log)


if __name__ == "__main__":
    project, output = Path(sys.argv[1]), Path(sys.argv[2])
    name = sys.argv[3] if len(sys.argv) > 3 else "Aurora App"
    built, journal = package_web_apk(project, output, name)
    Path(output / "apk-build.log").write_text(journal, encoding="utf-8")
    print(built or "ECHEC")
    if not built:
        print(journal[-1500:])
