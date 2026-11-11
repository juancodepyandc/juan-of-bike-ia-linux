"""Seeded exercise families with executable oracles, for skills no public dataset covers.

Each family returns an item holding BOTH a reference ``target`` and a ``grader``;
the suite builder keeps the one its role needs. Train and exam items differ by
construction: disjoint vocabularies, disjoint prompt templates and separate seed
namespaces, so an exam cannot be passed by memorising training items.

Mission families use the production contracts of ``agi_core`` as oracles: the
same validators that accept or reject a real mission action grade the answer.
"""
from __future__ import annotations

import hashlib
import json
import random

from .records import question_hash

FAMILIES = {}


def family(name, module, subskills):
    def register(function):
        FAMILIES[name] = {"build": function, "module": module, "subskills": tuple(subskills)}
        return function
    return register


def _rng(name, role, index, subskill):
    seed = hashlib.sha256(f"aurora-professor\x1f{name}\x1f{role}\x1f{subskill}\x1f{index}".encode()).digest()
    return random.Random(int.from_bytes(seed[:8], "big"))


def _exam(role):
    return role in ("diagnostic", "gate") or role.startswith("gate")


def _pick(rng, role, train, exam):
    """Vocabulary is split by role; an exam never reuses a training surface form."""
    return rng.choice(exam if _exam(role) else train)


def generate(name, role, index, subskill=None):
    """Build item ``index`` of a family for a role namespace (e.g. ``train``, ``gate:3``)."""
    spec = FAMILIES[name]
    rng0 = _rng(name, role, index, "")
    subskill = subskill or spec["subskills"][rng0.randrange(len(spec["subskills"]))]
    if subskill not in spec["subskills"]:
        raise ValueError(f"Unknown subskill {subskill} for {name}")
    rng = _rng(name, role, index, subskill)
    built = spec["build"](rng, role, subskill)
    item = {"id": f"gen:{name}:{role}:{subskill}:{index}", "module": spec["module"], "skill": name,
            "subskill": subskill, "lang": built.get("lang", "fr"),
            "messages": built["messages"], "target": built["target"], "grader": built["grader"],
            "max_new_tokens": built.get("max_new_tokens", 96), "source": "generator",
            "question_hash": question_hash(built["messages"][-1]["content"])}
    return item


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _pretty(value):
    return json.dumps(value, ensure_ascii=False, indent=1)


# --- shared receipt material ----------------------------------------------

_TITLES = {"train": ["Tableau de bord Aurora", "Atelier 3D", "Console des missions", "Journal du bridge",
                     "Bibliothèque de modèles", "Suivi des impressions", "Paramètres du tunnel"],
           "exam": ["Studio d'animation", "Rapport de calcul", "Inventaire des pièces", "Centre de contrôle",
                    "Archives des livraisons", "Banc de mesure", "Carnet de fabrication"]}
_LABELS = {"train": ["Nouveau projet", "Générer", "Importer un fichier", "Paramètres", "Historique", "Exporter",
                     "Valider", "Annuler", "Ouvrir le viewer", "Relancer"],
           "exam": ["Créer une scène", "Lancer le rendu", "Charger un maillage", "Préférences", "Journal",
                    "Télécharger", "Confirmer", "Fermer", "Afficher les coupes", "Reprendre"]}
_HOSTS = {"train": ["127.0.0.1:1420", "127.0.0.1:3001", "localhost:8188", "atelier.local:3009"],
          "exam": ["127.0.0.1:3002", "localhost:11435", "studio.local:4173", "banc.local:8080"]}
_GPUS = {"train": ["RTX 5070 Ti", "Tesla T4", "RTX 4090", "A100-SXM4-40GB"],
         "exam": ["RTX PRO 6000", "L4", "RTX 3060", "H100"]}
_FILES = {"train": ["src/main.py", "config/models.json", "docs/notes.md", "data/pieces.csv", "scripts/export.sh"],
          "exam": ["lib/solver.py", "etc/tunnel.yaml", "rapports/bilan.md", "mesures/coupes.csv", "bin/rendu.sh"]}
_SERVERS = {"train": ["aurora-core", "aurora-3d", "aurora-code"], "exam": ["aurora-image", "aurora-learning", "aurora-cowork"]}
_ODD_KEYS = {"train": ["content-type", "application/json", "x~trace", "a/b", "src/main.py", "cache~1", "taux %"],
             "exam": ["accept-language", "text/html", "y~span", "c/d", "lib/solver.py", "store~0", "débit max"]}


def _vocab(rng, role, table):
    return rng.choice(table["exam" if _exam(role) else "train"])


def _evidence_id(rng):
    return "ev_" + "".join(rng.choice("0123456789abcdef") for _ in range(10))


def _browser_receipt(rng, role, ok=True):
    labels = rng.sample(_LABELS["exam" if _exam(role) else "train"], 4)
    elements = [{"ref": f"e{n}", "role": rng.choice(["button", "link", "tab"]), "name": label,
                 "visible_text": label} for n, label in enumerate(labels, start=rng.randint(1, 20))]
    title = _vocab(rng, role, _TITLES)
    return {"id": _evidence_id(rng), "tool": "browser_action", "ok": ok, "action_number": rng.randint(2, 30),
            "result": {"session_id": "s" + str(rng.randint(100, 999)), "observation_id": "o" + str(rng.randint(1000, 9999)),
                       "url": "http://" + _vocab(rng, role, _HOSTS) + rng.choice(["/", "/projets", "/missions", "/etat"]),
                       "title": title, "text": title + " " + " ".join(labels), "elements": elements}}


def _compute_receipt(rng, role, ok=True):
    workers = rng.randint(0, 3)
    return {"id": _evidence_id(rng), "tool": "read_mcp_resource", "ok": ok, "action_number": rng.randint(2, 30),
            "result": {"server": _vocab(rng, role, _SERVERS), "uri": "aurora://runtime/compute",
                       "contents": [{"uri": "aurora://runtime/compute", "mimeType": "application/json",
                                     "data": {"connected_workers": workers,
                                              "gpu": {"name": _vocab(rng, role, _GPUS),
                                                      "free_vram_gb": round(rng.uniform(2, 90), 2)},
                                              "available_ram_gb": round(rng.uniform(4, 60), 2),
                                              "queue": [{"job": "j" + str(rng.randint(10, 99)), "state": rng.choice(["attente", "actif"])}
                                                        for _ in range(rng.randint(1, 3))]}}]}}


def _file_receipt(rng, role, ok=True):
    path = _vocab(rng, role, _FILES)
    return {"id": _evidence_id(rng), "tool": "read_file", "ok": ok, "action_number": rng.randint(2, 30),
            "result": {"path": path, "encoding": "utf-8", "lines": rng.randint(8, 900),
                       "sha256": "".join(rng.choice("0123456789abcdef") for _ in range(16)),
                       "headers": {rng.choice(_ODD_KEYS["exam" if _exam(role) else "train"]): rng.choice(["oui", "non", "42", "v2"]),
                                   "taille": rng.randint(100, 90000)}}}


def _csv_receipt(rng, role, ok=True):
    columns = rng.sample(["quantite", "masse_g", "duree_s", "cout_centimes", "longueur_mm", "pieces"], 3)
    return {"id": _evidence_id(rng), "tool": "inspect_csv", "ok": ok, "action_number": rng.randint(2, 30),
            "result": {"path": _vocab(rng, role, _FILES).rsplit(".", 1)[0] + ".csv", "rows": rng.randint(3, 400),
                       "columns": columns, "sums": {c: rng.randint(10, 99999) for c in columns}}}


_RECEIPTS = (_browser_receipt, _compute_receipt, _file_receipt, _csv_receipt)


def _leaves(value, path=""):
    if isinstance(value, dict):
        for key, child in value.items():
            token = str(key).replace("~", "~0").replace("/", "~1")
            yield from _leaves(child, f"{path}/{token}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _leaves(child, f"{path}/{index}")
    else:
        yield path, value


# --- mission.pointer -------------------------------------------------------

_POINTER_PROMPTS = {
    "train": ["Voici un reçu d'outil conservé par la mission :\n{doc}\n\nDonne le pointeur JSON RFC 6901, depuis la racine du reçu, du champ dont la valeur est exactement {value}. Réponds uniquement par le pointeur.",
              "Reçu :\n{doc}\n\nQuel pointeur RFC 6901 (depuis la racine) désigne la valeur {value} ? Écris seulement le pointeur, sans guillemets ni commentaire.",
              "Receipt:\n{doc}\n\nGive the RFC 6901 JSON pointer, from the receipt root, of the field whose value is exactly {value}. Answer with the pointer only."],
    "exam": ["Un outil a retourné ce reçu complet :\n{doc}\n\nÀ quel emplacement se trouve la valeur {value} ? Exprime-le comme pointeur JSON (RFC 6901) partant de la racine. Aucune autre sortie.",
             "Complete tool receipt:\n{doc}\n\nWrite the JSON pointer (RFC 6901, rooted at the receipt) that selects the value {value}. Output the pointer alone."],
}


@family("mission.pointer", "missions", ("plain", "array_index", "escape", "deep"))
def _pointer(rng, role, subskill):
    for _ in range(200):
        maker = {"plain": rng.choice([_csv_receipt, _file_receipt]), "array_index": rng.choice([_browser_receipt, _compute_receipt]),
                 "escape": _file_receipt, "deep": _compute_receipt}[subskill]
        receipt = maker(rng, role)
        leaves = list(_leaves(receipt))
        values = [json.dumps(v, sort_keys=True) for _, v in leaves]
        unique = [(p, v) for p, v in leaves if values.count(json.dumps(v, sort_keys=True)) == 1 and not isinstance(v, bool) and v is not None]

        def fits(path):
            parts = path.split("/")[1:]
            has_index = any(part.isdigit() for part in parts)
            escaped = "~" in path
            if subskill == "escape":
                return escaped
            if subskill == "array_index":
                return has_index and not escaped
            if subskill == "deep":
                return len(parts) >= 5 and not escaped
            return not has_index and not escaped and len(parts) <= 3
        candidates = [(p, v) for p, v in unique if fits(p)]
        if candidates:
            path, value = rng.choice(candidates)
            prompt = _pick(rng, role, _POINTER_PROMPTS["train"], _POINTER_PROMPTS["exam"])
            lang = "en" if prompt.startswith(("Receipt", "Complete")) else "fr"
            return {"messages": [{"role": "user", "content": prompt.format(doc=_pretty(receipt), value=_json(value))}],
                    "target": path, "lang": lang, "max_new_tokens": 64,
                    "grader": {"type": "pointer", "document": receipt, "value": value, "pointers": [path]}}
    raise RuntimeError("Could not build a pointer exercise")


# --- mission.evidence ------------------------------------------------------

_EVIDENCE_PROMPTS = {
    "train": ["Fichier sauvegardé `{path}` :\n{saved}\n\nReçus conservés par la mission :\n{receipts}\n\n{quantity}Produis l'unique action JSON `verify` avec un contrôle `json_evidence` sur `{path}` : chaque champ du fichier doit être lié par `path`, `evidence_id` et `source_pointer` (pointeurs RFC 6901 depuis la racine du reçu complet) à un reçu d'observation réussi. Réponds uniquement par l'objet JSON {{\"tool\":\"verify\",\"args\":{{...}}}}.",
              "Saved file `{path}`:\n{saved}\n\nReceipts retained by this mission:\n{receipts}\n\n{quantity}Output the single JSON action `verify` holding one `json_evidence` check on `{path}`. Bind every field of the file with `path`, `evidence_id` and `source_pointer` (RFC 6901 pointers from the complete receipt root) to a successful observation receipt. Answer with the JSON object only."],
    "exam": ["La mission a écrit `{path}` avec ce contenu :\n{saved}\n\nElle dispose de ces reçus :\n{receipts}\n\n{quantity}Rédige l'action de vérification (outil `verify`, un seul contrôle de type `json_evidence` visant `{path}`) qui rattache tous les champs du fichier aux observations réelles. Utilise des pointeurs RFC 6901 complets. Sortie : un seul objet JSON, rien d'autre.",
             "The mission saved `{path}`:\n{saved}\n\nAvailable receipts:\n{receipts}\n\n{quantity}Write the verification action (tool `verify`, exactly one `json_evidence` check for `{path}`) grounding all fields of the file in actual observations, using full RFC 6901 pointers. Output one JSON object and nothing else."],
}
_QUANTITY = {"fr": "Le critère exige exactement {n} libellés : ajoute une expression qui contrôle cette quantité sur le fichier sauvegardé.\n\n",
             "en": "The criterion demands exactly {n} labels: add an expression that checks this quantity on the saved file.\n\n"}


@family("mission.evidence", "missions", ("single_receipt", "two_receipts", "distractors", "quantity"))
def _evidence(rng, role, subskill):
    browser, compute = _browser_receipt(rng, role), _compute_receipt(rng, role)
    data = compute["result"]["contents"][0]["data"]
    saved, bindings = {}, []

    def bind(field, receipt, source):
        from agi_core.json_evidence import pointer
        saved_value = pointer(receipt, source)
        bindings.append({"path": field, "evidence_id": receipt["id"], "source_pointer": source})
        return saved_value
    labels = rng.sample(range(len(browser["result"]["elements"])), 2 if subskill != "single_receipt" else 1)
    saved["url"] = bind("/url", browser, "/result/url")
    saved["title"] = bind("/title", browser, "/result/title")
    if subskill == "single_receipt":
        saved["label"] = bind("/label", browser, f"/result/elements/{labels[0]}/visible_text")
    else:
        saved["visible_labels"] = [bind(f"/visible_labels/{n}", browser, f"/result/elements/{i}/visible_text")
                                   for n, i in enumerate(labels)]
        saved["connected_workers"] = bind("/connected_workers", compute, "/result/contents/0/data/connected_workers")
        saved["gpu"] = bind("/gpu", compute, "/result/contents/0/data/gpu/name")
    receipts = [browser] if subskill == "single_receipt" else [browser, compute]
    path = _pick(rng, role, ["diagnostic.json", "etat.json", "rapport.json"], ["bilan.json", "observation.json", "controle.json"])
    if subskill in ("distractors", "quantity"):
        failed = _browser_receipt(rng, role, ok=False)
        failed["result"]["title"] = saved["title"]          # tempting but not a successful observation
        written = {"id": _evidence_id(rng), "tool": "write_file", "ok": True, "action_number": 40,
                   "result": {"path": path, "bytes": 220, "content": saved}}
        receipts += [failed, written]
    rng.shuffle(receipts)
    grader = {"type": "evidence", "path": path, "saved": saved, "receipts": {r["id"]: r for r in receipts},
              "required_paths": [p for p, _ in _leaves(saved)]}
    check = {"kind": "json_evidence", "path": path, "bindings": bindings}
    prompt = _pick(rng, role, _EVIDENCE_PROMPTS["train"], _EVIDENCE_PROMPTS["exam"])
    lang = "en" if prompt.startswith(("Saved file", "The mission")) else "fr"
    quantity = ""
    if subskill == "quantity":
        count = len(saved["visible_labels"])
        check["expressions"] = [f'len(data["visible_labels"]) == {count}']
        grader["quantity_counterexamples"] = [{**saved, "visible_labels": saved["visible_labels"][:1]},
                                              {**saved, "visible_labels": saved["visible_labels"] + ["x"]}]
        quantity = _QUANTITY[lang].format(n=count)
    target = {"tool": "verify", "args": {"checks": [check]}}
    return {"messages": [{"role": "user", "content": prompt.format(path=path, saved=_pretty(saved), quantity=quantity,
                                                                 receipts="\n".join(_json(r) for r in receipts))}],
            "target": _json(target), "grader": grader, "lang": lang, "max_new_tokens": 560}


# --- mission.action --------------------------------------------------------

def _tool_card(names):
    from agi_core.mission_protocol import ARG_SCHEMAS, TOOL_DESCRIPTIONS
    lines = []
    for name in names:
        schema = {k: v for k, v in ARG_SCHEMAS[name].items() if k in ("properties", "required")}
        lines.append(f"- {name}: {TOOL_DESCRIPTIONS.get(name, '')}\n  args: {_json(schema)}")
    return "\n".join(lines)


_ACTION_PROMPTS = {
    "train": ["Outils disponibles :\n{tools}\n\nSituation : {situation}\n\nDonne la prochaine action sous la forme d'un unique objet JSON {{\"tool\":...,\"args\":{{...}}}}. N'ajoute aucun argument facultatif non demandé ni aucun texte.",
              "Available tools:\n{tools}\n\nSituation: {situation}\n\nReturn the next action as exactly one JSON object {{\"tool\":...,\"args\":{{...}}}}. No optional argument that was not requested, no prose."],
    "exam": ["Tu pilotes une mission. Contrats des outils :\n{tools}\n\n{situation}\n\nQuelle action exécutes-tu maintenant ? Un seul objet JSON avec les clés `tool` et `args`, sans commentaire et sans argument superflu.",
             "You are running a mission. Tool contracts:\n{tools}\n\n{situation}\n\nWhich action do you execute now? One JSON object with keys `tool` and `args`, no commentary, no superfluous argument."],
}


@family("mission.action", "missions", ("read_resource", "browser_open", "browser_click", "browser_fill", "browser_close",
                                       "read_file", "search_code", "inspect_evidence", "catalog"))
def _action(rng, role, subskill):
    exam = _exam(role)
    server = _vocab(rng, role, _SERVERS)
    observation = _browser_receipt(rng, role)["result"]
    session, obs = observation["session_id"], observation["observation_id"]
    element = rng.choice(observation["elements"])
    listing = _json([{k: e[k] for k in ("ref", "role", "visible_text")} for e in observation["elements"]])
    fr = rng.random() < 0.7
    if subskill == "read_resource":
        uri = rng.choice(["aurora://runtime/compute", "aurora://runtime/ratchet", "aurora://capabilities"] if not exam
                         else ["aurora://runtime/queue", "aurora://runtime/models", "aurora://capabilities/tools"])
        situation = (f"Le catalogue du serveur MCP `{server}` liste la ressource `{uri}`. Tu dois lire son contenu." if fr
                     else f"The catalog of MCP server `{server}` lists the resource `{uri}`. You must read its content.")
        expected, pool = {"tool": "read_mcp_resource", "args": {"server": server, "uri": uri}}, ["read_mcp_resource", "mcp_catalog", "call_mcp_tool", "fetch_url"]
    elif subskill == "browser_open":
        url = "http://" + _vocab(rng, role, _HOSTS) + "/"
        situation = (f"Aucune session navigateur n'est ouverte. Ouvre la page {url}." if fr
                     else f"No browser session is open. Open the page {url}.")
        expected, pool = {"tool": "browser_action", "args": {"action": "open", "url": url}}, ["browser_action", "fetch_url", "inspect_browser", "search_web"]
    elif subskill == "browser_click":
        situation = (f"Session `{session}`, dernière observation `{obs}`. Éléments observés : {listing}. Clique sur « {element['visible_text']} »." if fr
                     else f"Session `{session}`, latest observation `{obs}`. Observed elements: {listing}. Click on \"{element['visible_text']}\".")
        expected = {"tool": "browser_action", "args": {"action": "click", "session_id": session, "observation_id": obs, "ref": element["ref"]}}
        pool = ["browser_action", "inspect_browser", "run_command", "fetch_url"]
    elif subskill == "browser_fill":
        value = rng.choice(["vélo cargo", "support moteur", "rapport hebdomadaire"] if not exam else ["cadre acier", "carter imprimé", "bilan mensuel"])
        situation = (f"Session `{session}`, dernière observation `{obs}`. Éléments observés : {listing}. Saisis « {value} » dans l'élément `{element['ref']}`." if fr
                     else f"Session `{session}`, latest observation `{obs}`. Observed elements: {listing}. Type \"{value}\" into element `{element['ref']}`.")
        expected = {"tool": "browser_action", "args": {"action": "fill", "session_id": session, "observation_id": obs, "ref": element["ref"], "value": value}}
        pool = ["browser_action", "write_file", "inspect_browser", "run_command"]
    elif subskill == "browser_close":
        situation = (f"Le travail dans le navigateur est terminé. La session ouverte est `{session}`. Libère-la." if fr
                     else f"The browser work is finished. The open session is `{session}`. Release it.")
        expected, pool = {"tool": "browser_action", "args": {"action": "close", "session_id": session}}, ["browser_action", "close_mcp_session", "finish", "inspect_browser"]
    elif subskill == "read_file":
        path = _vocab(rng, role, _FILES)
        situation = (f"Tu dois lire le fichier texte `{path}` du workspace avant de le modifier." if fr
                     else f"You must read the workspace text file `{path}` before changing it.")
        expected, pool = {"tool": "read_file", "args": {"path": path}}, ["read_file", "inspect_path", "list_files", "inspect_csv"]
    elif subskill == "search_code":
        query = rng.choice(["def compare_evidence", "TODO", "class LLMGateway"] if not exam else ["def plan_compute", "FIXME", "class MissionStore"])
        folder = rng.choice(["agi_core", "auto_rl"] if not exam else ["application", "mcp"])
        situation = (f"Cherche la chaîne littérale `{query}` dans le dossier `{folder}`." if fr
                     else f"Search for the literal string `{query}` in folder `{folder}`.")
        expected, pool = {"tool": "search_code", "args": {"query": query, "path": folder}}, ["search_code", "read_file", "list_files", "search_web"]
    elif subskill == "inspect_evidence":
        evidence = _evidence_id(rng)
        sub = rng.choice(["/result", "/result/elements", "/result/contents/0"])
        situation = (f"Avant d'écrire des liaisons, inspecte le reçu conservé `{evidence}` à partir du pointeur `{sub}`." if fr
                     else f"Before writing bindings, inspect the retained receipt `{evidence}` starting at pointer `{sub}`.")
        expected, pool = {"tool": "inspect_evidence", "args": {"evidence_id": evidence, "pointer": sub}}, ["inspect_evidence", "read_file", "verify", "inspect_runtime"]
    else:
        kind = rng.choice(["tools", "resources", "prompts", "resource_templates"])
        noun = {"tools": ("outils", "tools"), "resources": ("ressources", "resources"), "prompts": ("prompts", "prompts"),
                "resource_templates": ("modèles de ressources", "resource templates")}[kind]
        situation = (f"Tu ne connais pas encore les {noun[0]} du serveur MCP `{server}`. Lis la première page de ce catalogue." if fr
                     else f"You do not know the {noun[1]} of MCP server `{server}` yet. Read the first page of that catalog.")
        expected, pool = {"tool": "mcp_catalog", "args": {"server": server, "kind": kind}}, ["mcp_catalog", "list_mcp_tools", "read_mcp_resource", "list_tools"]
    rng.shuffle(pool)
    templates = _ACTION_PROMPTS["exam" if exam else "train"]
    prompt = templates[0] if fr else templates[1]
    return {"messages": [{"role": "user", "content": prompt.format(tools=_tool_card(pool), situation=situation)}],
            "target": _json(expected), "grader": {"type": "mission_action", "accept": [expected]},
            "lang": "fr" if fr else "en", "max_new_tokens": 180}


# --- mission.grounded_report ----------------------------------------------

_REPORT_PROMPTS = {
    "train": ["Reçus réellement observés :\n{receipts}\n\nRemplis ce rapport JSON avec exactement les clés {keys}. Une valeur qui n'apparaît dans aucun reçu doit valoir null : n'invente rien. Réponds uniquement par l'objet JSON.",
              "Actually observed receipts:\n{receipts}\n\nFill this JSON report with exactly the keys {keys}. A value that appears in no receipt must be null: invent nothing. Answer with the JSON object only."],
    "exam": ["Observations disponibles :\n{receipts}\n\nÉcris le compte rendu JSON dont les clés sont exactement {keys}. Toute information non observée vaut null. Sortie : l'objet JSON seul.",
             "Available observations:\n{receipts}\n\nWrite the JSON report whose keys are exactly {keys}. Any unobserved information is null. Output the JSON object alone."],
}
_REPORT_FIELDS = {
    "page_title": ("browser", lambda r: r["result"]["title"]),
    "page_url": ("browser", lambda r: r["result"]["url"]),
    "connected_workers": ("compute", lambda r: r["result"]["contents"][0]["data"]["connected_workers"]),
    "gpu_name": ("compute", lambda r: r["result"]["contents"][0]["data"]["gpu"]["name"]),
    "free_vram_gb": ("compute", lambda r: r["result"]["contents"][0]["data"]["gpu"]["free_vram_gb"]),
    "available_ram_gb": ("compute", lambda r: r["result"]["contents"][0]["data"]["available_ram_gb"]),
    "csv_rows": ("csv", lambda r: r["result"]["rows"]),
    "csv_path": ("csv", lambda r: r["result"]["path"]),
    "file_lines": ("file", lambda r: r["result"]["lines"]),
    "file_path": ("file", lambda r: r["result"]["path"]),
}


@family("mission.grounded_report", "missions", ("all_observed", "some_missing", "mostly_missing"))
def _report(rng, role, subskill):
    makers = {"browser": _browser_receipt, "compute": _compute_receipt, "csv": _csv_receipt, "file": _file_receipt}
    present = {"all_observed": 4, "some_missing": rng.choice([2, 3]), "mostly_missing": 1}[subskill]
    kinds = rng.sample(sorted(makers), present)
    receipts = {kind: makers[kind](rng, role) for kind in kinds}
    wanted = rng.sample(sorted(_REPORT_FIELDS), 6 if subskill != "all_observed" else 5)
    if subskill == "all_observed":
        wanted = [f for f in sorted(_REPORT_FIELDS) if _REPORT_FIELDS[f][0] in receipts]
        wanted = rng.sample(wanted, min(5, len(wanted)))
    report = {f: (_REPORT_FIELDS[f][1](receipts[_REPORT_FIELDS[f][0]]) if _REPORT_FIELDS[f][0] in receipts else None) for f in wanted}
    if subskill != "all_observed" and all(v is not None for v in report.values()):
        missing = next(f for f in sorted(_REPORT_FIELDS) if _REPORT_FIELDS[f][0] not in receipts)
        report[missing] = None
    keys = list(report)
    rng.shuffle(keys)
    report = {k: report[k] for k in keys}
    templates = _REPORT_PROMPTS["exam" if _exam(role) else "train"]
    fr = rng.random() < 0.7
    shown = list(receipts.values())
    rng.shuffle(shown)
    return {"messages": [{"role": "user", "content": (templates[0] if fr else templates[1]).format(
                receipts="\n".join(_json(r) for r in shown), keys=_json(keys))}],
            "target": _json(report), "grader": {"type": "json", "accept": [report]},
            "lang": "fr" if fr else "en", "max_new_tokens": 260}
