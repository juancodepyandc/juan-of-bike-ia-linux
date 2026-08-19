/**
 * webEndpointAuditor.ts — Moteur d'audit passif de sécurité des endpoints web et génération
 * de guides de durcissement (Hardening & DoS Resilience).
 *
 * Contexte : Analyse architecturale non destructive, conformité OWASP / Vercel / Cloudflare.
 */

import { formatSecurityReport, type CyberExportPayload } from './cyberOutputManager.ts'

export interface SecurityHeaderCheck {
  header: string
  present: boolean
  value?: string
  recommended: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  status: 'PASS' | 'FAIL' | 'WARN'
  explanation: string
}

export interface WebAuditResult {
  targetUrl: string
  timestamp: string
  protocol: string
  securityScore: number // 0..100
  grade: 'A+' | 'A' | 'B' | 'C' | 'D' | 'F'
  headersAnalysis: SecurityHeaderCheck[]
  dosResilienceScore: number // 0..100
  dosObservations: string[]
  recommendedHardening: {
    vercelJsonConfig: string
    nextConfigJs: string
    middlewareRateLimit: string
  }
  exportPayload: CyberExportPayload
}

export const RECOMMENDED_SECURITY_HEADERS: Record<string, { recommended: string; severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'; explanation: string }> = {
  'Content-Security-Policy': {
    recommended: "default-src 'self'; script-src 'self' 'nonce-...'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none';",
    severity: 'CRITICAL',
    explanation: 'Empêche l\'exécution de scripts tiers non autorisés (mitigation majeure XSS et injection de code).',
  },
  'Strict-Transport-Security': {
    recommended: 'max-age=63072000; includeSubDomains; preload',
    severity: 'HIGH',
    explanation: 'Force le navigateur à utiliser uniquement HTTPS et prévient le déclassement SSL/TLS (SSL Stripping).',
  },
  'X-Frame-Options': {
    recommended: 'DENY',
    severity: 'HIGH',
    explanation: 'Empêche l\'intégration du site dans une <iframe> externe (mitigation anti-Clickjacking).',
  },
  'X-Content-Type-Options': {
    recommended: 'nosniff',
    severity: 'MEDIUM',
    explanation: 'Bloque le reniflage MIME du navigateur pour empêcher l\'interprétation de fichiers statiques en exécutables.',
  },
  'Referrer-Policy': {
    recommended: 'strict-origin-when-cross-origin',
    severity: 'MEDIUM',
    explanation: 'Contrôle la fuite d\'URLs et de tokens sensibles dans les en-têtes Referer lors des navigations externes.',
  },
  'Permissions-Policy': {
    recommended: 'camera=(), microphone=(), geolocation=(), interest-cohort=()',
    severity: 'LOW',
    explanation: 'Désactive l\'accès aux fonctionnalités matérielles du navigateur non requises par l\'application.',
  },
}

/**
 * Effectue une analyse architecturale d'un endpoint web à partir de son URL et de ses en-têtes.
 */
export function auditWebEndpoint(
  url: string,
  rawHeaders: Record<string, string> = {},
): WebAuditResult {
  let normalizedUrl = url.trim()
  if (!/^https?:\/\//i.test(normalizedUrl)) {
    normalizedUrl = 'https://' + normalizedUrl
  }

  const isHttps = normalizedUrl.startsWith('https://')
  const headersLower: Record<string, string> = {}
  for (const [k, v] of Object.entries(rawHeaders)) {
    headersLower[k.toLowerCase()] = v
  }

  const checks: SecurityHeaderCheck[] = []
  let missingCriticalCount = 0
  let missingHighCount = 0
  let missingMediumCount = 0

  for (const [headerName, meta] of Object.entries(RECOMMENDED_SECURITY_HEADERS)) {
    const val = headersLower[headerName.toLowerCase()]
    const present = Boolean(val && val.trim().length > 0)

    let status: 'PASS' | 'FAIL' | 'WARN' = 'FAIL'
    if (present) {
      status = 'PASS'
    } else {
      if (meta.severity === 'CRITICAL') missingCriticalCount++
      else if (meta.severity === 'HIGH') missingHighCount++
      else missingMediumCount++
    }

    checks.push({
      header: headerName,
      present,
      value: val,
      recommended: meta.recommended,
      severity: meta.severity,
      status,
      explanation: meta.explanation,
    })
  }

  // Calcul du score de conformité
  let score = 100
  if (!isHttps) score -= 40
  score -= missingCriticalCount * 25
  score -= missingHighCount * 15
  score -= missingMediumCount * 8
  const finalScore = Math.max(10, Math.min(100, score))

  let grade: WebAuditResult['grade'] = 'F'
  if (finalScore >= 95) grade = 'A+'
  else if (finalScore >= 85) grade = 'A'
  else if (finalScore >= 70) grade = 'B'
  else if (finalScore >= 55) grade = 'C'
  else if (finalScore >= 40) grade = 'D'

  // Évaluation de la résilience DoS (Cloud / Serverless / Edge)
  const isVercel = normalizedUrl.includes('vercel.app') || Boolean(headersLower['x-vercel-id'])
  const hasRateLimitHeader = Boolean(headersLower['x-ratelimit-limit'] || headersLower['retry-after'])

  const dosObservations: string[] = []
  let dosScore = 70

  if (isVercel) {
    dosObservations.push('Infrastructure Vercel Edge / Serverless détectée : Isolation native par fonction et absorption DDoS automatique au niveau réseau.')
    dosScore += 15
  } else {
    dosObservations.push('Hébergement standard détecté : Recommandation d\'ajouter un CDN en amont (Cloudflare DDoS Shield).')
  }

  if (hasRateLimitHeader) {
    dosObservations.push('En-têtes de limitation de débit (Rate-Limiting) actifs détectés.')
    dosScore += 15
  } else {
    dosObservations.push('Absence de middleware applicatif de Rate-Limiting visible : Risque d\'épuisement de quota sur les routes API coûteuses.')
    dosScore -= 20
  }

  // Snippets de configuration durcie
  const vercelJsonConfig = JSON.stringify(
    {
      headers: [
        {
          source: '/(.*)',
          headers: [
            { key: 'Content-Security-Policy', value: "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https:;" },
            { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
            { key: 'X-Frame-Options', value: 'DENY' },
            { key: 'X-Content-Type-Options', value: 'nosniff' },
            { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
            { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
          ],
        },
      ],
    },
    null,
    2,
  )

  const nextConfigJs = `// next.config.js — Durcissement des en-têtes HTTP de sécurité
const securityHeaders = [
  { key: 'X-DNS-Prefetch-Control', value: 'on' },
  { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
  { key: 'X-Frame-Options', value: 'DENY' },
  { key: 'X-Content-Type-Options', value: 'nosniff' },
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
  {
    key: 'Content-Security-Policy',
    value: "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;",
  },
];

module.exports = {
  poweredByHeader: false, // Supprime l'en-tête X-Powered-By pour éviter le fingerprinting
  async headers() {
    return [{ source: '/:path*', headers: securityHeaders }];
  },
};`

  const middlewareRateLimit = `// middleware.ts — Protection Anti-Abus & Rate-Limiting Edge (Upstash / Memory)
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const ipHits = new Map<string, { count: number; expires: number }>();

export function middleware(request: NextRequest) {
  const ip = request.ip || request.headers.get('x-forwarded-for') || '127.0.0.1';
  const now = Date.now();
  const windowMs = 60 * 1000; // Fenêtre de 1 minute
  const maxRequests = 120;     // 120 requêtes / min max par IP

  const record = ipHits.get(ip);
  if (!record || now > record.expires) {
    ipHits.set(ip, { count: 1, expires: now + windowMs });
  } else {
    record.count++;
    if (record.count > maxRequests) {
      return new NextResponse('Trop de requêtes — Ralentissez.', {
        status: 429,
        headers: { 'Retry-After': '60' },
      });
    }
  }

  return NextResponse.next();
}

export const config = { matcher: '/api/:path*' };`

  const exportPayload = formatSecurityReport(
    normalizedUrl,
    `Audit d'architecture de sécurité sur **${normalizedUrl}**. Score global : **${finalScore}/100** (Grade **${grade}**). Score de résilience DoS : **${dosScore}/100**.`,
    [
      {
        title: 'Analyse des En-Têtes de Sécurité HTTP',
        body: checks
          .map((c) => `- **${c.header}** [${c.status}] : ${c.present ? `Valeur = \`${c.value}\`` : `_MANQUANT_ · Recommandé : \`${c.recommended}\``}\n  _${c.explanation}_`)
          .join('\n\n'),
      },
      {
        title: 'Résilience au Déni de Service & Protection de Charge',
        body: dosObservations.map((o) => `- ${o}`).join('\n'),
      },
      {
        title: 'Configuration Durcie Clé-en-Main (vercel.json)',
        body: '```json\n' + vercelJsonConfig + '\n```',
      },
      {
        title: 'Configuration Durcie Next.js (next.config.js)',
        body: '```javascript\n' + nextConfigJs + '\n```',
      },
      {
        title: 'Middleware Anti-Abus & Rate-Limiting (middleware.ts)',
        body: '```typescript\n' + middlewareRateLimit + '\n```',
      },
    ],
  )

  return {
    targetUrl: normalizedUrl,
    timestamp: new Date().toISOString(),
    protocol: isHttps ? 'HTTPS (TLS)' : 'HTTP (Non chiffré)',
    securityScore: finalScore,
    grade,
    headersAnalysis: checks,
    dosResilienceScore: Math.min(100, Math.max(0, dosScore)),
    dosObservations,
    recommendedHardening: {
      vercelJsonConfig,
      nextConfigJs,
      middlewareRateLimit,
    },
    exportPayload,
  }
}
