export function dataDenseEnterpriseBlock(): string[] {
  return [
    '## ARCHETYPE: DATA-DENSE ENTERPRISE — interface operationnelle dense',
    '',
    '### Layout obligatoire',
    '- Sidebar compacte avec groupes d actions, topbar de recherche, filtres persistants et detail drawer.',
    '- Table principale dense mais lisible: header sticky, colonnes alignees, tri, statut, actions row-level.',
    '- Panneau de details lateral pour inspecter un item sans quitter la table.',
    '- KPI row compacte au-dessus de la table, charts petits mais informatifs.',
    '',
    '### Design',
    '- Densite assumee: font 13-14px, row height 36-44px, spacing 8/12/16.',
    '- Couleurs sobres: neutres + un accent fonctionnel; pas de hero marketing.',
    '- States complets: hover row, selected row, loading skeleton, empty state, error state.',
  ]
}

export function ideCodeEditorBlock(): string[] {
  return [
    '## ARCHETYPE: IDE / CODE EDITOR — workspace de developpement',
    '',
    '### Layout obligatoire',
    '- Activity bar verticale, file tree, editor tabs, editor pane, minimap ou outline, terminal bottom panel.',
    '- Barre de statut avec branche, erreurs, langage, position curseur.',
    '- Command palette modale accessible visuellement.',
    '',
    '### Design',
    '- Palette sombre type IDE, contrastes WCAG, monospace lisible.',
    '- Tokens de syntax highlighting coherents; pas de landing page.',
    '- Interactions: onglets actifs, selection fichier, panneau terminal repliable.',
  ]
}

export function osShellBlock(): string[] {
  return [
    '## ARCHETYPE: OS SHELL / BOOT CONSOLE — rendu systeme',
    '',
    '### Layout obligatoire',
    '- Fenetre terminal/console principale, boot log, prompt interactif, status bar systeme.',
    '- Panneau processus ou memoire si pertinent, messages kernel alignes monospace.',
    '- Indicateurs clairs: uptime, mode, target, erreurs.',
    '',
    '### Design',
    '- Monospace, grille stricte, contraste eleve, aucun marketing hero.',
    '- L effet visuel doit renforcer la lisibilite systeme: scanlines subtiles, cursor blink, log levels.',
  ]
}
