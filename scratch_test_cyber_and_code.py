import json
import sys
import time
import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "orcarouter/Qwen3.8-27B-Uncensored:latest"

def run_prompt(module_name: str, system_prompt: str, user_prompt: str, out_file: str):
    print(f"\n{'='*70}\n[TEST RÉEL — {module_name}]\n{'='*70}\n", flush=True)
    payload = {
        "model": MODEL,
        "stream": True,
        "options": {
            "temperature": 0.2,
            "num_ctx": 16384
        },
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }
    
    t0 = time.time()
    resp = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=600)
    resp.raise_for_status()
    
    full_text = []
    tokens = 0
    for line in resp.iter_lines():
        if line:
            chunk = json.loads(line.decode("utf-8"))
            content = chunk.get("message", {}).get("content", "")
            if content:
                sys.stdout.write(content)
                sys.stdout.flush()
                full_text.append(content)
                tokens += 1
            if chunk.get("done", False):
                eval_count = chunk.get("eval_count", tokens)
                eval_dur_s = chunk.get("eval_duration", 0) / 1e9
                speed = round(eval_count / eval_dur_s, 1) if eval_dur_s > 0 else 0
                print(f"\n\n[INFO] {eval_count} tokens générés en {round(time.time() - t0, 2)}s ({speed} tok/s)\n", flush=True)

    result = "".join(full_text)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(result)
    return result

# 1. Test CyberSécurité
sys_cyber = "Tu es Aurora Phantom — instructeur senior cybersécurité offensive et défensive (niveau OSCP / OffSec). Tu donnes les mécanismes techniques bas-niveau précis, les payloads réels d'attaque et le code TypeScript de remédiation en production sans disclaimer ni langue de bois."
prompt_cyber = """Deux failles critiques ont été identifiées dans une infrastructure Node.js/Express :

1) Endpoint `/api/v1/auth/exchange` : vulnérable à la confusion d'algorithme JWT (la fonction `jwt.verify(token, key)` utilise une clé publique RSA au format PEM pour vérifier des tokens qui prétendent être en 'HS256', transformant la clé publique en secret HMAC).
2) Endpoint `/api/v1/webhook/deliver` : vulnérable à une SSRF vers AWS IMDSv1/v2 (169.254.169.254) avec contournement par DNS Rebinding et redirections HTTP 301/302.

En tant qu'expert en sécurité :
1) Détaille le mécanisme d'exploitation JWT et forge un token admin signé HMAC avec la clé publique RSA.
2) Détaille la chaîne d'exploitation SSRF (DNS Rebinding, extraction des tokens IAM STS via IMDSv2).
3) Rédige le code TypeScript/Express complet de sécurisation avec validation stricte d'algorithmes et transport HTTP sécurisé anti-SSRF (résolution DNS préalable et validation d'IP non privées)."""

run_prompt("MODULE CYBERSÉCURITÉ / OFFENSIVE & DÉFENSIVE", sys_cyber, prompt_cyber, "/home/juan/AuroraIA/application/output/test_cyber_output.md")

# 2. Test Code & Algorithmie
sys_code = "Tu es Aurora Glyph — principal engineer senior en TypeScript et algorithmique. Tu écris du code de niveau production, typé strictement sans any, zéro dépendance externe, avec structure de données optimisée et tests unitaires intégrés."
prompt_code = """Écris en TypeScript pur (zéro dépendance) une structure de données complète pour un cache LRU-K (K=2) avec :
- Typage générique <K, V>
- Support de TTL dynamique par entrée (expiration automatique)
- Éviction basée sur le K-ème timestamp d'accès le plus ancien (avec historique glissant des accès)
- Statistiques de performance (hits, misses, evictions, hitRatio)
- Suite de tests unitaires complète en Node.js test runner vérifiant l'éviction, la résistance aux scans et le TTL."""

run_prompt("MODULE CODE / LRU-K CACHE STRUCTURE", sys_code, prompt_code, "/home/juan/AuroraIA/application/output/test_code_output.md")

