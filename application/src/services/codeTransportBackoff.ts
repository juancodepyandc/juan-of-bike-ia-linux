// Politique de reprise quand le service de modeles est INJOIGNABLE.
//
// Mesure reelle (run 1041): « Ollama: toutes les tentatives epuisees (3) [...]
// Derniere erreur: fetch failed », avec 0 octet de RAM libre sur la machine.
// Le bareme d origine (800 ms, 2 s, 4 s) s etale sur ~7 secondes au total;
// sous pression memoire, un rechargement de modele prend des dizaines de
// secondes. On abandonnait donc un run de 32 fichiers pendant que le service
// etait simplement en train de revenir.
//
// Distinction essentielle: un service INJOIGNABLE merite d etre attendu, un
// modele qui REFUSE le travail ne merite pas dix relances — s acharner sur une
// erreur deterministe est precisement le gaspillage corrige ailleurs dans ce
// module. Attendre ne consomme ni RAM ni VRAM: c est la seule forme de
// resilience acceptable sur cette machine, dont les gels historiques sont
// d origine memoire.

export const TRANSPORT_BACKOFF_MS = [1_000, 3_000, 8_000, 20_000, 40_000, 60_000] as const

/** L erreur decrit-elle un transport casse plutot qu un refus du modele ? */
export function isTransportFailure(message: string): boolean {
  return /\bfetch failed\b|\bECONNREFUSED\b|\bECONNRESET\b|\bsocket hang up\b|\bEAI_AGAIN\b|\bETIMEDOUT\b|network (?:error|request failed)/i.test(message)
}
