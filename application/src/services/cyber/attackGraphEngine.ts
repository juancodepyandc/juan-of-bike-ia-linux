/**
 * attackGraphEngine.ts — Moteur de modélisation de graphe d'attaque systémique,
 * cartographie des connexions réseau, chemins de pivot, et calcul du rayon d'impact (Blast Radius).
 *
 * Contexte : Compréhension systémique et analyse structurelle des menaces.
 */

export interface GraphNode {
  id: string
  name: string
  type: 'internet' | 'dmz' | 'internal' | 'database' | 'identity' | 'cloud' | 'crown-jewel'
  ip: string
  os: string
  vulnerabilities: string[]
  defenseControls: string[]
  criticality: number // 1..5
  x: number // Coordonnées 0..100 pour rendu SVG
  y: number // Coordonnées 0..100
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  protocol: 'HTTP/HTTPS' | 'SSH' | 'SQL' | 'RPC/SMB' | 'LDAP/Kerberos' | 'IAM API'
  port: number
  isCompromised: boolean
  isBlockedByFirewall: boolean
}

export interface AttackPath {
  id: string
  name: string
  steps: string[] // Node IDs
  likelihood: 'HIGH' | 'MEDIUM' | 'LOW'
  impactScore: number // 0..100
  chokepointNodeId: string // Meilleur endroit pour placer la défense
}

export interface SystemicInfrastructureGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  attackPaths: AttackPath[]
}

export const ENTERPRISE_SYSTEMIC_GRAPH: SystemicInfrastructureGraph = {
  nodes: [
    {
      id: 'ext-attacker',
      name: 'Menace Externe (Internet)',
      type: 'internet',
      ip: '198.51.100.4',
      os: 'Kali Linux / Custom Framework',
      vulnerabilities: [],
      defenseControls: ['WAF Edge', 'Cloudflare DDoS Shield'],
      criticality: 1,
      x: 10,
      y: 50,
    },
    {
      id: 'dmz-web',
      name: 'Web Portal (DMZ)',
      type: 'dmz',
      ip: '10.0.1.20',
      os: 'Debian 12 / NGINX',
      vulnerabilities: ['CVE-2025-1974 (Ingress RCE)', 'SSRF to Cloud Metadata'],
      defenseControls: ['WAF ModSecurity', 'Container ReadOnly RootFS'],
      criticality: 3,
      x: 32,
      y: 30,
    },
    {
      id: 'dmz-vpn',
      name: 'Passerelle VPN SSL',
      type: 'dmz',
      ip: '10.0.1.5',
      os: 'FortiOS Appliance',
      vulnerabilities: ['CVE-2024-21762 (Out-of-bounds Write RCE)'],
      defenseControls: ['MFA Obligatoire', 'GeoIP Blocking'],
      criticality: 4,
      x: 32,
      y: 70,
    },
    {
      id: 'int-api',
      name: 'API Microservice Interne',
      type: 'internal',
      ip: '10.0.2.15',
      os: 'Ubuntu 24.04 / Go Runtime',
      vulnerabilities: ['0-Day Race Condition Double-Spend', 'JWT Secret Key Leak'],
      defenseControls: ['Mutual TLS (mTLS)', 'eBPF Network Policy'],
      criticality: 3,
      x: 55,
      y: 30,
    },
    {
      id: 'int-ad',
      name: 'Active Directory Core (DC01)',
      type: 'identity',
      ip: '10.0.2.2',
      os: 'Windows Server 2022',
      vulnerabilities: ['Zerologon (CVE-2020-1472)', 'Kerberoasting PrivEsc'],
      defenseControls: ['Microsoft Defender for Identity', 'LAPS', 'Tier 0 Admin Isolation'],
      criticality: 5,
      x: 55,
      y: 70,
    },
    {
      id: 'db-customer',
      name: 'Postgres DB (Données Clients)',
      type: 'database',
      ip: '10.0.3.100',
      os: 'RedHat Enterprise Linux',
      vulnerabilities: ['SQL Injection via legacy stored proc', 'Cleartext Backup'],
      defenseControls: ['pg_crypto Encryption at rest', 'VPC Private Subnet'],
      criticality: 5,
      x: 80,
      y: 30,
    },
    {
      id: 'cloud-vault',
      name: 'Cloud Vault & HSM (Crown Jewel)',
      type: 'crown-jewel',
      ip: '192.168.200.10',
      os: 'AWS KMS / HashiCorp Vault Cluster',
      vulnerabilities: ['IAM Overprivileged Role Assumption'],
      defenseControls: ['Hardware HSM', 'Quorum Authorization (Multi-Signature)'],
      criticality: 5,
      x: 80,
      y: 70,
    },
  ],
  edges: [
    { id: 'e1', source: 'ext-attacker', target: 'dmz-web', protocol: 'HTTP/HTTPS', port: 443, isCompromised: false, isBlockedByFirewall: false },
    { id: 'e2', source: 'ext-attacker', target: 'dmz-vpn', protocol: 'HTTP/HTTPS', port: 10443, isCompromised: false, isBlockedByFirewall: false },
    { id: 'e3', source: 'dmz-web', target: 'int-api', protocol: 'HTTP/HTTPS', port: 8080, isCompromised: false, isBlockedByFirewall: false },
    { id: 'e4', source: 'dmz-vpn', target: 'int-ad', protocol: 'LDAP/Kerberos', port: 389, isCompromised: false, isBlockedByFirewall: false },
    { id: 'e5', source: 'int-api', target: 'db-customer', protocol: 'SQL', port: 5432, isCompromised: false, isBlockedByFirewall: false },
    { id: 'e6', source: 'int-ad', target: 'cloud-vault', protocol: 'IAM API', port: 443, isCompromised: false, isBlockedByFirewall: false },
    { id: 'e7', source: 'int-api', target: 'int-ad', protocol: 'RPC/SMB', port: 445, isCompromised: false, isBlockedByFirewall: true },
  ],
  attackPaths: [
    {
      id: 'path-web-to-db',
      name: 'Vecteur Web → API Interne → Base de Données',
      steps: ['ext-attacker', 'dmz-web', 'int-api', 'db-customer'],
      likelihood: 'HIGH',
      impactScore: 92,
      chokepointNodeId: 'int-api',
    },
    {
      id: 'path-vpn-to-vault',
      name: 'Vecteur VPN 0-Day → Active Directory → Cloud Vault',
      steps: ['ext-attacker', 'dmz-vpn', 'int-ad', 'cloud-vault'],
      likelihood: 'MEDIUM',
      impactScore: 99,
      chokepointNodeId: 'int-ad',
    },
  ],
}

export function computeBlastRadius(
  compromisedNodeId: string,
  graph: SystemicInfrastructureGraph = ENTERPRISE_SYSTEMIC_GRAPH,
): { reachableNodes: string[]; highRiskAssets: string[]; totalImpact: number } {
  const visited = new Set<string>([compromisedNodeId])
  const queue = [compromisedNodeId]

  while (queue.length > 0) {
    const current = queue.shift()!
    const outEdges = graph.edges.filter((e) => e.source === current && !e.isBlockedByFirewall)
    for (const edge of outEdges) {
      if (!visited.has(edge.target)) {
        visited.add(edge.target)
        queue.push(edge.target)
      }
    }
  }

  const reachableNodes = Array.from(visited).filter((id) => id !== compromisedNodeId)
  const reachableNodeObjects = graph.nodes.filter((n) => reachableNodes.includes(n.id))
  const highRiskAssets = reachableNodeObjects.filter((n) => n.criticality >= 4).map((n) => n.name)
  const totalImpact = Math.min(
    100,
    reachableNodeObjects.reduce((sum, n) => sum + n.criticality * 18, 0),
  )

  return {
    reachableNodes,
    highRiskAssets,
    totalImpact,
  }
}
