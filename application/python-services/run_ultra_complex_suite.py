import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from image_module_engine import generate_image_manifest, BASE_OUTPUT_DIR

JOBS = [
    {
        "category": "assets",
        "slug": "astrolabe_alchimique_orbe_celeste",
        "title": "Astrolabe Mécanique & Orbe Céleste Alchimique",
        "prompt": (
            "asset de jeu vidéo rpg 3d légendaire représentant un astrolabe alchimique et orbe céleste antique mécanique, "
            "sept anneaux concentriques rotatifs en laiton brossé et argent ciselé de runes zodiacales avec engrenages "
            "miniatures dentés apparents d'une précision horlogère suisse, au centre un globe de verre taillé translucide "
            "contenant une nébuleuse miniature tourbillonnante aux reflets violets et dorés, monté sur un lourd piédestal "
            "octogonal en bois de palissandre foncé sculpté avec ferrures dorées et lentilles optiques télescopiques en cristal, "
            "éclairage de studio neutre et précis mettant en valeur les textures métalliques patinées et les micro-rayures réalistes, "
            "fond gris anthracite sombre épuré, rendu 3d octanerender photoréaliste, netteté extrême"
        )
    },
    {
        "category": "decor",
        "slug": "neo_venise_cyber_baroque_crepuscule",
        "title": "Métropole Flottante Néo-Venise Cyber-Baroque",
        "prompt": (
            "vue panoramique grandiose d'une métropole flottante néo-vénitienne cyber-baroque au crépuscule doré, "
            "d'immenses canaux d'eau turquoise cristalline suspendus dans le ciel entre des palais en marbre blanc de Carrare "
            "et des ponts ornés de statues dorées entrelacées de câblages néon ambre et cyan, dômes monumentaux en verre cathédrale "
            "illuminés de l'intérieur par des lustres gigantesques, d'élégantes gondoles volantes à sustentation magnétique et "
            "propulseurs ioniques glissant au-dessus de la brume dorée, ciel crépusculaire spectaculaire embrasé de nuances pourpre, "
            "orange vif et magenta, rayons de soleil volumétriques perçant les arches, reflets miroirs ultra détaillés sur l'eau "
            "et les façades, composition épique d'une richesse architecturale foisonnante"
        )
    }
]

def main():
    print("=" * 70)
    print("🚀 SUITE HAUTE DENSITÉ : ASSETS & DECOR")
    print("=" * 70)
    
    results = []
    for i, job in enumerate(JOBS, 2):
        print(f"\n--- [RENDU {i}/3] CATÉGORIE : {job['category'].upper()} ({job['title']}) ---")
        out_dir = BASE_OUTPUT_DIR / job["category"] / job["slug"]
        
        manifest = generate_image_manifest(
            raw_prompt=job["prompt"],
            output_dir=out_dir,
            force_category=job["category"],
            use_comfy=True
        )
        
        dir_path = manifest["package_files"]["directory"]
        master_img = manifest["package_files"]["master_image"]
        sharpness = manifest["quality_assurance_metrics"]["sharpness_laplacian_variance"]
        contrast = manifest["quality_assurance_metrics"]["contrast_std"]
        palette = manifest["quality_assurance_metrics"]["dominant_palette_hex"]
        elapsed_s = manifest["metrics"]["generation_time_ms"] / 1000.0
        
        print(f"[SUCCÈS RENDU {i}/3] :")
        print(f"  • Dossier Sujet  : {dir_path}")
        print(f"  • Master Image   : {master_img}")
        print(f"  • Fichiers pack  : {len(manifest['package_files']['derived_files']) + 5} fichiers créés")
        print(f"  • Temps total    : {elapsed_s:.2f}s")
        print(f"  • Netteté Lapl.  : {sharpness}")
        print(f"  • Contraste      : {contrast}")
        print(f"  • Palette        : {palette}")
        results.append(manifest)
        
    print("\n" + "=" * 70)
    print("✨ TOUTES LES GÉNÉRATIONS HAUTE DENSITÉ ONT ÉTÉ EXÉCUTÉES AVEC SUCCÈS")
    print("=" * 70)

if __name__ == "__main__":
    main()
