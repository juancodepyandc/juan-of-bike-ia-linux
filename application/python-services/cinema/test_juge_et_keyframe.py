#!/usr/bin/env python3
"""Gardes : un juge muet n'est pas un verdict, et la keyframe part en action.

Contexte mesure sur le film du 27/07 a 22h08 :
  PROGRESS:vision_parse_fail:
  PROGRESS:char_reject:VeloRouge attempt 2 score None: pieces manquantes: left pedal
Le juge de ressemblance avait renvoye du VIDE (pas une erreur) parce qu'Ollama
ne peut pas reloger un modele de 19,6 Go pendant qu'une generation FLUX occupe
le GPU. `score None` = non juge : c'est par la qu'une reference amputee passe.

Ces tests figent :
  1. le repli vers un juge plus petit quand le principal ne repond pas ;
  2. l'absence de boucle infinie de repli ;
  3. le fait qu'une keyframe de plan decrit une action DEJA ENGAGEE — une pose
     au repos verrouille i2v a l'arret (mesure : phys 3/10, "Character
     stationary holding bike").
"""

import importlib.util
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(HERE, filename))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod


CP = _load("cinema_pipeline_juge", "cinema_pipeline.py")
SK = _load("shot_keyframe_test", "shot_keyframe.py")


class TestReplisDeVision(unittest.TestCase):

    def test_le_30b_replie_sur_le_8b(self):
        self.assertEqual(CP._vision_fallbacks("qwen3-vl:30b"), ["qwen3-vl:8b"])

    def test_le_8b_replie_sur_le_30b(self):
        self.assertEqual(CP._vision_fallbacks("qwen3-vl:8b"), ["qwen3-vl:30b"])

    def test_un_modele_ne_se_replie_jamais_sur_lui_meme(self):
        for m in ("qwen3-vl:30b", "qwen3-vl:8b"):
            self.assertNotIn(m, CP._vision_fallbacks(m))

    def test_modele_inconnu_garde_toute_la_chaine(self):
        self.assertEqual(CP._vision_fallbacks("autre:1b"),
                         ["qwen3-vl:30b", "qwen3-vl:8b"])

    def test_le_repli_ne_se_rappelle_pas_lui_meme(self):
        """allow_fallback=False coupe la recursion : sinon, N modeles muets
        declencheraient N! appels."""
        appels = []

        def faux_urlopen(req, timeout=None):
            appels.append(getattr(req, "full_url", str(req)))
            raise OSError("ollama injoignable")

        import urllib.request
        vrai = urllib.request.urlopen
        urllib.request.urlopen = faux_urlopen
        try:
            with self.assertRaises(OSError):
                CP._ollama_vision_json("p", [], model="qwen3-vl:30b",
                                       retries=0, allow_fallback=False)
        finally:
            urllib.request.urlopen = vrai
        self.assertEqual(len(appels), 1)


class TestPromptDeKeyframe(unittest.TestCase):

    def test_l_action_est_deja_engagee(self):
        p = SK.build_shot_prompt("Natsu rides a red bicycle", ", anime style")
        low = p.lower()
        self.assertIn("mid-action", low)
        self.assertIn("already underway", low)

    def test_le_style_est_toujours_appose(self):
        p = SK.build_shot_prompt("une ruelle", ", consistent hand-drawn 2D anime style")
        self.assertTrue(p.rstrip().endswith("anime style"))

    def test_le_contrat_d_action_est_repris(self):
        p = SK.build_shot_prompt("scene", ", anime style",
                                 action_contract="legs pumping on the pedals")
        self.assertIn("legs pumping on the pedals", p)

    def test_les_entites_exigent_toutes_leurs_pieces(self):
        p = SK.build_shot_prompt("scene", "", entities=["VeloRouge", "Natsu"])
        self.assertIn("VeloRouge", p)
        self.assertIn("every part present", p)

    def test_aucun_texte_dans_l_image(self):
        self.assertIn("no text", SK.build_shot_prompt("scene", "").lower())


class TestGrapheDeKeyframe(unittest.TestCase):

    def test_les_references_s_enchainent_sans_s_ecraser(self):
        """Chaque ReferenceLatent doit consommer le conditionnement precedent :
        sinon la derniere reference remplace toutes les autres."""
        wf = SK.build_workflow("p", ["a.png", "b.png"], 960, 544, 20, 1, 5.0, "x")
        refs = [k for k, v in wf.items()
                if v.get("class_type") == "ReferenceLatent"]
        self.assertEqual(len(refs), 2)
        sources = {tuple(wf[k]["inputs"]["conditioning"]) for k in refs}
        # l'un part du texte, l'autre de la reference precedente
        self.assertIn(("6", 0), sources)
        self.assertEqual(len(sources), 2)
        # le guider consomme le DERNIER maillon, pas le texte brut
        self.assertNotEqual(tuple(wf["26"]["inputs"]["positive"]), ("6", 0))

    def test_sans_reference_le_graphe_reste_valide(self):
        wf = SK.build_workflow("p", [], 960, 544, 20, 1, 5.0, "x")
        self.assertFalse([k for k, v in wf.items()
                          if v.get("class_type") == "ReferenceLatent"])
        self.assertEqual(tuple(wf["26"]["inputs"]["positive"]), ("6", 0))

    def test_le_nombre_de_references_est_borne(self):
        wf = SK.build_workflow("p", ["a.png", "b.png", "c.png", "d.png", "e.png"],
                               960, 544, 20, 1, 5.0, "x")
        refs = [k for k, v in wf.items()
                if v.get("class_type") == "ReferenceLatent"]
        self.assertEqual(len(refs), SK.MAX_REFERENCES)

    def test_le_negatif_interdit_la_derive_de_style(self):
        self.assertIn("style change", SK.NEGATIVE)
        self.assertIn("missing parts", SK.NEGATIVE)


class TestActivationKeyframeDePlan(unittest.TestCase):
    """La keyframe par plan coute une image FLUX : son declenchement doit
    etre previsible, pas devine."""

    def setUp(self):
        self._env = os.environ.pop("AURORA_SHOT_KEYFRAMES", None)

    def tearDown(self):
        os.environ.pop("AURORA_SHOT_KEYFRAMES", None)
        if self._env is not None:
            os.environ["AURORA_SHOT_KEYFRAMES"] = self._env

    def test_premium_active_par_defaut(self):
        self.assertTrue(CP.shot_keyframes_are_enabled({"quality_mode": "premium"}))

    def test_hors_premium_inactive(self):
        self.assertFalse(CP.shot_keyframes_are_enabled({"quality_mode": "auto"}))
        self.assertFalse(CP.shot_keyframes_are_enabled({}))

    def test_le_storyboard_peut_forcer(self):
        self.assertTrue(CP.shot_keyframes_are_enabled({"shot_keyframes": True}))
        self.assertFalse(CP.shot_keyframes_are_enabled(
            {"shot_keyframes": False, "quality_mode": "premium"}))

    def test_l_environnement_prime_sur_tout(self):
        os.environ["AURORA_SHOT_KEYFRAMES"] = "0"
        self.assertFalse(CP.shot_keyframes_are_enabled(
            {"quality_mode": "premium", "shot_keyframes": True}))
        os.environ["AURORA_SHOT_KEYFRAMES"] = "1"
        self.assertTrue(CP.shot_keyframes_are_enabled({"shot_keyframes": False}))


class TestEntitesDuPlan(unittest.TestCase):
    """Ne referencer que ce que le plan montre : ajouter tout le casting
    ferait apparaitre des personnages absents de la scene."""

    CASTING = {"Natsu": {}, "VeloRouge": {}, "Lucy": {}}

    def test_seules_les_entites_citees_sont_prises(self):
        got = CP._shot_entities(
            {"scene": "Natsu rides the VeloRouge down the alley"}, self.CASTING)
        self.assertEqual(set(got), {"Natsu", "VeloRouge"})
        self.assertNotIn("Lucy", got)

    def test_l_ordre_suit_le_texte(self):
        got = CP._shot_entities(
            {"scene": "The VeloRouge leans on a wall, then Natsu grabs it"},
            self.CASTING)
        self.assertEqual(got, ["VeloRouge", "Natsu"])

    def test_le_contrat_d_action_compte_aussi(self):
        got = CP._shot_entities(
            {"scene": "A wide alley", "action_contract": "Natsu pedals hard"},
            self.CASTING)
        self.assertEqual(got, ["Natsu"])

    def test_plan_sans_entite(self):
        self.assertEqual(CP._shot_entities({"scene": "An empty street"},
                                           self.CASTING), [])




class TestPorteKeyframeDePlan(unittest.TestCase):
    """Trois notes separees, pas une moyenne : une image magnifique mais AU
    REPOS verrouillerait i2v a l'arret, et une image juste mais photorealiste
    casserait la coherence d'un film anime. Une moyenne laisserait passer les
    deux."""

    def _juge(self, reponse):
        vrai = CP._ollama_vision_json
        CP._ollama_vision_json = lambda *a, **k: reponse
        try:
            return CP.validate_shot_keyframe("/dev/null", "une ruelle",
                                             "il pedale", "anime")
        finally:
            CP._ollama_vision_json = vrai

    def test_keyframe_conforme_acceptee(self):
        r = self._juge({"scene": 9, "action": 8, "style": 9, "text_present": False})
        self.assertTrue(r["ok"])
        self.assertTrue(r["graded"])

    def test_pose_figee_refusee_malgre_scene_parfaite(self):
        r = self._juge({"scene": 10, "action": 3, "style": 10, "text_present": False})
        self.assertFalse(r["ok"])
        self.assertIn("action figee", r["reason"])

    def test_derive_de_style_refusee_malgre_action_parfaite(self):
        r = self._juge({"scene": 9, "action": 9, "style": 4, "text_present": False})
        self.assertFalse(r["ok"])
        self.assertIn("style", r["reason"])

    def test_le_texte_est_signale_sans_faire_perdre_l_ancre(self):
        """Un decalque de marque de trois pixels ne doit pas coûter la keyframe :
        sans ancre, l'objet reapparait de nulle part au plan suivant — le defaut
        meme qu'on corrige. Le texte est donc signale, pas sanctionne."""
        r = self._juge({"scene": 9, "action": 9, "style": 9, "text_present": True})
        self.assertTrue(r["ok"])
        self.assertIn("texte", r["reason"])
        self.assertEqual(r["soft_faults"], ["du texte apparait dans l'image"])

    def test_un_vrai_defaut_reste_bloquant_meme_sans_texte(self):
        r = self._juge({"scene": 3, "action": 9, "style": 9, "text_present": False})
        self.assertFalse(r["ok"])

    def test_juge_muet_ne_note_pas(self):
        r = self._juge(None)
        self.assertFalse(r["graded"])
        self.assertFalse(r["ok"])

    def test_un_juge_muet_ne_bloque_pas_le_plan(self):
        """graded=False ne doit pas etre traite comme un rejet : le plan
        retombe sur l'ancrage habituel, il n'echoue pas."""
        r = self._juge(None)
        self.assertTrue(r["graded"] is False and r["ok"] is False)



class TestDepartageKeyframes(unittest.TestCase):
    """Quand deux essais sont imparfaits, il faut garder le meilleur — pas
    rien. Rendre le plan a l'ancrage habituel le renvoie souvent sur un gros
    plan de visage, d'ou l'objet qui reapparait de nulle part."""

    def test_le_rang_somme_les_trois_notes(self):
        self.assertEqual(CP._keyframe_rank(
            {"scene_score": 8, "action_score": 7, "style_score": 9}), 24)

    def test_les_notes_absentes_valent_zero(self):
        self.assertEqual(CP._keyframe_rank({}), 0)
        self.assertEqual(CP._keyframe_rank({"scene_score": None}), 0)

    def test_le_meilleur_essai_gagne(self):
        a = {"scene_score": 9, "action_score": 8, "style_score": 9}
        b = {"scene_score": 5, "action_score": 5, "style_score": 5}
        self.assertGreater(CP._keyframe_rank(a), CP._keyframe_rank(b))


class TestDepartageKeyframes(unittest.TestCase):
    """Quand deux essais sont imparfaits, il faut garder le meilleur — pas
    rien. Rendre le plan a l'ancrage habituel le renvoie souvent sur un gros
    plan de visage, d'ou l'objet qui reapparait de nulle part."""

    def test_le_rang_somme_les_trois_notes(self):
        self.assertEqual(CP._keyframe_rank(
            {"scene_score": 8, "action_score": 7, "style_score": 9}), 24)

    def test_les_notes_absentes_valent_zero(self):
        self.assertEqual(CP._keyframe_rank({}), 0)
        self.assertEqual(CP._keyframe_rank({"scene_score": None}), 0)

    def test_le_meilleur_essai_gagne(self):
        a = {"scene_score": 9, "action_score": 8, "style_score": 9}
        b = {"scene_score": 5, "action_score": 5, "style_score": 5}
        self.assertGreater(CP._keyframe_rank(a), CP._keyframe_rank(b))




class TestPorteAvantLipsync(unittest.TestCase):
    """Un plan dialogue en gros plan produit d'abord une video FIXE, que S2V
    anime ensuite avec l'audio. Noter son action a ce stade, c'est noter le
    mauvais artefact — mesure : scene 10, phys 10, identite 10, act 6, moyenne
    9,0, et TOUT le film echouait."""

    def test_un_plan_parfait_ailleurs_ne_doit_pas_echouer_sur_l_action(self):
        q = {"score": 10, "physics_score": 10, "identity_score": 10,
             "action_score": 6}
        self.assertFalse(CP.shot_quality_ok(q, "premium"))
        neutre = dict(q)
        neutre["action_score"] = int(round((10 + 10 + 10) / 3))
        self.assertTrue(CP.shot_quality_ok(neutre, "premium"))

    def test_un_plan_reellement_mauvais_echoue_toujours(self):
        self.assertFalse(CP.shot_quality_ok(
            {"score": 4, "physics_score": 3, "identity_score": 5,
             "action_score": 4}, "premium"))

    def test_neutraliser_ne_veut_pas_dire_annuler(self):
        """action_score=None vaudrait 0 via _score() : pire que le defaut
        qu'on refuse de sanctionner."""
        self.assertEqual(CP._score(None), 0)
        q = {"score": 10, "physics_score": 10, "identity_score": 10,
             "action_score": None}
        self.assertFalse(CP.shot_quality_ok(q, "premium"))


class TestMesureAmplitude(unittest.TestCase):
    """Contrepartie de la porte assouplie : le mouvement DOIT etre verifie
    apres le lipsync, sinon une photo muette passerait sans que rien ne le
    dise. Seuil calibre sur des fichiers reels : 0,58 = plan reste fige,
    2,5 = sortie S2V qui anime la bouche, 11 a 26 = plan en mouvement."""

    def test_fichier_absent_rend_none_sans_lever(self):
        self.assertIsNone(CP._mesure_amplitude("/tmp/inexistant_aurora.mp4"))

    def test_le_seuil_separe_les_valeurs_mesurees(self):
        seuil = 1.0
        self.assertLess(0.58, seuil)   # plan reste fige
        self.assertGreater(2.5, seuil)  # S2V anime vraiment
        self.assertGreater(11.7, seuil)  # plan genere




class TestDefautsDifferesAvantLipsync(unittest.TestCase):
    """Neutraliser la NOTE d'action ne suffisait pas : le juge ecrit AUSSI le
    defaut en toutes lettres dans `issues`, et has_blocking_visual_issue bloque
    sur ces phrases avant de regarder les notes. Charge reelle du plan 1 :
      'No visible mouth or head movement between frames'
      'Scarf appears static with no sway'
      'Action does not show continuous speech mechanism'
    Trois formulations du meme constat, exact et ATTENDU sur une image que S2V
    doit encore animer."""

    MOUVEMENT = ("movement", "motion", "static", "sway", "still", "frozen",
                 "speech mechanism", "mouth", "lip", "animation", "moving")

    def _differer(self, issues):
        return ([i for i in issues
                 if not any(t in i.lower() for t in self.MOUVEMENT)],
                [i for i in issues
                 if any(t in i.lower() for t in self.MOUVEMENT)])

    def test_la_charge_reelle_du_plan_1_passe_apres_differe(self):
        q = {"score": 7, "physics_score": 10, "identity_score": 10,
             "action_score": 6,
             "issues": ["No visible mouth or head movement between frames",
                        "Scarf appears static with no sway",
                        "Action does not show continuous speech mechanism"]}
        self.assertTrue(CP.has_blocking_visual_issue(q))
        gardes, differes = self._differer(q["issues"])
        self.assertEqual(gardes, [])
        self.assertEqual(len(differes), 3)
        corrige = dict(q, issues=gardes,
                       action_score=int(round((7 + 10 + 10) / 3)))
        self.assertFalse(CP.has_blocking_visual_issue(corrige))
        self.assertTrue(CP.shot_quality_ok(corrige, "premium"))

    def test_un_defaut_qui_ne_depend_pas_du_lipsync_reste_bloquant(self):
        """Le differe ne doit pas devenir une amnistie generale."""
        issues = ["No visible mouth or head movement between frames",
                  "The red bicycle is missing from the frame"]
        gardes, differes = self._differer(issues)
        self.assertEqual(gardes, ["The red bicycle is missing from the frame"])
        self.assertTrue(CP.has_blocking_visual_issue({"issues": gardes}))

    def test_un_plan_sans_dialogue_n_est_pas_concerne(self):
        """Sur un plan genere, l'immobilite est un vrai defaut : elle doit
        continuer a bloquer."""
        q = {"score": 8, "physics_score": 8, "identity_score": 8,
             "action_score": 3,
             "issues": ["No visible movement between frames"]}
        self.assertTrue(CP.has_blocking_visual_issue(q))
        self.assertFalse(CP.shot_quality_ok(q, "premium"))




class TestPortePostAudio(unittest.TestCase):
    """Mesure sur le plan 3 : porte pre-audio scene=5 phys=None id=None act=None
    (juge partiel -> "non mesure" -> laisse passer SANS consommer de reprise),
    puis post-audio scene=5 phys=8 id=9 act=7 = 7,2/10 -> tout le film echoue.
    Les images etaient identiques, et ce plan n'a AUCUN dialogue : rien n'a ete
    muxe. Une porte post-audio sur un plan muet ne peut sanctionner que
    l'instabilite du juge."""

    def test_un_verdict_partiel_n_est_pas_mesure(self):
        partiel = {"score": 5, "physics_score": None,
                   "identity_score": None, "action_score": None}
        self.assertFalse(CP.shot_quality_is_measured(partiel))

    def test_un_verdict_complet_est_mesure(self):
        complet = {"score": 5, "physics_score": 8,
                   "identity_score": 9, "action_score": 7}
        self.assertTrue(CP.shot_quality_is_measured(complet))

    def test_la_garde_s_arme_sur_un_plan_muet(self):
        """Sans dialogue ni lipsync, aucun audio n'est ajoute : la garde doit
        s'armer meme si la 1re notation etait partielle."""
        for dialogue, needs_lipsync, attendu in (
                (None, False, True), ("", False, True),
                ("Salut", False, False), (None, True, False)):
            with self.subTest(dialogue=dialogue, lipsync=needs_lipsync):
                self.assertEqual(
                    not bool(dialogue) and not bool(needs_lipsync), attendu)

    def test_l_ancienne_garde_ne_couvrait_pas_le_verdict_partiel(self):
        """Regression : `accepted_qa and shot_quality_ok(...)` valait False sur
        un verdict partiel, donc la protection tombait exactement quand le juge
        etait le plus instable."""
        partiel = {"score": 5, "physics_score": None,
                   "identity_score": None, "action_score": None}
        self.assertFalse(CP.shot_quality_ok(partiel, "premium"))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestErreurUtile(unittest.TestCase):
    """Le film a rapporte « musicgen failed: 6 [00:01<00:00, 628.88it/s] ».
    Ce n'est pas une erreur, c'est un fragment de barre tqdm : le code citait
    les 300 DERNIERS caracteres de stderr, or tqdm y ecrit sa progression. La
    vraie exception, situee plus haut, etait invisible."""

    BARRE = ("Loading weights:  95%|=====| 944/996 [00:01<00:00, 436.64it/s]\n"
             "Loading weights: 100%|=====| 996/996 [00:01<00:00, 628.88it/s]")

    def test_la_vraie_exception_prime_sur_la_barre(self):
        flux = self.BARRE + "\ntorch.OutOfMemoryError: CUDA out of memory."
        msg = CP._erreur_utile(flux, "")
        self.assertIn("CUDA out of memory", msg)
        self.assertNotIn("it/s", msg)

    def test_une_barre_seule_ne_fait_pas_passer_pour_une_erreur(self):
        msg = CP._erreur_utile(self.BARRE, "")
        self.assertTrue(msg)

    def test_les_lignes_de_progression_sont_ecartees(self):
        flux = self.BARRE + "\nRuntimeError: model not found"
        self.assertNotIn("436.64it/s", CP._erreur_utile(flux, ""))

    def test_flux_vide(self):
        self.assertEqual(CP._erreur_utile("", ""), "echec sans message")

    def test_les_retours_chariot_sont_traites_comme_des_lignes(self):
        flux = "avance 10%\ravance 50%\rValueError: mauvaise dimension"
        self.assertIn("ValueError", CP._erreur_utile(flux, ""))


class TestAmbianceParLieu(unittest.TestCase):
    """Un plan n'est presque jamais silencieux. Le silence total s'entend comme
    un defaut de production — c'est ce qui fait qu'une video « sonne IA » meme
    quand l'image tient."""

    def test_chaque_famille_de_lieu_a_son_fond(self):
        cas = {
            "ruelle_pierre": "stone street",
            "plage_sud": "seaside",
            "foret_nord": "forest",
            "marche_central": "market",
        }
        for lieu, attendu in cas.items():
            with self.subTest(lieu=lieu):
                self.assertIn(attendu, CP.prompt_ambiance(lieu, ""))

    def test_un_lieu_inconnu_recoit_un_fond_neutre(self):
        p = CP.prompt_ambiance("zzz_inconnu", "")
        self.assertIn("neutral", p)

    def test_l_ambiance_n_ajoute_jamais_de_musique(self):
        """La musique est une piste SEPAREE, avec son propre volume. Une
        ambiance qui contient de la musique doublerait la bande son."""
        for lieu in ("ruelle", "plage", "foret", "marche", "chambre", "inconnu"):
            with self.subTest(lieu=lieu):
                self.assertIn("no music", CP.prompt_ambiance(lieu, ""))

    def test_la_scene_compte_autant_que_le_lieu(self):
        p = CP.prompt_ambiance("", "heavy rain over the rooftops")
        self.assertIn("rain", p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
