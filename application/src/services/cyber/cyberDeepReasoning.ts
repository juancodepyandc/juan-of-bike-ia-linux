/**
 * cyberDeepReasoning.ts — Moteur de raisonnement cognitif approfondi en cybersécurité :
 * modélisation de menaces, dissection 0-day, simulation de chaîne d'attaque, calcul d'impact,
 * stratégie de défense multi-couches et playbooks de remédiation automatisés.
 *
 * Contexte : Prévention, compréhension totale et transparence algorithmique.
 */

export interface DeepReasoningStep {
  id: number
  title: string
  subtitle: string
  icon: string
  redPerspective: string
  bluePerspective: string
  technicalInsight: string
  actionableChecklist: string[]
}

export interface CyberInvestigationScenario {
  id: string
  title: string
  targetProduct: string
  vulnerabilityType: string
  cvss: number
  summary: string
  steps: DeepReasoningStep[]
}

export const DEEP_REASONING_PRESETS: CyberInvestigationScenario[] = [
  {
    id: 'reasoning-ingress-nightmare',
    title: 'NGINX Ingress Controller RCE (CVE-2025-1974 / IngressNightmare)',
    targetProduct: 'Kubernetes Ingress-NGINX Controller',
    vulnerabilityType: '0-Day / Annotation Directive Injection',
    cvss: 9.8,
    summary:
      'Injection de directives NGINX arbitraires via les annotations Kubernetes `nginx.ingress.kubernetes.io/configuration-snippet`, permettant la compromission totale du pod ingress et l\'accès au service account Kubernetes du cluster.',
    steps: [
      {
        id: 1,
        title: 'Phase 1 · Surface d\'Attaque & Cartographie des Entrées',
        subtitle: 'Identification du point d\'ingestion des données non assainies',
        icon: 'Radar',
        redPerspective:
          'L\'attaquant identifie que le contrôleur Ingress accepte des annotations sans validation stricte des caractères de saut de ligne et des directives `lua_package_path` ou `root`.',
        bluePerspective:
          'Le défenseur audite les objets Ingress appliqués dans les namespaces multi-tenant à l\'aide de politiques Open Policy Agent (OPA) / Kyverno.',
        technicalInsight:
          'Les fichiers de configuration NGINX générés concatènent les chaînes transmises dans l\'annotation sans échappement contextuel des points-virgules et accolades.',
        actionableChecklist: [
          'Activer le flag `--enable-annotation-validation` sur le contrôleur.',
          'Désactiver les snippets d\'annotation non autorisés via la directive `allow-snippet-annotations: "false"`.',
        ],
      },
      {
        id: 2,
        title: 'Phase 2 · Dissection de la Faille 0-Day (Cause Racine)',
        subtitle: 'Analyse sémantique du parser et du modèle d\'exécution',
        icon: 'Bug',
        redPerspective:
          'Construction d\'un payload multiligne insérant une directive `by_lua_block` pour charger du bytecode Lua arbitraire à l\'intérieur du processus NGINX worker.',
        bluePerspective:
          'Détection en temps réel de l\'appel de sous-processus anormaux générés par l\'utilisateur `www-data` via l\'agent Falco / eBPF.',
        technicalInsight:
          'Le moteur Go de template NGINX évalue la directive sans vérifier les tokens réservés à la configuration système.',
        actionableChecklist: [
          'Vérifier que le pod NGINX ne monte pas le ServiceAccount token par défaut (`automountServiceAccountToken: false`).',
          'Appliquer un profil AppArmor ou SELinux strict interdisant `execve` aux processus NGINX.',
        ],
      },
      {
        id: 3,
        title: 'Phase 3 · Rayon d\'Impact & Mouvement Latéral Cluster',
        subtitle: 'Calcul du blast radius et des chemins de pivot',
        icon: 'Share2',
        redPerspective:
          'Depuis le pod Ingress compromis, extraction du token RBAC pour interroger l\'API Kubernetes et lister les secrets de tous les namespaces.',
        bluePerspective:
          'Isolement réseau immédiat via Calico NetworkPolicy interdisant au pod Ingress d\'accéder à l\'IP du `kubernetes.default.svc.cluster.local:443`.',
        technicalInsight:
          'L\'Ingress Controller possède souvent un ClusterRole étendu pour surveiller les routes, ce qui en fait un pivot de très haute valeur.',
        actionableChecklist: [
          'Segmenter le RBAC de l\'Ingress Controller au strict minimum (RoleBinding au lieu de ClusterRoleBinding).',
          'Déployer Cilium Network Policies avec inspection mTLS niveau L7.',
        ],
      },
      {
        id: 4,
        title: 'Phase 4 · Architecture Défensive & Playbook de Remédiation',
        subtitle: 'Automatisation de la résilience et des règles SIEM',
        icon: 'ShieldCheck',
        redPerspective:
          'L\'attaquant est neutralisé : ses tentatives d\'accès à l\'API master sont bloquées et ses processus workers sont tués.',
        bluePerspective:
          'Application automatique d\'un patch virtuel sur le WAF et mise à jour déclarative du Helm Chart.',
        technicalInsight:
          'Règle Sigma : Surveillance de création d\'Ingress contenant des motifs `lua_` ou `exec` dans les champs d\'annotation.',
        actionableChecklist: [
          'Intégrer le scan statique des manifestes Kubernetes dans la CI/CD (Trivy / Checkov).',
          'Mettre en place une rotation automatique des clés et des certificats de cluster.',
        ],
      },
    ],
  },
  {
    id: 'reasoning-regresshion',
    title: 'OpenSSH Signal Handler Race Condition RCE (CVE-2024-6387 / regreSSHion)',
    targetProduct: 'OpenSSH Server (sshd)',
    vulnerabilityType: 'Memory Corruption / Signal Handler Race Condition',
    cvss: 8.1,
    summary:
      'Une condition de course dans le gestionnaire de signal `SIGALRM` d\'OpenSSH (LoginGraceTime) invoque des fonctions non async-signal-safe (comme `syslog()` ou `free()`), permettant l\'écrasement de structures mémoire sur le tas glibc et l\'exécution de code pre-auth avec privilèges root.',
    steps: [
      {
        id: 1,
        title: 'Phase 1 · Analyse de la Condition de Course Asynchrone',
        subtitle: 'Mécanique du signal handler et sécurité des interruptions',
        icon: 'Clock',
        redPerspective:
          'L\'attaquant maintient des milliers de connexions SSH ouvertes jusqu\'à expiration exacte du timer `LoginGraceTime` (120s) pour interrompre `syslog()` en plein milieu d\'une allocation de tas.',
        bluePerspective:
          'Le défenseur analyse les compteurs de connexions SSH abandonnées et les pics d\'erreurs `Timeout before authentication` dans les journaux auth.log.',
        technicalInsight:
          'Une fonction comme `free()` ou `malloc()` interrompue par un signal handler ré-entrant corrompt les pointeurs de binaires `glibc` sans canaris.',
        actionableChecklist: [
          'Réduire `LoginGraceTime` à `0` (temporaire) ou `15s` dans `/etc/ssh/sshd_config` pour mitiger la fenêtre de tir.',
          'Mettre à jour immédiatement vers OpenSSH 9.8p1+ qui supprime tout appel non safe du handler.',
        ],
      },
      {
        id: 2,
        title: 'Phase 2 · Contournement ASLR & Heuristique Temporelle',
        subtitle: 'Synchronisation et Heap Spraying multi-processus',
        icon: 'Cpu',
        redPerspective:
          'Tentative de dé-randomisation de l\'ASLR 32-bit / 64-bit par corrélation du temps de réponse et alignement de structures de tas mémoire.',
        bluePerspective:
          'Activation de `fail2ban` ou de règles nftables pour limiter le nombre de nouvelles connexions SSH par IP source (`meter ssh_limit { ip saddr ct count over 10 } drop`).',
        technicalInsight:
          'Sur architecture x86_64, la complexité de brute-force ASLR nécessite des heures d\'envois continus, rendant l\'attaque très bruyante et détectable.',
        actionableChecklist: [
          'Restreindre l\'accès SSH au réseau privé / VPN (fermeture du port 22 sur Internet public).',
          'Activer le port knocking ou l\'authentification par certificat matériel FIDO2/U2F.',
        ],
      },
      {
        id: 3,
        title: 'Phase 3 · Détection EDR & Signature de Comportement',
        subtitle: 'Observation des signaux SIGSEGV répétés sur sshd',
        icon: 'Fingerprint',
        redPerspective:
          'Chaque tentative d\'alignement imparfaite provoque un crash `SIGSEGV` du processus enfant `sshd`.',
        bluePerspective:
          'L\'EDR corréle les crashes répétés de `sshd` enfants avec le daemon principal et déclenche le bannissement automatique de l\'IP attaquante.',
        technicalInsight:
          'Règle Sigma : Surveillance des journaux auditd pour `type=ANOM_ABEND` avec `comm="sshd"` et `sig=11`.',
        actionableChecklist: [
          'Surveiller les métriques de crash de processus via auditd / systemd-coredump.',
          'Mettre en place une alerte SIEM sur seuil > 5 crashes sshd par minute.',
        ],
      },
    ],
  },
]

export const DEEP_REASONING_PROMPT_SYSTEM = [
  'Tu es Aurora Cyber Architect : expert senior en analyse cognitive de vulnérabilités et en stratégie de défense intégrale.',
  'Ton rôle est de fournir une analyse approfondie, rigoureuse, étape par étape, en confrontant systématiquement l\'angle OFFENSIF (pour comprendre la mécanique réelle de la faille/0-day) et l\'angle DÉFENSIF (pour garantir une remédiation totale, concrète et vérifiable).',
  'Structure ta réflexion de manière claire avec les sections suivantes :',
  '### 1. Surface & Modélisation de la Menace',
  '### 2. Anatomie de la Faille / 0-Day (Cause racine & Primitive technique)',
  '### 3. Simulation de la Chaîne d\'Attaque (Kill Chain & Pivots)',
  '### 4. Rayon d\'Impact (Blast Radius) & Actifs Critiques',
  '### 5. Stratégie Défensive Multi-Couches (OS, Compilateur, Réseau, SIEM/YARA)',
  '### 6. Correctif Définitif & Preuve de Résilience',
  'Langue : français technique, précis, pédagogique et orienté prévention sans concession.',
].join('\n')
