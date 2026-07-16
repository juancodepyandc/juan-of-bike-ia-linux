#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

OUT="${1:-$ROOT/output/final_code_refonte_validation/heavy_final}"
mkdir -p "$OUT"
RESULTS="$OUT/steps.ndjson"
: > "$RESULTS"
STARTED_AT="$(date --iso-8601=seconds)"
OVERALL=0

record_result() {
  local id="$1" description="$2" severity="$3" status="$4" exit_code="$5" duration_ms="$6" log="$7"
  jq -cn \
    --arg id "$id" \
    --arg description "$description" \
    --arg severity "$severity" \
    --arg status "$status" \
    --argjson exitCode "$exit_code" \
    --argjson durationMs "$duration_ms" \
    --arg log "$log" \
    '{id:$id,description:$description,severity:$severity,status:$status,exitCode:$exitCode,durationMs:$durationMs,log:$log}' \
    >> "$RESULTS"
}

run_step() {
  local severity="$1" id="$2" description="$3"
  shift 3
  local log="$OUT/$id.log" started finished duration exit_code status
  printf '[final] %-28s %s\n' "$id" "$description"
  started="$(date +%s%3N)"
  "$@" > "$log" 2>&1
  exit_code=$?
  finished="$(date +%s%3N)"
  duration=$((finished - started))
  status="passed"
  if (( exit_code != 0 )); then
    status="failed"
    OVERALL=1
    tail -40 "$log"
  elif [[ "$severity" == "known-debt" ]]; then
    status="warning"
  fi
  record_result "$id" "$description" "$severity" "$status" "$exit_code" "$duration" "${log#$ROOT/}"
}

run_required() {
  run_step required "$@"
}

run_known_debt() {
  run_step known-debt "$@"
}

run_required bridge_health "Bridge et ComfyUI vivants" \
  bash -lc 'curl -fsS http://127.0.0.1:3001/api/comfyui/status | jq -e ".ok == true and .running == true"'
run_required vite_health "Front de preuve vivant" \
  bash -lc 'test "$(curl -sS -o /dev/null -w "%{http_code}" http://127.0.0.1:1431/scripts/code_harness/visual_shell.html)" = 200'
run_required git_diff_check "Diff sans erreur d espace" git diff --check
run_required npm_dependency_graph "Graphe npm coherent" npm ls --depth=0
run_required npm_security_audit "Audit npm sans vulnerabilite" npm audit --json
run_required tracked_secret_scan "Aucun secret sensible suivi" \
  bash -lc '! git ls-files | rg -i "(^|/)(\.env|id_rsa|.*\.(pem|p12|key))$"'
run_required forbidden_source_scan "Unsplash et artefacts Windows absents du Code de production" \
  bash -lc '! rg -n "source\.unsplash\.com|lancement\.bat|start\.bat" src python-services/aurora_code --glob "!**/__tests__/**"'
run_required python_ast_all "Syntaxe de tous les Python suivis" \
  .venv/bin/python -c 'import ast,pathlib,subprocess; paths=subprocess.check_output(["git","ls-files","*.py"],text=True).splitlines(); [ast.parse(pathlib.Path(p).read_text(encoding="utf-8"),filename=p) for p in paths]; print(f"parsed={len(paths)}")'
run_required app_venv_integrity "Aucun residu WS14 dans le venv applicatif" \
  bash -lc '! find .venv -name aurora_tooling_eval.json -print -quit | rg .'
run_known_debt pip_optional_dependencies "Extras image externes manquants, aucun ajout dans .venv" \
  bash -lc 'set +e; .venv/bin/pip check > "$1" 2>&1; rc=$?; set -e; if ((rc==0)); then cat "$1"; exit 0; fi; node -e '\''const fs=require("fs");const p=process.argv[1];const lines=fs.readFileSync(p,"utf8").trim().split(/\r?\n/).filter(Boolean);const ok=lines.length>0&&lines.every(l=>/^(realesrgan|basicsr) /.test(l));console.log(JSON.stringify({ok,lines},null,2));if(!ok)process.exit(1)'\'' "$1"' _ "$OUT/pip-check.raw.log"
run_known_debt rootless_host_restriction "Podman rootless bloque par la politique hote" \
  bash -lc 'printf "podman=%s\n" "$(command -v podman || echo absent)"; printf "newuidmap=%s\n" "$(command -v newuidmap || echo absent)"; printf "newgidmap=%s\n" "$(command -v newgidmap || echo absent)"; if unshare -Ur true 2>/dev/null; then echo "user_namespace=available"; else echo "user_namespace=restricted"; fi; test ! -x "$(command -v podman 2>/dev/null || echo /nonexistent)"'
run_required cargo_metadata "Metadata Cargo valide" cargo metadata --manifest-path src-tauri/Cargo.toml --no-deps --format-version 1
run_required module_structure "Unites Code strictement sous 400 lignes" \
  node --experimental-strip-types --test src/__tests__/codeModuleStructure.test.ts
run_required acceptance_critical "Preuves agentiques, extreme, sandbox, visuelles et simulation" \
  bash -lc 'node --experimental-strip-types --test src/__tests__/codeAgenticLargeProjectProof.test.ts src/__tests__/codeExtremeCompilerProof.test.ts src/__tests__/codeSandbox*.test.ts src/__tests__/codeVisual*.test.ts src/__tests__/codeSimulationLab.test.ts'
run_required code_test_suite "Suite complete du Module Code" \
  bash -lc 'node --experimental-strip-types --test "src/__tests__/code*.test.ts"'
run_required python_code_suite "Suite Python aurora_code" \
  .venv/bin/python -m unittest discover -s python-services/aurora_code -p 'test_*.py'
FULL_REPOSITORY_RAW="$OUT/full-repository-tests.raw.log"
set +e
npm test > "$FULL_REPOSITORY_RAW" 2>&1
FULL_REPOSITORY_EXIT=$?
run_known_debt full_repository_tests "Suite globale: uniquement dette live Cowork connue" \
  node scripts/code_harness/final_node_test_scope_check.mjs \
  "$FULL_REPOSITORY_RAW" "$OUT/full-repository-test-scope.json" "$FULL_REPOSITORY_EXIT"
run_required production_build "Build Vite de production" npm run build
run_required cargo_check "Compilation Rust/Tauri" cargo check --manifest-path src-tauri/Cargo.toml

TSC_RAW="$OUT/typescript.raw.log"
set +e
npx tsc --noEmit --pretty false > "$TSC_RAW" 2>&1
TSC_EXIT=$?
run_known_debt typescript_scope "Typecheck: uniquement dettes globales hors Code" \
  node scripts/code_harness/final_tsc_scope_check.mjs "$TSC_RAW" "$OUT/typescript-scope.json" "$TSC_EXIT"

run_required ws15_asset_export "WS15: export autonome et hashes des assets reels" \
  bash -lc 'node --experimental-strip-types scripts/code_harness/ws15_asset_export_proof.ts ws15-live-selected-v6 http://127.0.0.1:3001 > "$1" && jq -e ".ok == true and .bridgeUrlsRemaining == false and (.checks | length) == 8 and all(.checks[]; .sourceMatch == true)" "$1" && sha256sum -c output/ws15_inter_module_proof/v6_selected_sha256.txt' _ "$OUT/ws15-export-report.json"

mkdir -p "$OUT/ws12/artifacts"
run_required ws12_real_lab "WS12: 3 navigateurs, 2 AVD, Renode et 2 boots QEMU" \
  bash -lc '.venv/bin/python python-services/aurora_code/simulation_lab.py http://127.0.0.1:1431 "$1" 2500 > "$2"' _ "$OUT/ws12/artifacts" "$OUT/ws12/report.json"
run_required ws12_acceptance "WS12: oracles et artefacts reels" \
  bash -lc 'jq -e '\''([.stages[] | select(.status == "executed" and .realExecution == true)] | length) == 11 and ([.stages[] | select(.status == "unavailable" or .status == "degraded" or .status == "detected")] | length) == 0 and ([.stages[] | select(.status == "deferred" and .id == "console_emulation_feasibility")] | length) == 1 and all(.stages[] | select(.id == "android_real_mobile" or .id == "android_real_tablet"); .interactionExecuted == true and .interactionVerified == true)'\'' "$1" && while IFS= read -r artifact; do test -s "$artifact"; done < <(jq -r '\''.stages[] | (.artifactPath? // empty), (.screenshotPath? // empty)'\'' "$1")' _ "$OUT/ws12/report.json"

run_required final_visual_proof "Rendu reel V1/V3/V4 sur sept profils" \
  env AURORA_URL=http://127.0.0.1:1431 AURORA_PROOF_DIR="$OUT/screens" \
  node scripts/code_harness/final_visual_proof.mjs
run_required screenshot_pixel_audit "Dimensions, entropie et pixels non vides" \
  node scripts/code_harness/final_screenshot_pixel_audit.mjs \
  "$OUT/screens/report.json" "$OUT/screens/pixel-report.json"

FINISHED_AT="$(date --iso-8601=seconds)"
HEAD_COMMIT="$(git rev-parse HEAD)"
BRANCH="$(git branch --show-current)"
TRACKED_FILES="$(git ls-files | wc -l)"
PYTHON_FILES="$(git ls-files '*.py' | wc -l)"
REPORT_OK=false
if (( OVERALL == 0 )); then REPORT_OK=true; fi
jq -s \
  --arg startedAt "$STARTED_AT" \
  --arg finishedAt "$FINISHED_AT" \
  --arg branch "$BRANCH" \
  --arg commit "$HEAD_COMMIT" \
  --argjson trackedFiles "$TRACKED_FILES" \
  --argjson pythonFiles "$PYTHON_FILES" \
  --argjson ok "$REPORT_OK" \
  '{schemaVersion:"aurora.code.final-heavy-validation/1",startedAt:$startedAt,finishedAt:$finishedAt,branch:$branch,commit:$commit,trackedFiles:$trackedFiles,pythonFiles:$pythonFiles,steps:.,requiredFailures:[.[]|select(.status=="failed")],knownDebts:[.[]|select(.status=="warning")],ok:$ok}' \
  "$RESULTS" > "$OUT/final-report.json"

(
  cd "$OUT"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

jq '{ok,startedAt,finishedAt,steps:(.steps|length),requiredFailures,knownDebts}' "$OUT/final-report.json"
exit "$OVERALL"
