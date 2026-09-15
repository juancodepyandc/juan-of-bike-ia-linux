#!/usr/bin/env python3
"""AuroraIA Masterpiece Complex Generator

Executes real end-to-end FLUX.2 generations for highly complex, detail-dense subjects:
1. PERSO  : Guerrière Cyber-Samouraï dans un temple néo-Tokyo (lumières dynamiques, armure ornée, sabre cyan)
2. ASSETS : Coffre au trésor steampunk & arcanique (rouages laiton, runes violettes, gemmes, cristaux)
3. DECOR  : Cité flottante solarpunk au lever du soleil (dômes de verre, cascades, aéronefs solaires)
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from image_module_engine import generate_image_manifest

def run_suite():
    print("=================================================================")
    print("🚀 LANCEMENT DU GÉNÉRATEUR DE SUJETS COMPLEXES & HAUTE DENSITÉ")
    print("=================================================================\n")
    
    jobs = [
        {
            "num": "1/3",
            "cat": "perso",
            "title": "Guerrière Cyber-Samouraï au Temple Néo-Tokyo",
            "prompt": "portrait cinématique en pied d'une guerrière samouraï cyberpunk en armure laquée rouge carmin et dorures de dragon impérial, tenant un katana à lame d'énergie bleu cyan incandescent, pose martiale vive dans la cour d'un temple néo-japonais au crépuscule, pétales de cerisier holographiques flottant dans l'air, éclairage dramatique chiaroscuro avec reflets volumétriques et textures organiques et métalliques ultra détaillées"
        },
        {
            "num": "2/3",
            "cat": "assets",
            "title": "Coffre au Trésor Steampunk & Arcanique",
            "prompt": "coffre au trésor légendaire steampunk et arcanique avec mécanismes de rouages en laiton poli apparents, serrures gravées de runes violettes luminescentes, cristaux arcaniques flottants, bois précieux sculpté et sangles de cuir rivetées d'or pour asset de jeu vidéo rpg 3d, éclairage de studio neutre et fond sombre épuré"
        },
        {
            "num": "3/3",
            "cat": "decor",
            "title": "Cité Flottante Solarpunk au Lever du Soleil",
            "prompt": "paysage majestueux d'une immense cité flottante solarpunk dans les cieux dorés de l'aube, dômes bioclimatiques en verre étincelant avec jardins suspendus luxuriants, cascades d'eau pure tombant dans les nuages moutonnants, élégants aéronefs à voiles photovoltaïques dorées voguant dans les airs, rayons de lumière volumétrique du matin et détails architecturaux foisonnants"
        }
    ]
    
    for job in jobs:
        print(f"\n--- [RENDU {job['num']}] CATÉGORIE : {job['cat'].upper()} ({job['title']}) ---")
        print(f"Demande : \"{job['prompt']}\"\n")
        
        t0 = time.time()
        manifest = generate_image_manifest(
            raw_prompt=job["prompt"],
            use_comfy=True
        )
        elapsed = time.time() - t0
        
        pkg = manifest["package_files"]
        qa = manifest["quality_assurance_metrics"]
        print(f"\n[SUCCÈS RENDU {job['num']}] :")
        print(f"  • Dossier Sujet  : {pkg['directory']}")
        print(f"  • Master Image   : {pkg['master_image']}")
        print(f"  • Fichiers pack  : {len(pkg['derived_files']) + 5} fichiers créés")
        print(f"  • Moteur utilisé : {manifest['generation_params']['engine']}")
        print(f"  • Temps total    : {elapsed:.2f}s")
        print(f"  • Netteté Lapl.  : {qa['sharpness_laplacian_variance']}")
        print(f"  • Contraste      : {qa['contrast_std']}")
        print(f"  • Palette        : {qa['dominant_palette_hex'][:4]}")

if __name__ == "__main__":
    run_suite()
