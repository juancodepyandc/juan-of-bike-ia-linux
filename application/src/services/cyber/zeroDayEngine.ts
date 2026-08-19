/**
 * zeroDayEngine.ts — Moteur d'analyse et d'entraînement sur les vulnérabilités 0-day,
 * simulation de fuzzing, inspection de mémoire, et validation de correctifs défensifs.
 *
 * Contexte : Entraînement pédagogique & prévention défensive haute fidélité.
 */

export type ZeroDayArchetype =
  | 'heap-overflow'
  | 'use-after-free'
  | 'type-confusion'
  | 'stack-bof-rop'
  | 'race-condition-toctou'
  | 'deserialization-rce'
  | 'jwt-algorithm-confusion'
  | 'ssrf-cloud-metadata'
  | 'prototype-pollution'
  | 'integer-overflow-wrap'

export interface ZeroDayVulnerability {
  id: string
  title: string
  cwe: string
  archetype: ZeroDayArchetype
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM'
  cvss: number
  targetLanguage: 'C/C++' | 'Rust' | 'Go' | 'Python' | 'TypeScript/Node.js'
  targetLayer: 'Kernel' | 'Memory Allocator' | 'Network Daemon' | 'Web API' | 'Cryptographic Parser'
  discoveryMethod: 'Coverage-Guided Fuzzing' | 'Differential Analysis' | 'Static Taint Analysis' | 'Memory Sanitizer (ASan/MSan)'
  rootCause: string
  exploitPrimitive: string
  vulnerableCode: string
  patchedCode: string
  mitigationMatrix: {
    compilerLevel: string
    osLevel: string
    architectural: string
    detectionRule: string
  }
  reproductionSteps: string[]
}

export const ZERO_DAY_CATALOG: ZeroDayVulnerability[] = [
  {
    id: '0DAY-MEM-UAF',
    title: 'Kernel Network Socket Use-After-Free (UAF)',
    cwe: 'CWE-416: Use After Free',
    archetype: 'use-after-free',
    severity: 'CRITICAL',
    cvss: 9.8,
    targetLanguage: 'C/C++',
    targetLayer: 'Kernel',
    discoveryMethod: 'Coverage-Guided Fuzzing',
    rootCause:
      'Une race condition dans le gestionnaire de fermeture de socket libère la structure `sock_context` sans mettre à zéro le pointeur dans la table des descripteurs. Une référence concurrente permet de réallouer la mémoire avec un payload contrôlé.',
    exploitPrimitive:
      'Primitive d\'écriture arbitraire en espace noyau via Heap Spraying slub/slab, permettant l\'élévation de privilèges vers UID 0.',
    vulnerableCode: `// Code vulnérable (C Kernel Module)
void socket_release(struct sock_context *ctx) {
    if (ctx->refcount <= 0) {
        kfree(ctx);
        // ERREUR : Le pointeur n'est pas invalidé dans le tableau global !
        // ctx_table[ctx->id] pointe toujours sur la zone mémoire libérée.
    }
}

int socket_send(int sock_id, const char *buf, size_t len) {
    struct sock_context *ctx = ctx_table[sock_id];
    if (!ctx) return -EINVAL;
    // DANGER : Utilisation d'un objet potentiellement déjà kfree()
    return ctx->send_fn(ctx, buf, len);
}`,
    patchedCode: `// Correctif défensif (Safe Pattern)
void socket_release_safe(struct sock_context *ctx) {
    mutex_lock(&socket_table_lock);
    if (--ctx->refcount == 0) {
        ctx_table[ctx->id] = NULL; // Invalidation atomique immédiate
        mutex_unlock(&socket_table_lock);
        kfree(ctx);
        return;
    }
    mutex_unlock(&socket_table_lock);
}`,
    mitigationMatrix: {
      compilerLevel: 'KASAN (Kernel Address Sanitizer) + GCC -fstack-protector-strong',
      osLevel: 'SLAB_FREELIST_HARDENED + SLAB_FREELIST_RANDOM + Kernel Page Table Isolation (KPTI)',
      architectural: 'Passage aux structures gérées par comptage de références atomique (Rust for Linux / Arc)',
      detectionRule: 'Sigma: Suspicious Kernel Memory Allocation Anomaly / eBPF socket lifecycle probe',
    },
    reproductionSteps: [
      '1. Initialiser 50 descripteurs de socket concurrents.',
      '2. Déclencher un thread de fermeture intensive (socket_release).',
      '3. Effectuer un heap spray avec des structures forgées pointant send_fn sur un shellcode noyau.',
      '4. Appeler socket_send sur le descripteur dangling.',
    ],
  },
  {
    id: '0DAY-WEB-DESER',
    title: 'Insecure Object Deserialization RCE Gadget Chain',
    cwe: 'CWE-502: Deserialization of Untrusted Data',
    archetype: 'deserialization-rce',
    severity: 'CRITICAL',
    cvss: 10.0,
    targetLanguage: 'Python',
    targetLayer: 'Web API',
    discoveryMethod: 'Static Taint Analysis',
    rootCause:
      'L\'API désérialise un cookie de session encodé en base64 directement avec `pickle.loads()` ou `yaml.unsafe_load()` sans signature cryptographique HMAC ni validation de schéma.',
    exploitPrimitive:
      'Exécution de code arbitraire distante (RCE) sans authentification dès la réception du cookie.',
    vulnerableCode: `# Code vulnérable (Python Web API)
import pickle
import base64
from flask import request

@app.route('/api/profile')
def view_profile():
    raw_token = request.cookies.get('session_data')
    if not raw_token:
        return {'error': 'No session'}, 401
    
    # ERREUR FATALE : Désérialisation directe de données non vérifiées
    user_session = pickle.loads(base64.b64decode(raw_token))
    return {'username': user_session.username, 'role': user_session.role}`,
    patchedCode: `# Correctif défensif (Pydantic / JSON + HMAC-SHA256)
import json
import hmac
import hashlib
from pydantic import BaseModel

class SessionModel(BaseModel):
    username: str
    role: str

def safe_load_session(token: str, secret_key: bytes) -> SessionModel:
    raw_json, signature = token.rsplit('.', 1)
    expected_sig = hmac.new(secret_key, raw_json.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_sig):
        raise PermissionError("Signature de session falsifiée")
    
    data = json.loads(raw_json)
    return SessionModel.model_validate(data)`,
    mitigationMatrix: {
      compilerLevel: 'Bannir pickle/unsafe_load via linting Bandit / Semgrep',
      osLevel: 'Container read-only filesystem + Non-root execution sandbox',
      architectural: 'Migration intégrale vers JWT signé Ed25519 ou JSON Schema strict',
      detectionRule: 'WAF: Détection de signatures de serialized bytecode (ex: Python pickle opcode cos/system)',
    },
    reproductionSteps: [
      '1. Construire une classe avec méthode __reduce__ instanciant un appel système de diagnostic.',
      '2. Sérialiser l\'objet avec pickle.dumps() puis encoder en Base64.',
      '3. Injecter le cookie "session_data" dans une requête HTTP GET /api/profile.',
      '4. Observer la capture de l\'impact immédiat dans le bac à sable.',
    ],
  },
  {
    id: '0DAY-PROTO-RACE',
    title: 'Financial Transaction TOCTOU Double-Spend Race Condition',
    cwe: 'CWE-367: Time-of-check Time-of-use (TOCTOU) Race Condition',
    archetype: 'race-condition-toctou',
    severity: 'HIGH',
    cvss: 8.5,
    targetLanguage: 'TypeScript/Node.js',
    targetLayer: 'Web API',
    discoveryMethod: 'Differential Analysis',
    rootCause:
      'Vérification asynchrone du solde utilisateur séparée de la déduction par un appel `await` sans transaction ni verrou distribué (SELECT ... puis UPDATE sans FOR UPDATE).',
    exploitPrimitive:
      'Multiplication de fonds / double retrait par envois parallèles synchronisés sur HTTP/2 Multiplexing.',
    vulnerableCode: `// Code vulnérable (Node.js / Express)
app.post('/api/wallet/withdraw', async (req, res) => {
    const { userId, amount } = req.body;
    const user = await db.getUser(userId);
    
    // CHECK : Vérification du solde
    if (user.balance >= amount) {
        // FENÊTRE DE VULNÉRABILITÉ : Attente I/O avant la mise à jour
        await externalPaymentGateway.transfer(user.iban, amount);
        
        // USE : Mise à jour du solde trop tardive
        await db.updateBalance(userId, user.balance - amount);
        return res.json({ success: true });
    }
    return res.status(400).json({ error: 'Solde insuffisant' });
});`,
    patchedCode: `// Correctif défensif (Pessimistic Locking / Atomic SQL Transaction)
app.post('/api/wallet/withdraw', async (req, res) => {
    const { userId, amount } = req.body;
    
    // Transaction SQL avec verrouillage strict FOR UPDATE
    const success = await db.transaction(async (trx) => {
        const [user] = await trx.raw(
            'SELECT balance, iban FROM users WHERE id = ? FOR UPDATE', [userId]
        );
        if (!user || user.balance < amount) return false;
        
        await trx.raw(
            'UPDATE users SET balance = balance - ? WHERE id = ?', [amount, userId]
        );
        await externalPaymentGateway.transfer(user.iban, amount);
        return true;
    });
    
    return success ? res.json({ success: true }) : res.status(400).json({ error: 'Solde insuffisant' });
});`,
    mitigationMatrix: {
      compilerLevel: 'Analyse statique de concurrence (ESLint lock consistency rules)',
      osLevel: 'Rate limiting granulaire par IP et par compte utilisateur',
      architectural: 'Modèle Ledger immuable avec clés d\'idempotence obligatoires',
      detectionRule: 'SIEM: Détection de rafales de requêtes sur le même endpoint en < 5ms avec même token',
    },
    reproductionSteps: [
      '1. Ouvrir 20 streams HTTP/2 concurrents pointant sur /api/wallet/withdraw.',
      '2. Envoyer simultanément le payload avec amount = 100€ pour un compte disposant de 100€.',
      '3. Analyser la fenêtre de latence d\'accès base de données.',
      '4. Constater le solde négatif anormal sans le verrou transactionnel.',
    ],
  },
  {
    id: '0DAY-MEM-ROPOFLOW',
    title: 'Stack Buffer Overflow with ROP Chain Bypass (NX/ASLR)',
    cwe: 'CWE-121: Stack-based Buffer Overflow',
    archetype: 'stack-bof-rop',
    severity: 'CRITICAL',
    cvss: 9.8,
    targetLanguage: 'C/C++',
    targetLayer: 'Network Daemon',
    discoveryMethod: 'Coverage-Guided Fuzzing',
    rootCause:
      'Lecture non bornée dans un buffer de pile via `strcpy()` ou `sprintf()` lors du parsing d\'un en-tête de protocole propriétaire.',
    exploitPrimitive:
      'Contrôle du registre d\'instruction (RIP/EIP) et chaînage de gadgets ROP (Return-Oriented Programming) pour neutraliser NX et exécuter mprotect().',
    vulnerableCode: `// Code vulnérable (C Protocol Daemon)
void parse_client_packet(int client_fd) {
    char header_buffer[256];
    char raw_input[1024];
    
    ssize_t n = read(client_fd, raw_input, sizeof(raw_input));
    if (n <= 0) return;
    
    // ERREUR : Copie sans vérification de taille vers un buffer de 256 octets
    strcpy(header_buffer, raw_input);
    process_header(header_buffer);
}`,
    patchedCode: `// Correctif défensif (Bounded copy & Canary)
void parse_client_packet_safe(int client_fd) {
    char header_buffer[256];
    ssize_t n = read(client_fd, header_buffer, sizeof(header_buffer) - 1);
    if (n <= 0) return;
    
    header_buffer[n] = '\\0'; // Null termination garantie
    process_header(header_buffer);
}`,
    mitigationMatrix: {
      compilerLevel: 'GCC/Clang -fstack-protector-all -D_FORTIFY_SOURCE=2 -fPIE -pie',
      osLevel: 'ASLR complet (kernel.randomize_va_space=2) + Stack Non-Executable (NX bit)',
      architectural: 'Isolation de processus via seccomp-bpf filters et capsicum/pledge',
      detectionRule: 'EDR: Détection d\'anomalie de pile (Stack Pivot / Corrupted Ret Address)',
    },
    reproductionSteps: [
      '1. Fuzzer l\'entrée avec un pattern cyclique De Bruijn pour calculer l\'offset exact du registre RIP.',
      '2. Identifier une fuite d\'adresse mémoire (Info Leak) pour calculer la base libc.',
      '3. Assembler une chaîne de gadgets (pop rdi; ret, system, bin_sh).',
      '4. Tester la mitigation stack canary qui bloque immédiatement l\'écrasement de pile.',
    ],
  },
]

export interface FuzzingSimulationResult {
  totalIterations: number
  uniqueCrashes: number
  codeCoveragePct: number
  discoveredArchetypes: ZeroDayArchetype[]
  crashLogs: Array<{
    iteration: number
    payloadHex: string
    faultAddress: string
    signal: 'SIGSEGV' | 'SIGABRT' | 'SIGBUS' | 'ASSERT_FAIL'
    inferredVuln: string
    remedy: string
  }>
  fuzzSpeedIps: number
}

export function runFuzzingSimulation(
  targetArchetype: ZeroDayArchetype,
  iterationTarget = 1500,
): FuzzingSimulationResult {
  const crashes: FuzzingSimulationResult['crashLogs'] = []
  let crashCount = 0
  const speed = Math.floor(18000 + Math.random() * 8000)

  // Simulation probabiliste et déterministe basée sur les mutations de fuzzing
  for (let i = 1; i <= iterationTarget; i += Math.floor(iterationTarget / 6)) {
    if (i > 100) {
      crashCount++
      const faultAddr = `0x7fff${Math.floor(Math.random() * 0xffff).toString(16).padStart(4, '0')}`
      crashes.push({
        iteration: i,
        payloadHex: '\\x41'.repeat(16) + '\\xeb\\x04' + '\\xff\\xff\\xff\\xff',
        faultAddress: faultAddr,
        signal: targetArchetype.includes('mem') || targetArchetype.includes('stack') ? 'SIGSEGV' : 'SIGABRT',
        inferredVuln: `Dépassement de structure détecté (Archetype: ${targetArchetype}) à l'itération ${i}`,
        remedy: 'Appliquer vérification de bornes stricte et vérification atomique des types.',
      })
    }
  }

  return {
    totalIterations: iterationTarget,
    uniqueCrashes: Math.max(1, crashCount),
    codeCoveragePct: Math.min(99.4, 72 + Math.floor(Math.random() * 24)),
    discoveredArchetypes: [targetArchetype],
    crashLogs: crashes,
    fuzzSpeedIps: speed,
  }
}
