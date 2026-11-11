"""Retired Kaggle entry point: it never trained an Aurora model.

The previous body fitted a small MLP on ``torch.randn`` tensors and wrote an
``improvement_percent`` derived from an assumed initial loss of 1.0. That figure
was not a measurement, so the script now explains itself and fails.
"""
import sys

MESSAGE = """\
Ce script est retiré : il n'a jamais entraîné de modèle Aurora.
Il ajustait un petit réseau sur des tenseurs aléatoires, puis écrivait un
« improvement_percent » calculé à partir d'une perte initiale supposée de 1,0.
Ce pourcentage n'était pas une mesure.

Rien n'est entraîné ici et aucun fichier de statistiques n'est écrit.
Pour un entraînement réel et mesuré, utiliser :
    python -m auto_rl.professor.kaggle_runner
"""

print(MESSAGE)
sys.exit(1)
