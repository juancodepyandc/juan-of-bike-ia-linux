"""Référence FLUX.2 conditionnée par plusieurs images : une chaîne par image, sur le positif ET le négatif.

Run du 15/11/2026, « Zig et Sharko en version réaliste : Zig la hyène qui court et Sharko le requin
qui nage » : les six rendus FLUX n'avaient ni LoadImage ni ReferenceLatent dans leurs métadonnées,
l'identité venait du texte seul. Le mode multi-références de `flux_reference_synth` reprend la
chaîne de l'interface (`createFlux2Workflow`, `src/utils/fluxWorkflow.ts`) : LoadImage →
ImageScaleToTotalPixels → VAEEncode → ReferenceLatent accroché aux nœuds 6 et 33, au départ d'un
EmptyFlux2LatentImage avec Flux2Scheduler. Le graphe mono-référence historique est figé tel que le
produisait le code avant ce mode (commit ee83436). Aucun rendu réel : le transport ComfyUI est simulé
et aucune requête ne quitte le processus.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "application" / "python-services"))
import flux_reference_synth as frs  # noqa: E402

# Adresse sans service : même si un faux était oublié, rien n'atteindrait le ComfyUI réel du poste.
COMFY_FERME = "http://127.0.0.1:9"

# Négatif historique du nœud 33, recopié du code d'avant le mode multi-références.
NEGATIF_HISTORIQUE = (
    "cropped, cut off, out of frame, partial view, close-up, truncated body, missing limbs, deformed hands, "
    "extra fingers, malformed limbs, blurry, low quality, unwanted background crowd, random pedestrians, "
    "deformed background bystanders, out-of-scale giant figures, distorted crowd, blurry humanoid blobs, "
    "random text, misspelled text, gibberish lettering, corrupted words, watermark, signature, duplicate "
    "subject, split panels, multi-panel layout, collage, cluttered background"
)

# Graphes produits par le code d'avant (prompt "P", 1024×1408, 20 pas, graine 7, sans adaptateur).
# Les noms de poids et le périphérique de l'encodeur viennent de variables d'environnement
# (AURORA_FLUX_*), et le chargeur du nœud 12 dépend du format du poids : ils sont retirés avant
# comparaison et contrôlés à part.
_COMMUN = {
    "10": ["VAELoader", {}], "11": ["CLIPLoader", {"type": "flux2"}], "12": ["<chargeur_unet>", {}],
    "33": ["CLIPTextEncode", {"clip": ["11", 0], "text": "<negatif>"}],
    "41": ["KSamplerSelect", {"sampler_name": "euler"}], "42": ["RandomNoise", {"noise_seed": 7}],
    "6": ["CLIPTextEncode", {"clip": ["11", 0], "text": "P"}],
    "8": ["VAEDecode", {"samples": ["31", 0], "vae": ["10", 0]}],
    "9": ["SaveImage", {"filename_prefix": "aurora_x", "images": ["8", 0]}],
    "27": ["EmptyFlux2LatentImage", {"batch_size": 1, "height": 1408, "width": 1024}],
}
INSTANTANE_HISTORIQUE = {
    "texte": ({}, dict(_COMMUN, **{
        "26": ["CFGGuider", {"cfg": 5.0, "model": ["12", 0], "negative": ["33", 0], "positive": ["6", 0]}],
        "31": ["SamplerCustomAdvanced", {"guider": ["26", 0], "latent_image": ["27", 0], "noise": ["42", 0],
                                         "sampler": ["41", 0], "sigmas": ["40", 0]}],
        "40": ["Flux2Scheduler", {"height": 1408, "steps": 20, "width": 1024}],
    })),
    "verrou_0_08": ({"reference_comfy_name": "ref.png", "reference_denoise": 0.08}, dict(_COMMUN, **{
        "26": ["CFGGuider", {"cfg": 1.2, "model": ["12", 0], "negative": ["54", 0], "positive": ["53", 0]}],
        "31": ["SamplerCustomAdvanced", {"guider": ["26", 0], "latent_image": ["52", 0], "noise": ["42", 0],
                                         "sampler": ["41", 0], "sigmas": ["40", 0]}],
        "40": ["BasicScheduler", {"denoise": 0.08, "model": ["12", 0], "scheduler": "simple", "steps": 20}],
        "50": ["LoadImage", {"image": "ref.png"}],
        "51": ["ImageScale", {"crop": "disabled", "height": 1408, "image": ["50", 0], "upscale_method": "lanczos",
                              "width": 1024}],
        "52": ["VAEEncode", {"pixels": ["51", 0], "vae": ["10", 0]}],
        "53": ["ReferenceLatent", {"conditioning": ["6", 0], "latent": ["52", 0]}],
        "54": ["ReferenceLatent", {"conditioning": ["33", 0], "latent": ["52", 0]}],
    })),
    "restyle_0_74": ({"reference_comfy_name": "ref.png", "reference_denoise": 0.74}, dict(_COMMUN, **{
        "26": ["CFGGuider", {"cfg": 3.5, "model": ["12", 0], "negative": ["33", 0], "positive": ["53", 0]}],
        "31": ["SamplerCustomAdvanced", {"guider": ["26", 0], "latent_image": ["27", 0], "noise": ["42", 0],
                                         "sampler": ["41", 0], "sigmas": ["40", 0]}],
        "40": ["Flux2Scheduler", {"height": 1408, "steps": 20, "width": 1024}],
        "50": ["LoadImage", {"image": "ref.png"}],
        "51": ["ImageScale", {"crop": "center", "height": 320, "image": ["50", 0], "upscale_method": "lanczos",
                              "width": 320}],
        "52": ["VAEEncode", {"pixels": ["51", 0], "vae": ["10", 0]}],
        "53": ["ReferenceLatent", {"conditioning": ["6", 0], "latent": ["52", 0]}],
    })),
}


def normaliser(graphe: dict) -> dict:
    sortie = {}
    for cle, noeud in graphe.items():
        entrees = {k: v for k, v in noeud["inputs"].items()
                   if k not in ("clip_name", "unet_name", "vae_name", "weight_dtype", "device")}
        if cle == "33":
            entrees["text"] = "<negatif>"
        sortie[cle] = ["<chargeur_unet>" if cle == "12" else noeud["class_type"], entrees]
    return sortie


def graphe(**options) -> dict:
    return frs.build_workflow("P", width=1024, height=1408, steps=20, seed=7, filename_prefix="aurora_x",
                              trained_adapter=False, **options)


def de_classe(g: dict, classe: str) -> dict:
    return {cle: noeud for cle, noeud in g.items() if noeud["class_type"] == classe}


def chaine(g: dict, depart: list, texte: str) -> list[tuple[str, str]]:
    """Remonte le conditionnement depuis le guide jusqu'au nœud texte ; rend (image, nœud VAEEncode)
    dans l'ordre où les références sont appliquées — l'ordre « image 1, image 2… » du modèle."""
    vu, lien = [], depart
    while lien[0] != texte:
        noeud = g[lien[0]]
        assert noeud["class_type"] == "ReferenceLatent", noeud
        code = g[noeud["inputs"]["latent"][0]]
        assert code["class_type"] == "VAEEncode" and code["inputs"]["vae"] == ["10", 0], code
        echelle = g[code["inputs"]["pixels"][0]]
        assert echelle["class_type"] == "ImageScaleToTotalPixels", echelle
        charge = g[echelle["inputs"]["image"][0]]
        assert charge["class_type"] == "LoadImage", charge
        vu.append((charge["inputs"]["image"], noeud["inputs"]["latent"][0]))
        lien = noeud["inputs"]["conditioning"]
    return vu[::-1]


class GrapheMultiReferences(unittest.TestCase):
    def test_trois_references_donnent_trois_chaines_sur_le_positif_et_le_negatif(self):
        g = graphe(reference_comfy_names=["a.png", "b.png", "c.png"])
        self.assertEqual(len(de_classe(g, "LoadImage")), 3)
        self.assertEqual(len(de_classe(g, "ImageScaleToTotalPixels")), 3)
        self.assertEqual(len(de_classe(g, "VAEEncode")), 3)
        self.assertEqual(len(de_classe(g, "ReferenceLatent")), 6)
        guide = g["26"]["inputs"]
        positif, negatif = chaine(g, guide["positive"], "6"), chaine(g, guide["negative"], "33")
        self.assertEqual([image for image, _ in positif], ["a.png", "b.png", "c.png"])
        # Même image ET même latent encodé des deux côtés du CFG : l'écart ne porte que le texte.
        self.assertEqual(positif, negatif)
        for noeud in de_classe(g, "ImageScaleToTotalPixels").values():
            self.assertEqual(noeud["inputs"]["megapixels"], 0.5)
            self.assertEqual(noeud["inputs"]["upscale_method"], "lanczos")
            self.assertEqual(noeud["inputs"]["resolution_steps"], 1)

    def test_le_mode_multi_ne_recadre_pas_a_320_n_etire_pas_et_ne_verrouille_pas(self):
        g = graphe(reference_comfy_names=["a.png", "b.png"])
        classes = {noeud["class_type"] for noeud in g.values()}
        self.assertNotIn("ImageScale", classes)
        self.assertNotIn("BasicScheduler", classes)
        self.assertEqual(g["40"]["class_type"], "Flux2Scheduler")
        self.assertEqual(g[g["31"]["inputs"]["latent_image"][0]]["class_type"], "EmptyFlux2LatentImage")
        self.assertEqual(g["26"]["inputs"]["cfg"], 5.0)
        for noeud in g.values():
            self.assertNotIn("denoise", noeud["inputs"])
            self.assertNotIn("crop", noeud["inputs"])
            self.assertNotIn(320, list(noeud["inputs"].values()))

    def test_la_taille_des_references_est_celle_demandee(self):
        g = graphe(reference_comfy_names=["a.png", "b.png"], reference_megapixels=0.25)
        self.assertEqual({n["inputs"]["megapixels"] for n in de_classe(g, "ImageScaleToTotalPixels").values()}, {0.25})

    def test_une_entree_qui_retirerait_l_identite_des_pixels_est_refusee(self):
        for options in ({"reference_comfy_names": []},
                        {"reference_comfy_names": ["a.png", ""]},
                        {"reference_comfy_names": ["a.png", "a.png"]},
                        {"reference_comfy_names": ["a.png"], "reference_comfy_name": "b.png"},
                        {"reference_comfy_names": ["a.png"], "reference_megapixels": 0},
                        {"reference_comfy_names": ["a.png"], "reference_megapixels": 20}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                graphe(**options)

    def test_un_negatif_fourni_remplace_le_generique(self):
        self.assertEqual(frs.NEGATIF_PAR_DEFAUT, NEGATIF_HISTORIQUE)
        self.assertEqual(graphe()["33"]["inputs"]["text"], NEGATIF_HISTORIQUE)
        self.assertEqual(graphe(negative_prompt="clothing, cartoon")["33"]["inputs"]["text"], "clothing, cartoon")
        multi = graphe(reference_comfy_names=["a.png"], negative_prompt="clothing, cartoon")
        self.assertEqual(multi["33"]["inputs"]["text"], "clothing, cartoon")


class GrapheMonoReferenceHistorique(unittest.TestCase):
    def test_le_graphe_mono_reference_est_celui_d_avant(self):
        chargeur = "UnetLoaderGGUF" if str(frs.DEFAULT_UNET).lower().endswith(".gguf") else "UNETLoader"
        for nom, (options, attendu) in INSTANTANE_HISTORIQUE.items():
            with self.subTest(cas=nom):
                g = graphe(**options)
                self.assertEqual(normaliser(g), attendu)
                self.assertEqual(g["12"]["class_type"], chargeur)
                self.assertEqual(g["33"]["inputs"]["text"], NEGATIF_HISTORIQUE)
                self.assertEqual({cle: n["class_type"] for cle, n in g.items()},
                                 {cle: (chargeur if cle == "12" else n[0]) for cle, n in attendu.items()})


def png(chemin: Path, taille=(40, 60), fond=(255, 0, 0, 0), sujet=(40, 90, 160, 255)) -> Path:
    """Découpe synthétique : sujet opaque au centre, fond transparent dont le RGB caché est `fond`
    (rouge par défaut : un alpha posé par `putalpha` garde la photo d'origine sous la transparence)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    pixels = np.zeros((taille[1], taille[0], 4), np.uint8)
    pixels[:, :] = fond
    pixels[10:50, 10:30] = sujet
    pixels[30, 5] = (0, 0, 0, 128)
    Image.fromarray(pixels, "RGBA").save(chemin)
    return chemin


class FauxComfy:
    """Transport ComfyUI simulé : téléversements et graphes reçus, réponses d'un rendu réussi."""

    def __init__(self, refuser_rang: int | None = None):
        self.televerses: list[Path] = []
        self.graphes: list[dict] = []
        self.refuser_rang = refuser_rang

    def televerser(self, chemin, comfy_base=frs.COMFY_BASE):
        self.televerses.append(Path(chemin))
        if self.refuser_rang == len(self.televerses):
            return None
        return "comfy_%d_%s" % (len(self.televerses), Path(chemin).name)

    def poster(self, workflow, comfy_base=frs.COMFY_BASE):
        self.graphes.append(workflow)
        return "travail-simule"

    @staticmethod
    def ecrire(url, destination):
        Path(destination).parent.mkdir(parents=True, exist_ok=True)
        Path(destination).write_bytes(b"png-simule")
        return 10

    @contextlib.contextmanager
    def actif(self):
        construire = frs.build_workflow

        def sans_adaptateur(*args, **kwargs):
            # L'adaptateur renforcé lit l'état du poste (auto_rl/state) : hors sujet ici.
            return construire(*args, **dict(kwargs, trained_adapter=False))

        def hors_reseau(*args, **kwargs):
            raise OSError("aucun reseau dans les tests")

        with contextlib.ExitStack() as pile:
            pile.enter_context(patch.object(frs, "upload_reference_image", self.televerser))
            pile.enter_context(patch.object(frs, "post_prompt", self.poster))
            pile.enter_context(patch.object(frs, "poll_history", lambda pid, **_: {"status": {"completed": True}}))
            pile.enter_context(patch.object(frs, "output_path_from_history", lambda entree, base=None: "http://simule/view"))
            pile.enter_context(patch.object(frs, "fetch_to", self.ecrire))
            pile.enter_context(patch.object(frs, "build_workflow", sans_adaptateur))
            pile.enter_context(patch("urllib.request.urlopen", hors_reseau))
            yield self


class SynthMultiReferences(unittest.TestCase):
    def test_chaque_image_est_preparee_televersee_dans_l_ordre_puis_chainee(self):
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            # Deux ancres de sujets différents portent le même nom sur le disque.
            sources = [png(racine / "sujet_a" / "ancre_1.png"), png(racine / "sujet_b" / "ancre_1.png"),
                       png(racine / "sujet_c" / "medoide.png")]
            faux = FauxComfy()
            with faux.actif():
                resultat = frs.synth("P", "run_t", output_dir=racine / "sortie", comfy_base=COMFY_FERME,
                                     reference_images=sources, negative_prompt="N")
            self.assertTrue(resultat["ok"], resultat)
            self.assertEqual([p.name for p in faux.televerses], ["run_t_ancre_1.png", "run_t_ancre_2.png",
                                                                 "run_t_ancre_3.png"])
            noms = [entree["comfy_name"] for entree in resultat["references"]]
            self.assertEqual(len(set(noms)), 3)
            self.assertEqual([entree["source"] for entree in resultat["references"]], [str(s) for s in sources])
            g = faux.graphes[0]
            self.assertEqual([image for image, _ in chaine(g, g["26"]["inputs"]["positive"], "6")], noms)
            self.assertEqual([image for image, _ in chaine(g, g["26"]["inputs"]["negative"], "33")], noms)
            self.assertEqual(g["33"]["inputs"]["text"], "N")
            self.assertEqual(resultat["negative_prompt"], "N")
            self.assertEqual(resultat["reference_megapixels"], 0.5)

    def test_aucun_rendu_quand_une_reference_manque_ou_est_refusee(self):
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            a, b = png(racine / "a.png"), png(racine / "b.png")
            faux = FauxComfy(refuser_rang=2)
            with faux.actif():
                refusee = frs.synth("P", "run_r", output_dir=racine, comfy_base=COMFY_FERME, reference_images=[a, b])
            self.assertFalse(refusee["ok"])
            self.assertIn(str(b), refusee["error"])
            self.assertEqual(faux.graphes, [])
            faux = FauxComfy()
            with faux.actif():
                absente = frs.synth("P", "run_r", output_dir=racine, comfy_base=COMFY_FERME,
                                    reference_images=[a, racine / "absente.png"])
                vide = frs.synth("P", "run_r", output_dir=racine, comfy_base=COMFY_FERME, reference_images=[])
                double = frs.synth("P", "run_r", output_dir=racine, comfy_base=COMFY_FERME,
                                   reference_image=a, reference_images=[b])
            for res in (absente, vide, double):
                self.assertFalse(res["ok"], res)
            self.assertIn("absente.png", absente["error"])
            self.assertEqual(faux.graphes, [])

    def test_le_chemin_mono_reference_reste_celui_d_avant(self):
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            source = png(racine / "ref.png")
            faux = FauxComfy()
            with faux.actif():
                resultat = frs.synth("P", "run_m", output_dir=racine, comfy_base=COMFY_FERME, width=1024,
                                     height=1408, steps=20, seed=7, reference_image=source)
            self.assertTrue(resultat["ok"], resultat)
            # La source est téléversée telle quelle, sans copie préparée ni clé nouvelle au résultat.
            self.assertEqual(faux.televerses, [source])
            self.assertNotIn("references", resultat)
            self.assertNotIn("negative_prompt", resultat)
            attendu = frs.build_workflow("P", width=1024, height=1408, steps=20, seed=7,
                                         filename_prefix="aurora_run_m", trained_adapter=False,
                                         reference_comfy_name="comfy_1_ref.png", reference_denoise=0.08)
            self.assertEqual(faux.graphes[0], attendu)

    def test_la_ligne_de_commande_refuse_les_references_en_multivue(self):
        argv = ["flux_reference_synth.py", "--prompt", "P", "--run-id", "x", "--multi-view",
                "--reference-image", "a.png"]
        with patch.object(sys, "argv", argv), patch.object(frs, "synth_multiview") as multivue, \
                contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            frs.main()
        multivue.assert_not_called()


class PreparationDesReferences(unittest.TestCase):
    def test_une_decoupe_transparente_est_aplatie_sur_le_fond_neutre_sans_etirement(self):
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            preparee = frs.preparer_reference(png(racine / "decoupe.png"), racine / "envoyee.png")
            self.assertTrue(preparee["aplatie"])
            self.assertEqual(preparee["taille"], [40, 60])
            with Image.open(preparee["envoyee"]) as image:
                self.assertEqual(image.mode, "RGB")
                pixels = np.asarray(image)
            # Le rouge caché sous l'alpha nul ne doit pas atteindre FLUX.
            self.assertEqual(tuple(pixels[0, 0]), frs.FOND_REFERENCE)
            self.assertEqual(tuple(pixels[20, 20]), (40, 90, 160))
            self.assertTrue(all(abs(int(c) - 127) <= 1 for c in pixels[30, 5]))

    def test_une_image_opaque_est_envoyee_sans_retouche(self):
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            source = racine / "opaque.png"
            pixels = np.random.default_rng(3).integers(0, 255, (24, 32, 3), dtype=np.uint8)
            Image.fromarray(pixels, "RGB").save(source)
            preparee = frs.preparer_reference(source, racine / "envoyee.png")
            self.assertFalse(preparee["aplatie"])
            with Image.open(preparee["envoyee"]) as image:
                self.assertTrue(np.array_equal(np.asarray(image), pixels))

    def test_un_televersement_qui_rendrait_deux_fois_le_meme_nom_est_refuse(self):
        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            sources = [png(racine / "a.png"), png(racine / "b.png")]
            with self.assertRaises(frs.ReferenceIndisponible) as refus:
                frs.televerser_references(sources, dossier=racine, prefixe="run",
                                          televerser=lambda chemin, base: "meme_nom.png")
            self.assertEqual(len(refus.exception.details), 2)


if __name__ == "__main__":
    unittest.main()
