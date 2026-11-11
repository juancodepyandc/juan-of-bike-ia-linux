"""Domain exercise families: business maths, engineering, prompt understanding,
document extraction, program tracing and French format obedience.

Same contract as :mod:`generators`: every item carries a reference target and an
executable grader, and exam surface forms never appear in training.
"""
from __future__ import annotations

import contextlib
import io
import json
import math

from .generators import _exam, _json, family

_FINAL = {"fr": "Réponse finale : {value}", "en": "Final answer: {value}"}


def _num(value, digits=2):
    text = f"{round(value, digits):.{digits}f}"
    return text


def _numeric(question, steps, value, digits=2, abs_tol=None, lang="fr", tokens=360):
    target = "\n".join(steps + [_FINAL[lang].format(value=_num(value, digits))])
    return {"messages": [{"role": "user", "content": question}], "target": target, "lang": lang,
            "grader": {"type": "numeric", "answer": _num(value, digits), "rel_tol": 1e-6,
                       "abs_tol": abs_tol if abs_tol is not None else 0.6 * 10 ** -digits},
            "max_new_tokens": tokens}


_ASK = {
    "train": ["{body} Donne le calcul puis termine par « Réponse finale : <nombre> » ({unit}, arrondi à {digits} décimales, point décimal, sans séparateur de milliers).",
              "{body} Montre les étapes, puis écris la dernière ligne sous la forme « Réponse finale : <nombre> » en {unit}, {digits} décimales."],
    "exam": ["{body} Explique brièvement ton raisonnement et conclus par une ligne « Réponse finale : <nombre> » (valeur en {unit}, {digits} chiffres après le point).",
             "{body} Détaille le calcul. La dernière ligne doit être exactement de la forme « Réponse finale : <nombre> », exprimée en {unit} avec {digits} décimales."],
}


def _contract(text):
    """French elisions: ``de un`` -> ``d'un``."""
    return text.replace(" de un", " d'un").replace(" de une", " d'une")


def _ask(rng, role, body, unit, digits=2):
    return rng.choice(_ASK["exam" if _exam(role) else "train"]).format(body=_contract(body), unit=unit, digits=digits)


# --- business.fin_math -----------------------------------------------------

_FIRMS = {"train": ["une boulangerie", "un atelier de réparation de vélos", "une librairie", "un studio de design",
                    "une menuiserie", "un magasin de pièces détachées"],
          "exam": ["une brasserie artisanale", "un cabinet d'architecture", "une ferme maraîchère",
                   "un atelier d'impression 3D", "une agence de voyages", "un garage automobile"]}


@family("business.fin_math", "business", ("tva", "marge", "interets_composes", "cagr", "van", "seuil_rentabilite",
                                          "drawdown", "mensualite", "esperance"))
def _fin_math(rng, role, subskill):
    firm = rng.choice(_FIRMS["exam" if _exam(role) else "train"])
    if subskill == "tva":
        rate = rng.choice([5.5, 10, 20])
        if rng.random() < 0.5:
            ht = round(rng.uniform(20, 4000), 2)
            value = ht * (1 + rate / 100)
            return _numeric(_ask(rng, role, f"Dans {firm}, un article est vendu {_num(ht)} € hors taxes avec une TVA de {rate} %. Quel est le prix TTC ?", "euros"),
                            [f"Prix TTC = HT × (1 + taux) = {_num(ht)} × {1 + rate / 100:.3f} = {_num(value)}"], value)
        ttc = round(rng.uniform(20, 4000), 2)
        value = ttc / (1 + rate / 100)
        return _numeric(_ask(rng, role, f"Dans {firm}, un article coûte {_num(ttc)} € TTC, TVA de {rate} % incluse. Quel est le prix hors taxes ?", "euros"),
                        [f"Prix HT = TTC / (1 + taux) = {_num(ttc)} / {1 + rate / 100:.3f} = {_num(value)}"], value)
    if subskill == "marge":
        cost = round(rng.uniform(5, 900), 2)
        price = round(cost * rng.uniform(1.1, 2.8), 2)
        if rng.random() < 0.5:
            value = (price - cost) / cost * 100
            return _numeric(_ask(rng, role, f"{firm.capitalize()} achète un produit {_num(cost)} € et le revend {_num(price)} € hors taxes. Quel est le taux de marge (marge rapportée au coût d'achat) ?", "pourcentage"),
                            [f"Marge = {_num(price)} − {_num(cost)} = {_num(price - cost)}",
                             f"Taux de marge = marge / coût × 100 = {_num(price - cost)} / {_num(cost)} × 100 = {_num(value)}"], value)
        value = (price - cost) / price * 100
        return _numeric(_ask(rng, role, f"{firm.capitalize()} achète un produit {_num(cost)} € et le revend {_num(price)} € hors taxes. Quel est le taux de marque (marge rapportée au prix de vente) ?", "pourcentage"),
                        [f"Marge = {_num(price)} − {_num(cost)} = {_num(price - cost)}",
                         f"Taux de marque = marge / prix de vente × 100 = {_num(price - cost)} / {_num(price)} × 100 = {_num(value)}"], value)
    if subskill == "interets_composes":
        capital, rate, years = rng.randrange(500, 50000, 100), rng.choice([1.5, 2, 2.5, 3, 4, 5, 6.5]), rng.randint(2, 12)
        value = capital * (1 + rate / 100) ** years
        return _numeric(_ask(rng, role, f"{firm.capitalize()} place {capital} € à {rate} % par an, intérêts composés annuellement, pendant {years} ans. Quel capital obtient-elle à la fin ?", "euros"),
                        [f"Capital final = C × (1 + t)^n = {capital} × {1 + rate / 100:.3f}^{years}",
                         f"{1 + rate / 100:.3f}^{years} = {(1 + rate / 100) ** years:.6f}", f"Capital final = {_num(value)}"], value)
    if subskill == "cagr":
        start, years = rng.randrange(20000, 400000, 1000), rng.randint(2, 8)
        end = round(start * rng.uniform(0.7, 2.4), -2)
        value = ((end / start) ** (1 / years) - 1) * 100
        return _numeric(_ask(rng, role, f"Le chiffre d'affaires de {firm} passe de {start} € à {int(end)} € en {years} ans. Quel est le taux de croissance annuel moyen (TCAM) ?", "pourcentage"),
                        [f"TCAM = (Vf / Vi)^(1/n) − 1 = ({int(end)} / {start})^(1/{years}) − 1",
                         f"Rapport = {end / start:.6f} ; racine {years}e = {(end / start) ** (1 / years):.6f}", f"TCAM = {_num(value)} %"], value)
    if subskill == "van":
        invest, rate = rng.randrange(5000, 80000, 500), rng.choice([4, 5, 6, 8, 10])
        flows = [rng.randrange(1000, 40000, 500) for _ in range(rng.randint(3, 4))]
        terms = [flow / (1 + rate / 100) ** (t + 1) for t, flow in enumerate(flows)]
        value = sum(terms) - invest
        return _numeric(_ask(rng, role, f"{firm.capitalize()} investit {invest} € aujourd'hui et attend des flux nets de {', '.join(str(f) + ' €' for f in flows)} à la fin de chacune des {len(flows)} années suivantes. Avec un taux d'actualisation de {rate} %, quelle est la valeur actuelle nette ?", "euros"),
                        [f"Flux actualisé année {t + 1} = {flow} / {1 + rate / 100:.2f}^{t + 1} = {_num(term)}" for t, (flow, term) in enumerate(zip(flows, terms))]
                        + [f"Somme des flux actualisés = {_num(sum(terms))}", f"VAN = {_num(sum(terms))} − {invest} = {_num(value)}"], value, abs_tol=0.02, tokens=460)
    if subskill == "seuil_rentabilite":
        fixed, price = rng.randrange(2000, 90000, 500), round(rng.uniform(8, 400), 2)
        variable = round(price * rng.uniform(0.25, 0.8), 2)
        rate = (price - variable) / price
        value = fixed / rate
        return _numeric(_ask(rng, role, f"{firm.capitalize()} supporte {fixed} € de charges fixes par an. Chaque unité est vendue {_num(price)} € et coûte {_num(variable)} € de charges variables. Quel chiffre d'affaires annuel atteint le seuil de rentabilité ?", "euros"),
                        [f"Taux de marge sur coût variable = ({_num(price)} − {_num(variable)}) / {_num(price)} = {rate:.6f}",
                         f"Seuil = charges fixes / taux = {fixed} / {rate:.6f} = {_num(value)}"], value, abs_tol=0.02)
    if subskill == "drawdown":
        values, current = [], rng.randrange(8000, 20000, 100)
        for _ in range(rng.randint(6, 8)):
            values.append(current)
            current = max(500, int(round(current * rng.uniform(0.72, 1.3), -1)))
        peak, worst, steps = values[0], 0.0, []
        for v in values:
            peak = max(peak, v)
            drop = (peak - v) / peak * 100
            if drop > worst:
                worst = drop
                steps.append(f"Sommet {peak}, creux {v} : baisse = ({peak} − {v}) / {peak} × 100 = {_num(drop)} %")
        if worst == 0:
            steps.append("La valeur ne redescend jamais sous un sommet précédent : aucune baisse.")
        return _numeric(_ask(rng, role, f"Un portefeuille de {firm} vaut successivement, en euros : {', '.join(map(str, values))}. Quel est le drawdown maximal (plus forte baisse depuis un sommet précédent) ?", "pourcentage"),
                        steps + [f"Drawdown maximal = {_num(worst)} %"], worst, tokens=460)
    if subskill == "mensualite":
        capital, annual, months = rng.randrange(3000, 250000, 1000), rng.choice([1.2, 2.4, 3, 3.6, 4.8, 6]), rng.choice([12, 24, 36, 60, 120, 180, 240])
        t = annual / 100 / 12
        value = capital * t / (1 - (1 + t) ** -months)
        return _numeric(_ask(rng, role, f"{firm.capitalize()} emprunte {capital} € sur {months} mois au taux annuel nominal de {annual} % (taux mensuel = taux annuel / 12). Quelle est la mensualité constante ?", "euros"),
                        [f"Taux mensuel t = {annual} % / 12 = {t:.6f}", f"Mensualité = C × t / (1 − (1 + t)^−n) = {capital} × {t:.6f} / (1 − {(1 + t) ** -months:.6f})",
                         f"Mensualité = {_num(value)}"], value, abs_tol=0.02)
    probability = rng.choice([0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.75])
    gain, loss = rng.randrange(200, 20000, 100), rng.randrange(100, 9000, 100)
    value = probability * gain - (1 - probability) * loss
    verdict = "positive : la décision est favorable en moyenne" if value > 0 else "négative ou nulle : la décision détruit de la valeur en moyenne"
    return _numeric(_ask(rng, role, f"{firm.capitalize()} envisage une opération qui rapporte {gain} € avec une probabilité de {probability} et fait perdre {loss} € sinon. Quelle est l'espérance de gain ?", "euros"),
                    [f"Espérance = p × gain − (1 − p) × perte = {probability} × {gain} − {1 - probability:.2f} × {loss}",
                     f"Espérance = {_num(probability * gain)} − {_num((1 - probability) * loss)} = {_num(value)}", f"L'espérance est {verdict}."], value)


# --- engineering.calc ------------------------------------------------------

_PARTS = {"train": ["une entretoise", "un support moteur", "un carter", "une bague", "un boîtier"],
          "exam": ["une rondelle épaisse", "un palier", "un capot", "un manchon", "un socle"]}
_DENSITY = {"PLA": 1.24, "PETG": 1.27, "ABS": 1.04, "ASA": 1.07, "TPU": 1.21}


@family("engineering.calc", "engineering", ("volume", "masse", "conversion", "jeu", "temps_impression", "puissance",
                                            "cinematique", "echelle"))
def _engineering(rng, role, subskill):
    part = rng.choice(_PARTS["exam" if _exam(role) else "train"])
    if subskill == "volume":
        shape = rng.choice(["cylindre", "pave", "tube", "sphere"])
        if shape == "cylindre":
            d, h = round(rng.uniform(4, 120), 1), round(rng.uniform(2, 200), 1)
            value = math.pi * (d / 2) ** 2 * h / 1000
            return _numeric(_ask(rng, role, f"{part.capitalize()} est un cylindre plein de diamètre {d} mm et de hauteur {h} mm. Quel est son volume ?", "cm³"),
                            [f"Rayon = {d} / 2 = {d / 2} mm", f"Volume = π × r² × h = π × {d / 2}² × {h} = {math.pi * (d / 2) ** 2 * h:.2f} mm³",
                             f"1 cm³ = 1000 mm³, donc volume = {_num(value)} cm³"], value)
        if shape == "pave":
            a, b, c = (round(rng.uniform(3, 220), 1) for _ in range(3))
            value = a * b * c / 1000
            return _numeric(_ask(rng, role, f"{part.capitalize()} est un pavé droit de {a} mm × {b} mm × {c} mm. Quel est son volume ?", "cm³"),
                            [f"Volume = {a} × {b} × {c} = {a * b * c:.2f} mm³", f"Volume = {_num(value)} cm³"], value)
        if shape == "tube":
            outer = round(rng.uniform(10, 120), 1)
            inner, h = round(outer * rng.uniform(0.3, 0.85), 1), round(rng.uniform(5, 300), 1)
            value = math.pi * ((outer / 2) ** 2 - (inner / 2) ** 2) * h / 1000
            return _numeric(_ask(rng, role, f"{part.capitalize()} est un tube de diamètre extérieur {outer} mm, de diamètre intérieur {inner} mm et de longueur {h} mm. Quel est le volume de matière ?", "cm³"),
                            [f"Volume = π × (R² − r²) × h = π × ({outer / 2}² − {inner / 2}²) × {h}",
                             f"= {math.pi * ((outer / 2) ** 2 - (inner / 2) ** 2) * h:.2f} mm³ = {_num(value)} cm³"], value)
        d = round(rng.uniform(5, 150), 1)
        value = 4 / 3 * math.pi * (d / 2) ** 3 / 1000
        return _numeric(_ask(rng, role, f"Une bille pleine a un diamètre de {d} mm. Quel est son volume ?", "cm³"),
                        [f"Volume = 4/3 × π × r³ = 4/3 × π × {d / 2}³ = {4 / 3 * math.pi * (d / 2) ** 3:.2f} mm³", f"Volume = {_num(value)} cm³"], value)
    if subskill == "masse":
        material = rng.choice(sorted(_DENSITY))
        volume, infill = round(rng.uniform(2, 600), 1), rng.choice([15, 20, 30, 40, 50, 100])
        value = volume * _DENSITY[material] * infill / 100
        return _numeric(_ask(rng, role, f"{part.capitalize()} occupe un volume de {volume} cm³. Elle est imprimée en {material} (masse volumique {_DENSITY[material]} g/cm³) et l'on suppose que {infill} % de ce volume est rempli de matière. Quelle masse de filament faut-il ?", "grammes"),
                        [f"Volume de matière = {volume} × {infill} / 100 = {volume * infill / 100:.2f} cm³",
                         f"Masse = volume × masse volumique = {volume * infill / 100:.2f} × {_DENSITY[material]} = {_num(value)} g"], value)
    if subskill == "conversion":
        kind = rng.choice(["mm_in", "in_mm", "rpm_rad", "kmh_ms", "c_k", "nmm_nm", "cm3_mm3"])
        x = round(rng.uniform(1, 900), 2)
        table = {"mm_in": (f"{x} mm en pouces", x / 25.4, "pouces", f"{x} / 25.4", 3),
                 "in_mm": (f"{x} pouces en millimètres", x * 25.4, "millimètres", f"{x} × 25.4", 2),
                 "rpm_rad": (f"{x} tr/min en rad/s", x * 2 * math.pi / 60, "rad/s", f"{x} × 2π / 60", 3),
                 "kmh_ms": (f"{x} km/h en m/s", x / 3.6, "m/s", f"{x} / 3.6", 3),
                 "c_k": (f"{x} °C en kelvins", x + 273.15, "kelvins", f"{x} + 273.15", 2),
                 "nmm_nm": (f"{x} N·mm en N·m", x / 1000, "N·m", f"{x} / 1000", 4),
                 "cm3_mm3": (f"{x} cm³ en mm³", x * 1000, "mm³", f"{x} × 1000", 1)}
        text, value, unit, formula, digits = table[kind]
        return _numeric(_ask(rng, role, f"Convertis {text}.", unit, digits), [f"{formula} = {_num(value, digits)}"], value, digits)
    if subskill == "jeu":
        nominal = rng.choice([4, 5, 6, 8, 10, 12, 16, 20, 25, 30])
        hole_tol, shaft_tol = round(rng.uniform(0.01, 0.3), 3), round(rng.uniform(0.01, 0.3), 3)
        shaft = round(nominal - rng.uniform(0.0, 0.4), 3)
        if rng.random() < 0.5:
            value = nominal - shaft
            return _numeric(_ask(rng, role, f"Un alésage est coté Ø{nominal} mm avec une tolérance de 0 / +{hole_tol} mm. L'axe est coté Ø{shaft} mm avec une tolérance de −{shaft_tol} / 0 mm. Quel est le jeu diamétral minimal ?", "mm", 3),
                            [f"Jeu minimal = alésage minimal − axe maximal = {nominal} − {shaft} = {_num(value, 3)}"], value, 3)
        value = (nominal + hole_tol) - (shaft - shaft_tol)
        return _numeric(_ask(rng, role, f"Un alésage est coté Ø{nominal} mm avec une tolérance de 0 / +{hole_tol} mm. L'axe est coté Ø{shaft} mm avec une tolérance de −{shaft_tol} / 0 mm. Quel est le jeu diamétral maximal ?", "mm", 3),
                        [f"Alésage maximal = {nominal} + {hole_tol} = {_num(nominal + hole_tol, 3)}", f"Axe minimal = {shaft} − {shaft_tol} = {_num(shaft - shaft_tol, 3)}",
                         f"Jeu maximal = {_num(nominal + hole_tol, 3)} − {_num(shaft - shaft_tol, 3)} = {_num(value, 3)}"], value, 3)
    if subskill == "temps_impression":
        volume = round(rng.uniform(1, 300), 1)
        width, layer, speed = rng.choice([0.4, 0.45, 0.6]), rng.choice([0.12, 0.16, 0.2, 0.28]), rng.choice([40, 60, 80, 120, 200])
        flow = width * layer * speed
        value = volume * 1000 / flow / 60
        return _numeric(_ask(rng, role, f"Il faut déposer {volume} cm³ de matière. La buse dépose un cordon de {width} mm de large et {layer} mm de haut à {speed} mm/s en continu. Combien de temps dure le dépôt, hors déplacements ?", "minutes"),
                        [f"Débit = {width} × {layer} × {speed} = {flow:.3f} mm³/s", f"Volume = {volume} × 1000 = {volume * 1000:.0f} mm³",
                         f"Durée = {volume * 1000:.0f} / {flow:.3f} = {volume * 1000 / flow:.1f} s = {_num(value)} min"], value, abs_tol=0.02)
    if subskill == "puissance":
        torque, rpm = round(rng.uniform(0.1, 60), 2), rng.randrange(60, 6000, 10)
        if rng.random() < 0.5:
            value = torque * rpm * 2 * math.pi / 60
            return _numeric(_ask(rng, role, f"Un moteur fournit un couple de {torque} N·m à {rpm} tr/min. Quelle puissance mécanique délivre-t-il ?", "watts"),
                            [f"ω = {rpm} × 2π / 60 = {rpm * 2 * math.pi / 60:.3f} rad/s", f"P = C × ω = {torque} × {rpm * 2 * math.pi / 60:.3f} = {_num(value)} W"], value, abs_tol=0.02)
        ratio, efficiency = rng.choice([3, 4, 5, 10, 16, 25, 50]), rng.choice([80, 85, 90, 95])
        value = torque * ratio * efficiency / 100
        return _numeric(_ask(rng, role, f"Un moteur délivre {torque} N·m en entrée d'un réducteur de rapport {ratio}:1 dont le rendement vaut {efficiency} %. Quel couple est disponible en sortie ?", "N·m"),
                        [f"Couple de sortie = couple × rapport × rendement = {torque} × {ratio} × {efficiency / 100} = {_num(value)}"], value)
    if subskill == "cinematique":
        if rng.random() < 0.5:
            v0, a, t = round(rng.uniform(0, 12), 1), round(rng.uniform(0.2, 6), 1), round(rng.uniform(1, 20), 1)
            value = v0 * t + 0.5 * a * t * t
            return _numeric(_ask(rng, role, f"Un chariot part à {v0} m/s et accélère uniformément à {a} m/s² pendant {t} s. Quelle distance parcourt-il ?", "mètres"),
                            [f"d = v0 × t + ½ × a × t² = {v0} × {t} + 0.5 × {a} × {t}²", f"d = {v0 * t:.2f} + {0.5 * a * t * t:.2f} = {_num(value)}"], value)
        h = round(rng.uniform(0.3, 80), 2)
        value = math.sqrt(2 * h / 9.81)
        return _numeric(_ask(rng, role, f"Une pièce tombe sans vitesse initiale d'une hauteur de {h} m (g = 9.81 m/s², frottements négligés). Combien de temps dure la chute ?", "secondes", 3),
                        [f"t = √(2h / g) = √(2 × {h} / 9.81) = √({2 * h / 9.81:.5f}) = {_num(value, 3)}"], value, 3)
    mass, factor = round(rng.uniform(2, 900), 1), rng.choice([0.5, 0.75, 1.25, 1.5, 2, 2.5, 3])
    if rng.random() < 0.5:
        value = mass * factor ** 3
        return _numeric(_ask(rng, role, f"{part.capitalize()} pleine pèse {mass} g. On l'imprime à l'échelle {factor} dans les trois directions, même matière et même remplissage. Quelle est sa nouvelle masse ?", "grammes"),
                        [f"La masse suit le volume, donc le cube de l'échelle : {factor}³ = {factor ** 3:.4f}", f"Masse = {mass} × {factor ** 3:.4f} = {_num(value)}"], value)
    value = mass * factor ** 2
    return _numeric(_ask(rng, role, f"La surface extérieure de {part} vaut {mass} cm². On l'imprime à l'échelle {factor} dans les trois directions. Quelle est sa nouvelle surface ?", "cm²"),
                    [f"La surface suit le carré de l'échelle : {factor}² = {factor ** 2:.4f}", f"Surface = {mass} × {factor ** 2:.4f} = {_num(value)}"], value)


# --- media.prompt_spec / media.prompt_translate ---------------------------

# (lemme, pluriel, genre, anglais singulier, anglais pluriel)
_NOUNS = {"train": [("chat", "chats", "m", "cat", "cats"), ("voiture", "voitures", "f", "car", "cars"),
                    ("arbre", "arbres", "m", "tree", "trees"), ("lampe", "lampes", "f", "lamp", "lamps"),
                    ("canapé", "canapés", "m", "sofa", "sofas"), ("fleur", "fleurs", "f", "flower", "flowers"),
                    ("robot", "robots", "m", "robot", "robots"), ("maison", "maisons", "f", "house", "houses"),
                    ("ballon", "ballons", "m", "ball", "balls"), ("table", "tables", "f", "table", "tables")],
          "exam": [("chien", "chiens", "m", "dog", "dogs"), ("chaise", "chaises", "f", "chair", "chairs"),
                   ("vélo", "vélos", "m", "bicycle", "bicycles"), ("tasse", "tasses", "f", "cup", "cups"),
                   ("livre", "livres", "m", "book", "books"), ("porte", "portes", "f", "door", "doors"),
                   ("dragon", "dragons", "m", "dragon", "dragons"), ("bougie", "bougies", "f", "candle", "candles"),
                   ("bateau", "bateaux", "m", "boat", "boats"), ("fenêtre", "fenêtres", "f", "window", "windows")]}
# (masc. sing., fém. sing., masc. plur., fém. plur., anglais)
_COLORS = {"train": [("rouge", "rouge", "rouges", "rouges", "red"), ("bleu", "bleue", "bleus", "bleues", "blue"),
                     ("vert", "verte", "verts", "vertes", "green"), ("noir", "noire", "noirs", "noires", "black"),
                     ("jaune", "jaune", "jaunes", "jaunes", "yellow")],
           "exam": [("blanc", "blanche", "blancs", "blanches", "white"), ("gris", "grise", "gris", "grises", "grey"),
                    ("violet", "violette", "violets", "violettes", "purple"), ("rose", "rose", "roses", "roses", "pink"),
                    ("brun", "brune", "bruns", "brunes", "brown")]}
_NUMBERS = ["un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix"]
_NUMBERS_EN = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
_RELATIONS = [("sur", "on"), ("sous", "under"), ("à gauche de", "left of"), ("à droite de", "right of"),
              ("devant", "in front of"), ("derrière", "behind"), ("à côté de", "next to")]
_STYLES = {"train": [("aquarelle", "watercolor"), ("photo réaliste", "realistic photo"), ("dessin au crayon", "pencil drawing")],
           "exam": [("peinture à l'huile", "oil painting"), ("animation japonaise", "anime"), ("pâte à modeler", "claymation")]}
_SPEC_SCHEMA = ("Clés attendues : `objects` (liste d'objets {\"name\": nom au singulier, \"count\": entier, \"color\": couleur au masculin singulier ou null}), "
                "`relations` (liste de {\"subject\": nom, \"relation\": une valeur parmi " + _json([r for r, _ in _RELATIONS]) + ", \"object\": nom}), "
                "`exclusions` (liste des noms au singulier explicitement interdits) et `style` (style demandé ou null).")
_SPEC_PROMPTS = {
    "train": ["Demande de création visuelle : « {request} »\n\nExtrais sa spécification sous la forme d'un unique objet JSON. " + _SPEC_SCHEMA + " Réponds uniquement par le JSON.",
              "Analyse cette demande d'image : « {request} »\n\nRetourne un seul objet JSON décrivant ce qu'il faut dessiner. " + _SPEC_SCHEMA + " Aucun texte hors du JSON."],
    "exam": ["Un utilisateur écrit : « {request} »\n\nAvant de générer, liste exactement ce qui est demandé dans un objet JSON. " + _SPEC_SCHEMA + " Sortie : le JSON seul.",
             "Brief reçu : « {request} »\n\nTraduis ce brief en contrat JSON vérifiable. " + _SPEC_SCHEMA + " N'écris rien d'autre que cet objet."],
}


def _article(count, gender):
    return ("un" if gender == "m" else "une") if count == 1 else _NUMBERS[count - 1]


def _scene(rng, role, simple=False):
    side = "exam" if _exam(role) else "train"
    nouns = rng.sample(_NOUNS[side], 2 if simple else rng.choice([2, 3]))
    objects, phrases, english = [], [], []
    for lemma, plural, gender, en, en_plural in nouns:
        count = rng.choice([1, 1, 2, 3, 4, 5]) if not simple else rng.choice([1, 2, 3])
        color = rng.choice(_COLORS[side] + [None]) if not simple else rng.choice(_COLORS[side])
        form = "" if color is None else " " + color[(0 if gender == "m" else 1) + (2 if count > 1 else 0)]
        objects.append({"name": lemma, "count": count, "color": None if color is None else color[0]})
        phrases.append(f"{_article(count, gender)} {plural if count > 1 else lemma}{form}")
        english.append({"count": count, "noun": (en, en_plural), "color": None if color is None else color[4]})
    return objects, phrases, english


@family("media.prompt_spec", "media", ("counts_colors", "relations", "exclusions", "style"))
def _prompt_spec(rng, role, subskill):
    side = "exam" if _exam(role) else "train"
    objects, phrases, _ = _scene(rng, role)
    relations, exclusions, style = [], [], None
    request = phrases[0]
    if subskill in ("relations", "style") or rng.random() < 0.35:
        relation = rng.choice(_RELATIONS)[0]
        relations.append({"subject": objects[0]["name"], "relation": relation, "object": objects[1]["name"]})
        request = f"{phrases[0]} {relation} {phrases[1]}"
        rest = phrases[2:]
    else:
        rest = phrases[1:]
    if rest:
        request += (", avec " if _exam(role) else " et ") + " et ".join(rest)
    request = _contract(request)
    if subskill == "exclusions" or rng.random() < 0.2:
        used = {o["name"] for o in objects}
        banned = rng.choice([n for n in _NOUNS[side] if n[0] not in used])
        exclusions.append(banned[0])
        request += (f", sans {banned[0]}" if rng.random() < 0.5 else f", surtout aucun{'e' if banned[2] == 'f' else ''} {banned[0]}")
    if subskill == "style" or rng.random() < 0.25:
        style = rng.choice(_STYLES[side])[0]
        request += (f", style {style}" if rng.random() < 0.5 else f", rendu façon {style}")
    opener = rng.choice(["Dessine", "Génère", "Je veux"] if not _exam(role) else ["Crée", "Fais-moi", "Il me faut"])
    request = f"{opener} {request}."
    spec = {"objects": objects, "relations": relations, "exclusions": exclusions, "style": style}
    return {"messages": [{"role": "user", "content": rng.choice(_SPEC_PROMPTS[side]).replace("{request}", request)}],
            "target": _json(spec), "max_new_tokens": 360,
            "grader": {"type": "json", "accept": [spec], "unordered": ["/objects", "/relations", "/exclusions"]}}


_TRANSLATE_PROMPTS = {
    "train": ["Traduis cette demande en un prompt anglais concis pour un générateur d'images, en conservant exactement les quantités, les couleurs et les positions : « {request} » Réponds uniquement par le prompt anglais.",
              "Rewrite this French request as one concise English image prompt. Keep every quantity, colour and position exactly: « {request} » Output the English prompt only."],
    "exam": ["Le moteur d'images ne comprend que l'anglais. Convertis fidèlement : « {request} » — mêmes nombres, mêmes couleurs, mêmes relations spatiales. Donne seulement la phrase anglaise.",
             "Convert to English for the image model, preserving all counts, colours and spatial relations: « {request} » Reply with the English sentence alone."],
}


@family("media.prompt_translate", "media", ("counts_colors", "relations"))
def _prompt_translate(rng, role, subskill):
    side = "exam" if _exam(role) else "train"
    objects, phrases, english = _scene(rng, role, simple=True)
    relation = rng.choice(_RELATIONS)
    if subskill == "relations":
        request = _contract(f"{phrases[0]} {relation[0]} {phrases[1]}")
    else:
        request = f"{phrases[0]} et {phrases[1]}"

    def render(entry):
        number = ("a" if entry["count"] == 1 else _NUMBERS_EN[entry["count"] - 1])
        return f"{number} {entry['color'] + ' ' if entry['color'] else ''}{entry['noun'][1 if entry['count'] > 1 else 0]}"
    target = f"{render(english[0])} {relation[1]} {render(english[1])}" if subskill == "relations" else f"{render(english[0])} and {render(english[1])}"
    required = []
    for entry in english:
        required.append([entry["noun"][1 if entry["count"] > 1 else 0]])
        if entry["count"] > 1:
            required.append([_NUMBERS_EN[entry["count"] - 1], str(entry["count"])])
        if entry["color"]:
            required.append([entry["color"]] + (["gray"] if entry["color"] == "grey" else []) + (["violet"] if entry["color"] == "purple" else []))
    forbidden = []
    if subskill == "relations":
        synonyms = {"on": ["on", "on top of", "atop"], "under": ["under", "beneath", "below", "underneath"],
                    "left of": ["left of", "to the left of", "on the left of"], "right of": ["right of", "to the right of", "on the right of"],
                    "in front of": ["in front of"], "behind": ["behind"], "next to": ["next to", "beside", "by"]}
        required.append(synonyms[relation[1]])
        opposite = {"left of": "right of", "right of": "left of", "under": "on top of", "behind": "in front of", "in front of": "behind"}
        if relation[1] in opposite:
            forbidden.append(opposite[relation[1]])
    return {"messages": [{"role": "user", "content": rng.choice(_TRANSLATE_PROMPTS[side]).format(request=request)}],
            "target": target, "max_new_tokens": 72,
            "grader": {"type": "contains", "required": required, "forbidden": forbidden, "max_chars": 220}}


# --- cowork.extract_fields -------------------------------------------------

_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
_CLIENTS = {"train": ["Cycles Durand", "Atelier Morel", "Boulangerie Petit", "Garage Lefèvre", "Studio Marin", "Menuiserie Roux"],
            "exam": ["Brasserie Faure", "Imprimerie Colin", "Ferme Blanchard", "Cabinet Renaud", "Verrerie Chevalier", "Fonderie Gautier"]}
_DOC_TEMPLATES = {
    "train": ["FACTURE {ref}\nClient : {client}\nÉmise le {issued}. Livraison effectuée le {noise_date}.\nTotal hors taxes : {ht} €\nTVA {rate} % : {tva} €\nTotal TTC : {ttc} €\nAcompte déjà versé : {noise_amount} €\nÀ régler avant le {due}.",
              "Bonjour,\n\nVeuillez trouver la facture n° {ref} adressée à {client}, datée du {issued}. Notre dernier échange remonte au {noise_date}. Le montant s'élève à {ht} € HT, soit {ttc} € TTC (TVA {rate} %). Une remise de {noise_amount} € avait été évoquée mais n'est pas appliquée. Merci de régler au plus tard le {due}.\n\nCordialement"],
    "exam": ["Objet : relance — pièce {ref}\n\nMadame, Monsieur,\nNous revenons vers {client} au sujet de la facture {ref} du {issued}. Le devis initial datait du {noise_date} et prévoyait {noise_amount} € de frais de port, offerts. Restent dus {ttc} € toutes taxes comprises ({ht} € hors taxes, TVA à {rate} %). Date limite de paiement : {due}.",
             "RELEVÉ DE COMPTE\nRéférence du document : {ref} | Destinataire : {client}\nDate d'émission : {issued} | Commande passée le {noise_date}\nBase HT {ht} € — taxe {rate} % — net à payer {ttc} € TTC\nPénalités éventuelles : {noise_amount} € par mois de retard\nÉchéance : {due}"],
}
_EXTRACT_PROMPTS = {
    "train": ["Document :\n{doc}\n\nExtrais un objet JSON avec exactement les clés `client`, `reference`, `date_emission`, `date_echeance` (dates au format AAAA-MM-JJ), `montant_ht` et `montant_ttc` (nombres en euros). Réponds uniquement par le JSON.",
              "Texte reçu :\n{doc}\n\nRetourne uniquement un objet JSON : `client`, `reference`, `date_emission` et `date_echeance` au format AAAA-MM-JJ, `montant_ht` et `montant_ttc` en nombres."],
    "exam": ["Voici une pièce comptable :\n{doc}\n\nRemplis la fiche JSON suivante et rien d'autre : `client`, `reference`, `date_emission`, `date_echeance` (ISO AAAA-MM-JJ), `montant_ht`, `montant_ttc` (valeurs numériques en euros).",
             "Pièce à saisir :\n{doc}\n\nProduis la saisie au format JSON strict avec les clés `client`, `reference`, `date_emission`, `date_echeance` (AAAA-MM-JJ), `montant_ht`, `montant_ttc` (nombres). Aucun commentaire."],
}


def _date(rng):
    return rng.choice([2025, 2026, 2027]), rng.randint(1, 12), rng.randint(1, 28)


def _date_text(rng, date):
    year, month, day = date
    return rng.choice([f"{day}{'er' if day == 1 else ''} {_MONTHS[month - 1]} {year}", f"{day:02d}/{month:02d}/{year}"])


def _euros(rng, value):
    plain = f"{value:.2f}"
    if rng.random() < 0.5:
        whole, cents = plain.split(".")
        groups = []
        while whole:
            groups.insert(0, whole[-3:])
            whole = whole[:-3]
        return " ".join(groups) + "," + cents
    return plain


@family("cowork.extract_fields", "cowork", ("facture",))
def _extract(rng, role, subskill):
    side = "exam" if _exam(role) else "train"
    issued, due, noise = _date(rng), _date(rng), _date(rng)
    rate = rng.choice([5.5, 10, 20])
    ht = round(rng.uniform(40, 25000), 2)
    ttc = round(ht * (1 + rate / 100), 2)
    reference = rng.choice(["F", "FA", "INV", "R"] if side == "train" else ["DOC", "RL", "PC", "K"]) + "-" + str(rng.randint(2025, 2027)) + "-" + str(rng.randint(100, 9999))
    client = rng.choice(_CLIENTS[side])
    doc = rng.choice(_DOC_TEMPLATES[side]).format(
        ref=reference, client=client, issued=_date_text(rng, issued), due=_date_text(rng, due),
        noise_date=_date_text(rng, noise), ht=_euros(rng, ht), ttc=_euros(rng, ttc), rate=str(rate).replace(".", ","),
        tva=_euros(rng, ttc - ht), noise_amount=_euros(rng, round(rng.uniform(5, 900), 2)))
    record = {"client": client, "reference": reference, "date_emission": "%04d-%02d-%02d" % issued,
              "date_echeance": "%04d-%02d-%02d" % due, "montant_ht": ht, "montant_ttc": ttc}
    return {"messages": [{"role": "user", "content": rng.choice(_EXTRACT_PROMPTS[side]).format(doc=doc)}],
            "target": _json(record), "grader": {"type": "json", "accept": [record]}, "max_new_tokens": 220}


# --- code.trace ------------------------------------------------------------

def _run_trusted(source):
    """Execute one of OUR OWN templates to measure its real output (never model code)."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exec(compile(source, "<aurora-template>", "exec"), {"__builtins__": __builtins__, "__name__": "__main__"})
    return buffer.getvalue()


def _trace_program(rng, role, subskill):
    exam = _exam(role)
    a, b, c = rng.randint(2, 9), rng.randint(3, 12), rng.randint(2, 6)
    words = rng.sample(["aurora", "vélo", "mission", "tunnel", "bridge", "rendu", "maillage", "pointeur"], 4)
    numbers = [rng.randint(-9, 30) for _ in range(rng.randint(5, 8))]
    if subskill == "loops":
        if not exam:
            return f"total = 0\nfor i in range({a}, {a + b}):\n    if i % {c} == 0:\n        total += i\n    else:\n        total -= 1\nprint(total)\n"
        return f"n = {a * b}\nsteps = 0\nwhile n > 1:\n    n = n // 2 if n % 2 == 0 else n - 1\n    steps += 1\nprint(steps, n)\n"
    if subskill == "strings":
        if not exam:
            return f"text = {words[0]!r} + '-' + {words[1]!r}\nprint(text[{a % 4}:{a % 4 + c}].upper())\nprint(len(text), text.count({words[0][0]!r}))\n"
        return f"parts = {words!r}\nresult = '/'.join(w[::-1] for w in parts if len(w) > {c + 2})\nprint(result)\nprint(result.split('/')[-1][:{c}])\n"
    if subskill == "collections":
        if not exam:
            return f"values = {numbers!r}\ncounts = {{}}\nfor v in values:\n    key = v % {c}\n    counts[key] = counts.get(key, 0) + 1\nprint(sorted(counts.items()))\n"
        return f"values = {numbers!r}\nseen = set()\nkept = []\nfor v in values:\n    if abs(v) not in seen:\n        seen.add(abs(v))\n        kept.append(v)\nprint(kept[-{c % 3 + 1}:], len(seen))\n"
    if subskill == "recursion":
        if not exam:
            return f"def f(n):\n    if n <= 1:\n        return {c}\n    return f(n - 1) + n * {a % 3 + 1}\n\nprint(f({b % 6 + 3}))\n"
        return f"def g(n, depth=0):\n    if n < {c}:\n        return depth\n    return g(n // {c}, depth + 1) + n % {c}\n\nprint(g({a * b * 7}))\n"
    if not exam:
        return f"values = {numbers!r}\nsquares = [v * v for v in values if v % 2 == {a % 2}]\nprint(squares)\nprint(sum(squares) - max(values))\n"
    return f"values = {numbers!r}\npairs = sorted(((v % {c}, v) for v in values), key=lambda p: (p[0], -p[1]))\nprint([v for _, v in pairs][:{c}])\n"


_TRACE_PROMPTS = {
    "train": ["Quelle est la sortie exacte de ce programme Python ?\n\n```python\n{code}```\n\nRéponds uniquement par ce qui est affiché, ligne pour ligne.",
              "What does this Python program print?\n\n```python\n{code}```\n\nAnswer with the exact output only, line by line."],
    "exam": ["On exécute le script suivant avec Python 3 :\n\n```python\n{code}```\n\nRecopie précisément ce qui apparaît sur la sortie standard, sans explication.",
             "The following script runs under Python 3:\n\n```python\n{code}```\n\nWrite exactly what appears on standard output, with no explanation."],
}


@family("code.trace", "code", ("loops", "strings", "collections", "recursion", "comprehension"))
def _trace(rng, role, subskill):
    code = _trace_program(rng, role, subskill)
    output = _run_trusted(code)
    prompt = rng.choice(_TRACE_PROMPTS["exam" if _exam(role) else "train"])
    return {"messages": [{"role": "user", "content": prompt.format(code=code)}], "target": output.strip("\n"),
            "lang": "en" if prompt.startswith(("What", "The following")) else "fr",
            "grader": {"type": "python_output", "stdout": output}, "max_new_tokens": 96}


# --- conversation.format_fr ------------------------------------------------

_TOPICS = {
    "train": {
        "l'entretien d'un vélo": ["Nettoie la chaîne après chaque sortie sous la pluie.", "Vérifie la pression des pneus chaque semaine.",
                                  "Contrôle l'usure des patins de frein.", "Graisse les câbles avant l'hiver.",
                                  "Resserre les vis du cintre et de la selle.", "Range le vélo à l'abri de l'humidité."],
        "l'impression 3D": ["Nivelle le plateau avant une longue impression.", "Sèche le filament s'il a pris l'humidité.",
                            "Ajoute des supports sous les porte-à-faux.", "Réduis la vitesse pour les petits détails.",
                            "Nettoie la buse quand le débit devient irrégulier.", "Oriente la pièce pour limiter les supports."],
        "la sauvegarde des données": ["Garde trois copies de tes fichiers importants.", "Stocke une copie hors de ton domicile.",
                                      "Teste la restauration au moins une fois par an.", "Chiffre les disques que tu transportes.",
                                      "Automatise les sauvegardes pour ne pas les oublier.", "Note où se trouvent les clés de chiffrement."],
        "la rédaction d'un rapport": ["Annonce la conclusion dès le premier paragraphe.", "Utilise des titres qui résument chaque partie.",
                                      "Chiffre tes affirmations quand c'est possible.", "Relis le texte à voix haute pour repérer les lourdeurs.",
                                      "Place les détails techniques en annexe.", "Termine par les actions attendues du lecteur."],
    },
    "exam": {
        "la préparation d'une randonnée": ["Consulte la météo la veille du départ.", "Emporte un litre d'eau par tranche de deux heures.",
                                           "Préviens un proche de ton itinéraire.", "Garde une couche chaude au fond du sac.",
                                           "Charge la carte hors ligne sur ton téléphone.", "Pars tôt pour éviter l'orage de l'après-midi."],
        "la gestion d'un budget": ["Note chaque dépense pendant un mois complet.", "Mets de côté une épargne de précaution.",
                                   "Résilie les abonnements que tu n'utilises plus.", "Compare les offres avant un gros achat.",
                                   "Fixe un plafond pour les dépenses de loisirs.", "Rembourse d'abord le crédit le plus cher."],
        "la sécurité d'un mot de passe": ["Utilise une phrase longue plutôt qu'un mot court.", "Active la double authentification partout.",
                                          "Ne réutilise jamais le même secret sur deux sites.", "Confie tes accès à un gestionnaire dédié.",
                                          "Change un mot de passe dès qu'une fuite est annoncée.", "Méfie-toi des liens reçus par courriel."],
    },
}
_FORMAT_PROMPTS = {
    "train": ["Donne des conseils sur {topic}. Contraintes à respecter toutes ensemble : {rules}",
              "Écris un court texte sur {topic}. Respecte strictement ces consignes : {rules}"],
    "exam": ["Rédige une réponse à propos de {topic}. Elle doit obéir à chacune de ces règles : {rules}",
             "Sujet : {topic}. Ta réponse sera vérifiée automatiquement sur ces points : {rules}"],
}


@family("conversation.format_fr", "conversation", ("bullets", "lines_bounds", "json_keys", "uppercase"))
def _format(rng, role, subskill):
    side = "exam" if _exam(role) else "train"
    topic = rng.choice(sorted(_TOPICS[side]))
    tips = rng.sample(_TOPICS[side][topic], len(_TOPICS[side][topic]))
    if subskill == "bullets":
        count = rng.randint(2, 5)
        banned = rng.choice(["toujours", "jamais", "simplement", "évidemment"])
        chosen = [t for t in tips if banned not in t.lower()][:count]
        ending = rng.choice(["Bonne route !", "À toi de jouer.", "Fin de la liste."])
        target = "\n".join(f"- {t}" for t in chosen) + "\n" + ending
        rules = [{"kind": "bullets", "count": len(chosen)}, {"kind": "exclude", "words": [banned]}, {"kind": "ends_with", "text": ending}]
        text = f"exactement {len(chosen)} puces commençant par « - » ; le mot « {banned} » est interdit ; la réponse se termine exactement par « {ending} »."
    elif subskill == "lines_bounds":
        count = rng.randint(2, 4)
        chosen = tips[:count]
        opening = rng.choice(["Voici l'essentiel :", "En bref :", "À retenir :"])
        target = opening + "\n" + "\n".join(chosen)
        limit = len(" ".join([opening] + chosen).split()) + rng.randint(3, 12)
        rules = [{"kind": "lines", "count": count + 1}, {"kind": "starts_with", "text": opening}, {"kind": "max_words", "count": limit}]
        text = f"exactement {count + 1} lignes non vides ; la première ligne est exactement « {opening} » ; au plus {limit} mots au total."
    elif subskill == "json_keys":
        keys = rng.choice([["conseil_1", "conseil_2", "conseil_3"], ["premier", "deuxieme", "troisieme"], ["etape_a", "etape_b", "etape_c"]]
                          if side == "train" else [["point_1", "point_2", "point_3"], ["un", "deux", "trois"], ["idee_x", "idee_y", "idee_z"]])
        target = json.dumps({k: t for k, t in zip(keys, tips)}, ensure_ascii=False)
        rules = [{"kind": "json_keys", "keys": keys}]
        text = f"un unique objet JSON dont les clés sont exactement {_json(keys)}, chaque valeur étant un conseil d'une phrase ; aucun texte hors du JSON."
    else:
        count = rng.randint(1, 3)
        target = "\n".join(t.upper() for t in tips[:count])
        rules = [{"kind": "uppercase"}, {"kind": "lines", "count": count}]
        text = f"tout le texte en MAJUSCULES ; exactement {count} ligne{'s' if count > 1 else ''} non vide{'s' if count > 1 else ''}."
    return {"messages": [{"role": "user", "content": rng.choice(_FORMAT_PROMPTS[side]).format(topic=topic, rules=text)}],
            "target": target, "grader": {"type": "constraints", "rules": rules}, "max_new_tokens": 220}
