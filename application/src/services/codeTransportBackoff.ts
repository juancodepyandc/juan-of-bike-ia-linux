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

/**
 * Budget d horloge TOTAL pour recuperer UN appel de generation.
 *
 * Run 1131, mesure: la passe 8 est entree en recuperation a 15:13:40 et en est
 * sortie a 16:13:09 — 59,5 minutes pour un seul appel, 24 cycles, rien qui
 * avance et 0 Go de RAM libre. Le compte de tentatives avait ete choisi en
 * supposant des echecs RAPIDES (`fetch failed` revient tout de suite), mais
 * chaque tentative peut consommer le timeout complet de l appelant (20 min pour
 * une correction): six tentatives x 20 min = deux heures de pire cas.
 *
 * Un compteur de tentatives ne borne donc AUCUNE duree. Seule une horloge
 * borne. Passe ce budget, on rend la main et le pipeline livre le travail
 * preserve en phase `interrupted`, avec la cause exacte.
 */
export const RECOVERY_TOTAL_BUDGET_MS = 10 * 60_000
