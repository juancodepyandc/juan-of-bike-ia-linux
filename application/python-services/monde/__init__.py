"""Moteur de scènes « monde » : intérieurs complets, villes, paysages, depuis une seule phrase.

Créé le 15/11/2026 après la cartographie de l'existant : une demande « intérieur de maison complet »
donnait trois pièces générées comme des objets isolés et posées en ligne, sans mur commun, sans porte,
sans meuble ; une ville donnait « les rues », « les immeubles » et « le parc » en trois blocs alignés.
Aucune scène n'était jugée.

Chaîne (chaque étape est une loi générale, jamais une règle par sujet) :
  programme (le LLM écrit un programme typé à partir de la phrase, vocabulaire fermé)
  → plan (pièces, murs, portes, fenêtres) / ville (rues, îlots, parcelles, bâtiments) / paysage (relief, eau,
    végétation)
  → disposition (contraintes mesurées : dans la pièce, sans chevauchement, dégagements, portes libres,
    chaque meuble accessible depuis une porte)
  → géométrie paramétrique (meubles, bâtiments) + matériaux PBR procéduraux
  → export glTF (un nœud par pièce et par objet, prêt à animer) → rendus f3d → porte mesurée.

Conventions communes : voir `monde.ir`. Vocabulaires fermés : `monde.vocabulaire`.
"""
