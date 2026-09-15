import json
import sys
import time
import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "orcarouter/Qwen3.8-27B-Uncensored:latest"

def run_prompt(module_name: str, system_prompt: str, user_prompt: str):
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

    return "".join(full_text)

# 1. Test Académique
sys_acad = "Tu es Aurora Sage — principal engineer et professeur d'automatique et sciences de l'ingénieur. Tu réponds avec une rigueur mathématique absolue, étape par étape, calculs exacts et sans approximation non justifiée."
prompt_acad = """Je travaille sur le dimensionnement d'un système d'asservissement en position d'un actionneur pour un robot de précision. La fonction de transfert en boucle ouverte non corrigée est :
G(p) = 10 / (p * (1 + 0.2*p) * (1 + 0.05*p))

Fais une analyse complète d'ingénieur :
1) Calcule la fonction de transfert en boucle fermée H(p) = G(p)/(1+G(p)) à retour unitaire.
2) Détermine si le système non corrigé en boucle fermée est stable en appliquant rigoureusement le critère de Routh-Hurwitz.
3) Calcule la pulsation d'oscillation critique w_osc et le gain statique critique K_critique pour lequel le système est à la limite de stabilité.
4) Dimensionne un correcteur pour garantir la stabilité et une marge de phase de 45°.
Rédige les calculs algébriques complets."""

out_acad = run_prompt("MODULE ACADÉMIQUE / AUTOMATIQUE", sys_acad, prompt_acad)
with open("/home/juan/AuroraIA/application/output/test_academic_output.md", "w", encoding="utf-8") as f:
    f.write(out_acad)

