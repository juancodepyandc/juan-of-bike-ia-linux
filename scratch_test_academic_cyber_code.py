import json
import time
import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "orcarouter/Qwen3.8-27B-Uncensored:latest"

def ask_local_ai(system_prompt: str, user_prompt: str, temperature: float = 0.2):
    payload = {
        "model": MODEL,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": 16384
        },
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }
    t0 = time.time()
    resp = requests.post(OLLAMA_URL, json=payload, timeout=300)
    resp.raise_for_status()
    t1 = time.time()
    data = resp.json()
    content = data.get("message", {}).get("content", "")
    return {
        "content": content,
        "elapsed_s": round(t1 - t0, 2),
        "eval_count": data.get("eval_count", 0),
        "eval_duration": data.get("eval_duration", 0)
    }

print("Lancement du test 1 : Module Academique (Asservissement robotique & Routh-Hurwitz)...")
academic_sys = "Tu es Aurora Sage — principal engineer et professeur d'automatique et sciences de l'ingénieur. Tu résous avec une rigueur mathématique absolue, étape par étape, calculs exacts et sans approximation non justifiée."
academic_user = """Je travaille sur le dimensionnement d'un système d'asservissement en position d'un actionneur pour un robot de précision. La fonction de transfert en boucle ouverte non corrigée est G(p) = 10 / (p * (1 + 0.2*p) * (1 + 0.05*p)).
Fais une analyse complète d'ingénieur :
1) Calcule la fonction de transfert en boucle fermée H(p) = G(p)/(1+G(p)) à retour unitaire et détermine si le système non corrigé est stable (critère de Routh-Hurwitz).
2) Calcule la pulsation d'oscillation critique w_osc et le gain critique K_critique si on augmentait le gain.
3) Propose un correcteur à avance de phase C(p) = K * (1 + a*T*p)/(1 + T*p) ou PID pour obtenir une marge de phase de 45° à la pulsation de coupure désirée.
4) Donne la réponse indicielle qualitative (dépassement, temps de réponse à 5%).
Rédige les calculs algébriques complets."""

res_acad = ask_local_ai(academic_sys, academic_user)
print(f"Academique repondu en {res_acad['elapsed_s']}s ({res_acad['eval_count']} tokens).")
with open("/home/juan/AuroraIA/application/output/test_academic_output.md", "w", encoding="utf-8") as f:
    f.write(res_acad["content"])

print("\nLancement du test 2 : Module CyberSecurite (JWT Algorithm Confusion & SSRF AWS Metadata)...")
cyber_sys = "Tu es Aurora Phantom — instructeur senior cybersécurité offensive et défensive (niveau OSCP / OffSec). Tu donnes les vrais mécanismes techniques bas-niveau, les payloads d'attaque réels et le code de remédiation en production sans disclaimer ni langue de bois."
cyber_user = """On a découvert deux failles sur notre API Node.js/Express :
1) Endpoint `/api/v1/auth/exchange` : validation de tokens JWT avec confusion d'algorithme (l'application accepte à la fois RS256 et HS256 avec la même fonction de vérification qui charge la clé publique RSA).
2) Endpoint `/api/v1/webhook/deliver` : reçoit une URL `target_url` et fait un post Axios, permettant une SSRF vers AWS Metadata (169.254.169.254) ou le réseau interne via DNS Rebinding.

En tant qu'expert en sécurité :
- Démontre pas à pas comment un attaquant forge un token admin via la confusion RSA -> HMAC-SHA256 (avec la clé publique traitée comme clé secrète symétrique).
- Démontre comment contourner un filtre SSRF naïf (redirection 302, DNS rebinding avec TTL 0, encodages alternatifs d'IP).
- Écris le code TypeScript de remédiation complet, robuste et testé pour Express et Axios."""

res_cyber = ask_local_ai(cyber_sys, cyber_user)
print(f"Cyber repondu en {res_cyber['elapsed_s']}s ({res_cyber['eval_count']} tokens).")
with open("/home/juan/AuroraIA/application/output/test_cyber_output.md", "w", encoding="utf-8") as f:
    f.write(res_cyber["content"])

print("\nLancement du test 3 : Module Code (LRU-K Cache TypeScript avec TTL et Heap Min)...")
code_sys = "Tu es Aurora Glyph — principal engineer senior en TypeScript et algorithmique. Tu écris du code de niveau production, typé strictement sans any, zéro dépendance externe, avec gestion d'erreurs et suite de tests unitaires complète intégrée."
code_user = """Écris un module TypeScript complet et autonome pour un cache LRU-K (avec K=2, c'est-à-dire tracking des 2 derniers accès pour résister aux scans séquentiels massifs) qui supporte :
- Typage générique <K, V>
- Support de TTL dynamique par clé
- Éviction concurrente basée sur le K-ème timestamp d'accès le plus ancien
- Statistiques complètes (hits, misses, evictions, hitRatio)
- Suite de tests unitaires TypeScript exécutable vérifiant les cas nominaux et cas limites (TTL expiré, résistance aux scans, capacité maximale).
Donne le code TypeScript prêt à être exécuté avec tsx."""

res_code = ask_local_ai(code_sys, code_user)
print(f"Code repondu en {res_code['elapsed_s']}s ({res_code['eval_count']} tokens).")
with open("/home/juan/AuroraIA/application/output/test_code_output.md", "w", encoding="utf-8") as f:
    f.write(res_code["content"])

print("\nTous les tests ont ete enregistres dans application/output/")
