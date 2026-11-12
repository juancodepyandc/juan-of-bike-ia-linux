"""Public datasets turned into training pools and exam families.

Every source declares where it comes from, its licence, the split it uses and
its role. ``train`` sources feed the curriculum; ``exam`` sources are split
deterministically into a steering part (diagnostic) and a verification reserve
(gate) and are never shown to the trainer. A source with only one public split
is divided by a stable hash of its rows (``split_share``).

Prompt wording differs between training and exam on purpose: a model that only
memorised a training template gains nothing on the exam.
"""
from __future__ import annotations

import json
import random
import re

from .graders import LETTERS, run_sql, parse_numbers
from .records import bucket, exam_role, question_hash

SOURCES = {}


def source(name, *, dataset, config=None, split, role, skill, module, license, lang="en", cap=None,
           split_share=None, files=None, streaming=False, parquet=False):
    """Register one dataset split. ``role`` is ``train`` or ``exam``.

    ``parquet`` reads the Hub's converted Parquet branch, for repositories that
    still ship a loading script (no longer executed by ``datasets``).
    """
    def register(function):
        SOURCES[name] = {"name": name, "dataset": dataset, "config": config, "split": split, "role": role,
                         "skill": skill, "module": module, "license": license, "lang": lang, "cap": cap,
                         "split_share": split_share, "files": files, "streaming": streaming, "parquet": parquet,
                         "adapt": function}
        return function
    return register


# --- prompt wording --------------------------------------------------------

_MCQ = {
    ("train", "fr"): ["{q}\n\n{o}\n\nRéponds uniquement par la lettre de la bonne réponse.",
                      "Question : {q}\nChoix :\n{o}\nIndique seulement la lettre correcte."],
    ("train", "en"): ["{q}\n\n{o}\n\nAnswer with the letter of the correct option only.",
                      "Question: {q}\nOptions:\n{o}\nGive just the letter of the right answer."],
    ("exam", "fr"): ["Voici une question à choix multiples.\n\n{q}\n\n{o}\n\nQuelle est la bonne réponse ? Donne uniquement la lettre correspondante."],
    ("exam", "en"): ["The following is a multiple choice question.\n\n{q}\n\n{o}\n\nWhich option is correct? Reply with its letter and nothing else."],
}
_MATH = {
    ("train", "en"): ["{q}\n\nSolve step by step, then end with a line \"Final answer: <number>\".",
                      "{q}\n\nShow your reasoning and finish with \"Final answer: <number>\"."],
    ("exam", "en"): ["Solve the following problem.\n\n{q}\n\nExplain briefly, and write the result on a last line of the form \"Final answer: <number>\"."],
}
_LATEX = {
    ("train", "en"): ["{q}\n\nSolve the problem and give the final answer inside \\boxed{{}}."],
    ("exam", "en"): ["Problem:\n{q}\n\nWork it out, then state the final result as \\boxed{{...}}."],
}


def _side(role):
    return "train" if role == "train" else "exam"


def _rng(key):
    return random.Random(bucket(key, "aurora-source-rng", 2 ** 62))


def _mcq(key, role, lang, question, options, answer_index, *, shuffle=None):
    """Build one multiple-choice item. Training options are shuffled to remove position cues."""
    options = [str(o).strip() for o in options]
    if not question or len(options) < 2 or len(options) > len(LETTERS) or not 0 <= answer_index < len(options) or any(not o for o in options):
        return None
    rng = _rng(key)
    order = list(range(len(options)))
    if shuffle if shuffle is not None else role == "train":
        rng.shuffle(order)
    shown = [options[i] for i in order]
    letter = LETTERS[order.index(answer_index)]
    body = "\n".join(f"{LETTERS[i]}. {text}" for i, text in enumerate(shown))
    template = rng.choice(_MCQ[(_side(role), lang)])
    return {"messages": [{"role": "user", "content": template.format(q=question.strip(), o=body)}],
            "target": letter, "grader": {"type": "mcq", "answer": letter, "options": len(shown)},
            "max_new_tokens": 8, "question": question}


def _plain(messages, target, grader, tokens, question):
    return {"messages": messages, "target": target, "grader": grader, "max_new_tokens": tokens, "question": question}


def _user(text):
    return [{"role": "user", "content": text}]


# --- knowledge and reasoning ----------------------------------------------

@source("mmlu_test", dataset="cais/mmlu", config="all", split="test", role="exam", skill="academy.knowledge", module="academy", license="mit")
@source("mmlu_aux_train", dataset="cais/mmlu", config="all", split="auxiliary_train", role="train", skill="academy.knowledge", module="academy", license="mit", cap=12000)
def _mmlu(row, key, role):
    item = _mcq(key, role, "en", row["question"], row["choices"], int(row["answer"]))
    if item:
        item["subskill"] = row.get("subject") or "auxiliary"
    return item


@source("mmmlu_fr", dataset="openai/MMMLU", config="FR_FR", split="test", role="exam", skill="conversation.knowledge_fr", module="conversation", license="mit", lang="fr")
def _mmmlu(row, key, role):
    answer = str(row["Answer"]).strip().upper()
    if answer not in "ABCD" or len(answer) != 1:
        return None
    item = _mcq(key, role, "fr", str(row["Question"]), [row["A"], row["B"], row["C"], row["D"]], "ABCD".index(answer))
    if item:
        item["subskill"] = row["Subject"]
    return item


@source("global_mmlu_fr_dev", dataset="CohereLabs/Global-MMLU", config="fr", split="dev", role="train", skill="conversation.knowledge_fr", module="conversation", license="apache-2.0", lang="fr")
def _global_mmlu(row, key, role):
    answer = str(row["answer"]).strip().upper()
    if answer not in "ABCD" or len(answer) != 1:
        return None
    item = _mcq(key, role, "fr", row["question"], [row["option_a"], row["option_b"], row["option_c"], row["option_d"]], "ABCD".index(answer))
    if item:
        item["subskill"] = row["subject"]
    return item


@source("mmlu_pro", dataset="TIGER-Lab/MMLU-Pro", split="test", role="exam", skill="academy.knowledge_pro", module="academy", license="mit")
def _mmlu_pro(row, key, role):
    options = [o for o in row["options"] if str(o).strip() and str(o).strip().upper() != "N/A"]
    if len(options) != len(row["options"]):
        return None
    item = _mcq(key, role, "en", row["question"], options, int(row["answer_index"]))
    if item:
        item["subskill"] = row["category"]
    return item


@source("sciq_train", dataset="allenai/sciq", split="train", role="train", skill="academy.science", module="academy", license="cc-by-nc-3.0", cap=6000)
@source("sciq_test", dataset="allenai/sciq", split="test", role="exam", skill="academy.science", module="academy", license="cc-by-nc-3.0")
def _sciq(row, key, role):
    options = [row["correct_answer"], row["distractor1"], row["distractor2"], row["distractor3"]]
    order = list(range(4))
    _rng(key + ":layout").shuffle(order)          # the dataset stores the answer first
    item = _mcq(key, role, "en", row["question"], [options[i] for i in order], order.index(0), shuffle=False)
    if item:
        item["subskill"] = "sciq"
    return item


@source("arc_train", dataset="allenai/ai2_arc", config="ARC-Challenge", split="train", role="train", skill="academy.science", module="academy", license="cc-by-sa-4.0")
@source("arc_test", dataset="allenai/ai2_arc", config="ARC-Challenge", split="test", role="exam", skill="academy.science", module="academy", license="cc-by-sa-4.0")
@source("openbookqa_train", dataset="allenai/openbookqa", config="main", split="train", role="train", skill="academy.science", module="academy", license="unknown")
@source("openbookqa_test", dataset="allenai/openbookqa", config="main", split="test", role="exam", skill="academy.science", module="academy", license="unknown")
@source("commonsense_train", dataset="tau/commonsense_qa", split="train", role="train", skill="academy.commonsense", module="academy", license="mit", cap=6000)
@source("commonsense_val", dataset="tau/commonsense_qa", split="validation", role="exam", skill="academy.commonsense", module="academy", license="mit")
def _labelled_choices(row, key, role):
    labels, texts = list(row["choices"]["label"]), list(row["choices"]["text"])
    if row["answerKey"] not in labels:
        return None
    item = _mcq(key, role, "en", row.get("question") or row.get("question_stem"), texts, labels.index(row["answerKey"]))
    if item:
        item["subskill"] = "arc" if "Mercury" in key or "arc" in key else ("openbookqa" if "openbook" in key else "commonsense")
    return item


@source("medqa_train", dataset="GBaker/MedQA-USMLE-4-options", split="train", role="train", skill="academy.medicine", module="academy", license="cc-by-4.0", cap=6000)
@source("medqa_test", dataset="GBaker/MedQA-USMLE-4-options", split="test", role="exam", skill="academy.medicine", module="academy", license="cc-by-4.0")
def _medqa(row, key, role):
    labels = sorted(row["options"])
    if row["answer_idx"] not in labels:
        return None
    item = _mcq(key, role, "en", row["question"], [row["options"][l] for l in labels], labels.index(row["answer_idx"]))
    if item:
        item["subskill"] = row.get("meta_info") or "usmle"
    return item


@source("belebele_fr", dataset="facebook/belebele", config="fra_Latn", split="test", role="exam", skill="conversation.reading_fr", module="conversation", license="cc-by-sa-4.0", lang="fr")
def _belebele(row, key, role):
    question = f"Texte : {row['flores_passage'].strip()}\n\nQuestion : {row['question'].strip()}"
    item = _mcq(key, role, "fr", question, [row[f"mc_answer{i}"] for i in range(1, 5)], int(row["correct_answer_num"]) - 1)
    if item:
        item["subskill"] = "belebele"
    return item


_BBH = ["compréhension_de_la_date", "compréhension_des_sports", "comptage_d_objets", "dyck_languages",
        "déduction_logique_cinq_objets", "déduction_logique_sept_objets", "déduction_logique_trois_objets",
        "désambiguïsation_qa", "détection_d_erreur_de_traduction_sailante", "expressions_booléennes",
        "formes_géométriques", "hyperbate", "jugement_causal", "multistep_arithmetic_two", "naviguer",
        "noms_de_ruines", "pingouins_sur_une_table", "raisonnement_sur_les_objets_colorés", "recommandation_de_film",
        "sarcasmes", "sophismes_formels", "suivi_objets_mélangés_cinq_objets", "suivi_objets_mélangés_sept_objets",
        "suivi_objets_mélangés_trois_objets", "séquences_temporelles", "toile_de_mensonges", "tri_de_mots"]


#: Equivalent answers of the yes/no and true/false tasks (the French translation mixes "Vrai" and "Incorrect").
_BBH_SYNONYMS = [{"oui", "yes"}, {"non", "no"}, {"vrai", "true", "correct"}, {"faux", "false", "incorrect"}]
_BBH_NUMERIC = {"comptage_d_objets", "multistep_arithmetic_two"}


def _edit_distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        previous, row[0] = row[0], i
        for j, y in enumerate(b, 1):
            previous, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, previous + (x != y))
    return row[-1]


def _bbh(config):
    """BBH in French. Items whose reference no correct answer can match are kept in the layout (so the
    slices of other cycles do not move) but marked ``unusable`` and left out of every exam."""
    def adapt(row, key, role):
        target = str(row["target"]).strip()
        if not target:
            return None
        text = row["input"]
        letters = sorted(set(re.findall(r"\(([A-Z])\)", text)))
        choice = re.fullmatch(r"\(([A-Z])\)", target)
        unusable = None
        if choice and choice.group(1) in letters:
            # Options are not always at the start of a line: a letter target is a multiple-choice answer.
            grader = {"type": "mcq", "answer": choice.group(1), "options": len(LETTERS[:LETTERS.index(letters[-1]) + 1])}
            ask = "Réponds uniquement par la lettre de l'option correcte."
        elif config in _BBH_NUMERIC and parse_numbers(target):
            grader = {"type": "numeric", "answer": target}
            ask = "Réponds uniquement par le nombre final, sans explication."
        else:
            offered = [line.strip()[2:].strip() for line in text.splitlines() if re.match(r"^\s*-\s+\S", line)]
            if offered and target not in offered:
                close = [option for option in offered if _edit_distance(option.casefold(), target.casefold()) <= 2]
                if len(set(close)) == 1:
                    target = close[0]                      # "invalidee" for the offered option "invalide"
                else:
                    unusable = "reference_not_offered"
            answers = sorted(next((group for group in _BBH_SYNONYMS if target.casefold() in group), {target}))
            if config == "tri_de_mots":
                listed = text.rsplit(":", 1)[-1].split()
                if sorted(listed) != target.split():
                    unusable = "reference_is_not_the_sorted_list"
            grader = {"type": "text", "answers": answers, "literal": True}
            ask = "Réponds uniquement par la réponse finale, sans explication."
        item = _plain(_user(f"{text.strip()}\n\n{ask}"), target, grader, 24 if config != "tri_de_mots" else 96, text)
        item["subskill"] = config
        if unusable:
            item["unusable"] = unusable
        return item
    return adapt


for _config in _BBH:
    source("bbh_fr_" + _config, dataset="le-leadboard/bbh-fr", config=_config, split="test", role="exam",
           skill="conversation.reasoning_fr", module="conversation", license="apache-2.0", lang="fr")(_bbh(_config))


def _translation(row, key, role):
    pair = row["translation"]
    english, french = pair["en"].strip(), pair["fr"].strip()
    if not 20 <= len(english) <= 400 or not 20 <= len(french) <= 500:
        return None
    to_french = bucket(key, "direction", 2) == 0
    source_text, reference = (english, french) if to_french else (french, english)
    if role == "train":
        ask = (f"Traduis en français :\n{source_text}" if to_french else f"Translate into English:\n{source_text}")
    else:
        ask = (f"Donne la traduction française fidèle de ce texte, sans commentaire.\n\n{source_text}" if to_french
               else f"Provide a faithful English translation of this text, with no commentary.\n\n{source_text}")
    item = _plain(_user(ask), reference, {"type": "chrf", "references": [reference], "threshold": 0.55},
                  min(260, 40 + len(reference) // 2), source_text)
    item["subskill"] = "en_fr" if to_french else "fr_en"
    item["lang"] = "fr" if to_french else "en"
    return item


# Streaming: a plain load would download the 40-million-pair training split to read 3 000 rows.
source("wmt14_val", dataset="wmt/wmt14", config="fr-en", split="validation", role="train", skill="conversation.translation",
       module="conversation", license="unknown", lang="fr", streaming=True)(_translation)
source("wmt14_test", dataset="wmt/wmt14", config="fr-en", split="test", role="exam", skill="conversation.translation",
       module="conversation", license="unknown", lang="fr", streaming=True)(_translation)


@source("french_alpaca", dataset="jpacifico/French-Alpaca-dataset-Instruct-110K", split="train", role="train",
        skill="conversation.instruct_fr", module="conversation", license="apache-2.0", lang="fr", cap=8000)
def _french_alpaca(row, key, role):
    instruction, extra, output = row["instruction"].strip(), (row.get("input") or "").strip(), (row.get("output") or "").strip()
    if not instruction or not 20 <= len(output) <= 1800:
        return None
    item = _plain(_user(instruction + ("\n\n" + extra if extra else "")), output, None, 0, instruction + " " + extra)
    item["subskill"] = "alpaca_fr"
    return item


@source("aya_fr", dataset="CohereLabs/aya_dataset", split="train", role="train", skill="conversation.instruct_fr",
        module="conversation", license="apache-2.0", lang="fr", cap=4000)
def _aya(row, key, role):
    if row.get("language_code") != "fra" or not 20 <= len(row["targets"]) <= 1800 or len(row["inputs"]) < 10:
        return None
    item = _plain(_user(row["inputs"].strip()), row["targets"].strip(), None, 0, row["inputs"])
    item["subskill"] = "aya_fr"
    return item


# --- mathematics -----------------------------------------------------------

def _gsm_answer(answer):
    solution, _, final = answer.partition("####")
    final = final.strip().replace(",", "")
    return re.sub(r"<<[^>]*>>", "", solution).strip(), final


@source("gsm8k_train", dataset="openai/gsm8k", config="main", split="train", role="train", skill="academy.math_word", module="academy", license="mit")
@source("gsm8k_test", dataset="openai/gsm8k", config="main", split="test", role="exam", skill="academy.math_word", module="academy", license="mit")
def _gsm8k(row, key, role):
    solution, final = _gsm_answer(row["answer"])
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", final):
        return None
    template = _rng(key).choice(_MATH[(_side(role), "en")])
    item = _plain(_user(template.format(q=row["question"].strip())), f"{solution}\nFinal answer: {final}",
                  {"type": "numeric", "answer": final, "rel_tol": 1e-6, "abs_tol": 1e-6}, 640, row["question"])
    item["subskill"] = "gsm8k"
    return item


@source("metamath", dataset="meta-math/MetaMathQA", split="train", role="train", skill="academy.math_word", module="academy", license="mit", cap=12000)
def _metamath(row, key, role):
    response = row["response"].strip()
    body, marker, final = response.rpartition("The answer is:")
    if not marker or not final.strip() or len(response) > 1800:
        return None
    hard = row["type"].startswith("MATH")
    if hard:
        target = body.strip() if "\\boxed" in body else f"{body.strip()}\nThe final answer is $\\boxed{{{final.strip()}}}$."
        template = _rng(key).choice(_LATEX[("train", "en")])
    else:
        if not re.fullmatch(r"-?[\d,]+(?:\.\d+)?", final.strip()):
            return None
        target = f"{body.strip()}\nFinal answer: {final.strip().replace(',', '')}"
        template = _rng(key).choice(_MATH[("train", "en")])
    item = _plain(_user(template.format(q=row["query"].strip())), target, None, 0, row["original_question"] or row["query"])
    item["skill"] = "academy.math_hard" if hard else "academy.math_word"
    item["subskill"] = row["type"]
    return item


_MATH_SUBJECTS = ["algebra", "counting_and_probability", "geometry", "intermediate_algebra", "number_theory", "prealgebra", "precalculus"]


def _math_hard(row, key, role):
    from .graders import last_boxed
    answer = last_boxed(row["solution"])
    if answer is None or len(row["solution"]) > 1800:
        return None
    template = _rng(key).choice(_LATEX[(_side(role), "en")])
    item = _plain(_user(template.format(q=row["problem"].strip())), row["solution"].strip(),
                  {"type": "latex", "answer": answer}, 900, row["problem"])
    item["subskill"] = f"{row['type']} · {row['level']}"
    return item


for _subject in _MATH_SUBJECTS:
    source("math_train_" + _subject, dataset="EleutherAI/hendrycks_math", config=_subject, split="train", role="train",
           skill="academy.math_hard", module="academy", license="mit")(_math_hard)
    source("math_test_" + _subject, dataset="EleutherAI/hendrycks_math", config=_subject, split="test", role="exam",
           skill="academy.math_hard", module="academy", license="mit")(_math_hard)


# --- code ------------------------------------------------------------------

_CODE_ASK = {"train": "Write a complete Python solution. Return the code in one ```python block.",
             "exam": "Implement it in Python and reply with the full code inside a single ```python fenced block."}


@source("humaneval_plus", dataset="evalplus/humanevalplus", split="test", role="exam", skill="code.python", module="code", license="apache-2.0")
def _humaneval(row, key, role):
    prompt = row["prompt"]
    ask = f"Complete the following Python function.\n\n```python\n{prompt}```\n\n{_CODE_ASK['exam']}"
    item = _plain(_user(ask), f"```python\n{prompt}{row['canonical_solution']}\n```",
                  {"type": "python_tests", "prompt": prompt, "entry_point": row["entry_point"],
                   "tests": row["test"] + f"\n\ncheck({row['entry_point']})\n", "timeout": 40}, 512, prompt)
    item["subskill"] = "humaneval"
    return item


def mbpp_task(task_id):
    """Identity of an MBPP problem shared by MBPP and MBPP+, used as the question to hash.

    MBPP+ (EvalPlus) reuses MBPP problems and rewords many of them: 108 of its 378 exam tasks are in the
    MBPP train split, and hashing the wording removed only 42 of them from training (measured 2026-11-12).
    """
    return "mbpp-task:" + str(int(str(task_id).rsplit("/", 1)[-1]))


@source("mbpp_plus", dataset="evalplus/mbppplus", split="test", role="exam", skill="code.python", module="code", license="apache-2.0")
def _mbpp_plus(row, key, role):
    example = row["test_list"][0] if row["test_list"] else ""
    ask = f"{row['prompt'].strip()}\nYour code must satisfy this assertion:\n{example}\n\n{_CODE_ASK['exam']}"
    item = _plain(_user(ask), f"```python\n{row['code'].strip()}\n```",
                  {"type": "python_tests", "tests": "\n".join(row.get("test_imports") or []) + "\n" + row["test"], "timeout": 40},
                  512, mbpp_task(row["task_id"]))
    item["subskill"] = "mbpp"
    return item


@source("mbpp_train", dataset="google-research-datasets/mbpp", config="full", split="train", role="train", skill="code.python", module="code", license="cc-by-4.0")
def _mbpp(row, key, role):
    example = row["test_list"][0] if row["test_list"] else ""
    ask = f"{row['text'].strip()}\nYour code must satisfy this assertion:\n{example}\n\n{_CODE_ASK['train']}"
    # The tests travel with the item so the student's own solutions can be verified (self-worked training, mining).
    tests = "\n".join(row["test_list"]) + ("\n" + "\n".join(row["challenge_test_list"]) if row.get("challenge_test_list") else "")
    item = _plain(_user(ask), f"```python\n{row['code'].strip()}\n```",
                  {"type": "python_tests", "setup": row.get("test_setup_code") or "", "tests": tests, "timeout": 40},
                  512, mbpp_task(row["task_id"]))
    item["subskill"] = "mbpp"
    return item


@source("self_oss", dataset="bigcode/self-oss-instruct-sc2-exec-filter-50k", split="train", role="train", skill="code.python", module="code", license="odc-by", cap=10000)
def _self_oss(row, key, role):
    if not 40 <= len(row["response"]) <= 2400:
        return None
    item = _plain(_user(row["instruction"].strip()), row["response"].strip(), None, 0, row["instruction"])
    item["subskill"] = "oss_python"
    return item


@source("magicoder", dataset="ise-uiuc/Magicoder-OSS-Instruct-75K", split="train", role="train", skill="code.polyglot", module="code", license="mit", cap=10000)
def _magicoder(row, key, role):
    if not 40 <= len(row["solution"]) <= 2400 or len(row["problem"]) > 2400:
        return None
    item = _plain(_user(row["problem"].strip()), row["solution"].strip(), None, 0, row["problem"])
    item["subskill"] = row["lang"]
    return item


@source("humanevalfix", dataset="bigcode/humanevalpack", config="python", split="test", role="exam", skill="code.bugfix", module="code", license="mit")
def _bugfix(row, key, role):
    buggy = row["declaration"] + row["buggy_solution"]
    ask = (f"The following Python function is buggy.\n\n```python\n{buggy}\n```\n\nIt should behave as described:\n{row['docstring'].strip()}\n\n"
           "Fix the bug and reply with the complete corrected function inside a single ```python fenced block.")
    tests = row["test"]
    if not re.search(rf"^check\({re.escape(row['entry_point'])}\)", tests, flags=re.M):
        tests += f"\n\ncheck({row['entry_point']})\n"
    item = _plain(_user(ask), f"```python\n{row['declaration']}{row['canonical_solution']}\n```",
                  {"type": "python_tests", "entry_point": row["entry_point"], "tests": tests,
                   "setup": (row.get("import") or "") + "\n" + (row.get("test_setup") or ""), "timeout": 30}, 512, buggy)
    item["subskill"] = row["bug_type"]
    return item


def _sql(row, key, role):
    context, gold = row["sql_context"], row["sql"].strip().rstrip(";")
    if len(context) > 1800 or not gold.lower().startswith(("select", "with")) or ";" in gold:
        return None
    try:
        rows = run_sql(context, gold)
    except Exception:                      # the reference itself is not valid SQLite: unusable as an oracle
        return None
    if not rows or all(all(v is None for v in r) for r in rows) or len(rows) > 50:
        return None
    if role == "train":
        ask = f"Schema and data (SQLite):\n{context}\n\nQuestion: {row['sql_prompt'].strip()}\n\nAnswer with one SQL query only."
    else:
        ask = f"Given this SQLite database:\n{context}\n\nWrite a single SQL query that answers: {row['sql_prompt'].strip()}\nOutput the query alone."
    # Identified by schema, data and reference query: a reworded question over the same task is the same exam item
    # (11 test items had a training twin differing only in wording, 2026-11-12).
    item = _plain(_user(ask), gold, {"type": "sql", "context": context, "rows": [list(r) for r in rows],
                                     "ordered": bool(re.search(r"\border\s+by\b", gold, flags=re.I))}, 160,
                  "sql-task:" + context + "\n" + " ".join(gold.split()))
    item["subskill"] = row["sql_complexity"]
    return item


source("sql_train", dataset="gretelai/synthetic_text_to_sql", split="train", role="train", skill="code.sql", module="code",
       license="apache-2.0", cap=8000)(_sql)
source("sql_test", dataset="gretelai/synthetic_text_to_sql", split="test", role="exam", skill="code.sql", module="code",
       license="apache-2.0", cap=2500)(_sql)


# --- security --------------------------------------------------------------

@source("cti_mcq", dataset="AI4Sec/cti-bench", config="cti-mcq", split="test", role="exam", skill="cyber.knowledge", module="cyber", license="cc-by-nc-sa-4.0")
def _cti_mcq(row, key, role):
    answer = str(row["GT"]).strip().upper()
    if answer not in "ABCD" or len(answer) != 1:
        return None
    item = _mcq(key, role, "en", row["Question"], [row[f"Option {l}"] for l in "ABCD"], "ABCD".index(answer))
    if item:
        item["subskill"] = "cti_mcq"
    return item


@source("secqa_v1", dataset="zefang-liu/secqa", config="secqa_v1", split="test", role="exam", skill="cyber.knowledge", module="cyber", license="cc-by-nc-sa-4.0")
@source("secqa_v2", dataset="zefang-liu/secqa", config="secqa_v2", split="test", role="exam", skill="cyber.knowledge", module="cyber", license="cc-by-nc-sa-4.0")
def _secqa(row, key, role):
    answer = str(row["Answer"]).strip().upper()
    if answer not in "ABCD" or len(answer) != 1:
        return None
    item = _mcq(key, role, "en", row["Question"], [row[l] for l in "ABCD"], "ABCD".index(answer))
    if item:
        item["subskill"] = "secqa"
    return item


def _cybermetric(row, key, role):
    answers = row["answers"]
    labels = sorted(answers)
    if row["solution"] not in labels:
        return None
    item = _mcq(key, role, "en", row["question"], [answers[l] for l in labels], labels.index(row["solution"]))
    if item:
        item["subskill"] = "cybermetric"
    return item


source("cybermetric_exam", dataset="tihanyin/CyberMetric", split="questions", role="exam", skill="cyber.knowledge", module="cyber",
       license="apache-2.0", files="CyberMetric-2000-v1.json")(_cybermetric)
source("cybermetric_train", dataset="tihanyin/CyberMetric", split="questions", role="train", skill="cyber.knowledge", module="cyber",
       license="apache-2.0", files="CyberMetric-10000-v1.json", cap=6000)(_cybermetric)

_CWE_LABELS = []


def _cwe(row, key, role):
    label = str(row["GT"]).strip().upper()
    if not re.fullmatch(r"CWE-\d+", label):
        return None
    description = row["Description"].strip()
    if role == "train":
        ask = f"CVE description:\n{description}\n\nWhich CWE identifier best describes the root weakness? Answer with the identifier only (for example CWE-79)."
    else:
        ask = f"Map this vulnerability description to its CWE.\n\n{description}\n\nReply with the single most appropriate identifier in the form CWE-<number>, nothing else."
    item = _plain(_user(ask), label, {"type": "label", "answer": label, "pattern": r"CWE-\d+"}, 12, description)
    item["subskill"] = label
    return item


source("cwe_train", dataset="AI4Sec/cti-bench", config="cti-rcm-2021", split="test", role="train", skill="cyber.cwe", module="cyber",
       license="cc-by-nc-sa-4.0")(_cwe)
source("cwe_exam", dataset="AI4Sec/cti-bench", config="cti-rcm", split="test", role="exam", skill="cyber.cwe", module="cyber",
       license="cc-by-nc-sa-4.0")(_cwe)


@source("trendyol_cyber", dataset="Trendyol/Trendyol-Cybersecurity-Instruction-Tuning-Dataset", split="train", role="train",
        skill="cyber.defense", module="cyber", license="apache-2.0", cap=5000)
def _trendyol(row, key, role):
    if not row.get("assistant") or not row.get("user"):             # two rows of the pinned revision are empty
        return None
    if not 80 <= len(row["assistant"]) <= 2600 or len(row["user"]) > 1200:
        return None
    item = _plain(_user(row["user"].strip()), row["assistant"].strip(), None, 0, row["user"])
    item["subskill"] = "defense"
    return item


# --- finance ---------------------------------------------------------------

def _table(table):
    return "\n".join(" | ".join(str(cell) for cell in line) for line in table)


# Whole words only: "corporation" is not "ratio" and "shareholders" is not "share" (review, 2026-11-12). "shares" and
# "returns" are left out: they name amounts as often as percentages. An answer's own "%" is read by the grader.
_PERCENT_WORDS = re.compile(r"%|\b(?:percent(?:age)?s?|ratios?|proportions?|portions?|rates?|margins?|yields?)\b", re.I)


def _finqa(row, key, role):
    answer = str(row.get("answer") or "").strip()
    number = re.fullmatch(r"\$?\s*(-?[\d,]*\.?\d+)\s*(%?)", answer)
    if not number:
        return None
    context = "\n".join(row["pre_text"]) + "\n\n" + _table(row["table"]) + "\n\n" + "\n".join(row["post_text"])
    if len(context) > 5200:
        return None
    question = row["question"].strip()
    if role == "train":
        ask = f"{context}\n\nQuestion: {question}\nGive the calculation, then end with \"Final answer: <number>\"."
    else:
        ask = f"Financial report excerpt:\n{context}\n\nAnswer the question from the excerpt: {question}\nShow the computation briefly and finish with a line \"Final answer: <number>\"."
    evidence = "\n".join(row.get("gold_evidence") or [])
    value = number.group(1).replace(",", "")
    item = _plain(_user(ask), (evidence + "\n" if evidence else "") + f"Final answer: {value}{number.group(2)}",
                  {"type": "numeric", "answer": value, "rel_tol": 0.01, "abs_tol": 0.005,
                   # A percentage may be written as a ratio and the reverse; an amount may not be 100 times off.
                   "percent_ok": bool(number.group(2)) or bool(_PERCENT_WORDS.search(question))}, 640, question + " " + row["id"])
    item["subskill"] = "percent" if number.group(2) else "amount"
    return item


source("finqa_train", dataset="dreamerdeo/finqa", split="train", role="train", skill="business.finqa", module="business",
       license="unknown", parquet=True)(_finqa)
source("finqa_test", dataset="dreamerdeo/finqa", split="test", role="exam", skill="business.finqa", module="business",
       license="unknown", parquet=True)(_finqa)


@source("convfinqa", dataset="AdaptLLM/finance-tasks", config="ConvFinQA", split="test", role="exam", skill="business.convfinqa",
        module="business", license="unknown")
def _convfinqa(row, key, role):
    text = row["input"].strip()
    try:
        value = float(row["label"])
    except (TypeError, ValueError):
        return None
    if len(text) > 5200:
        return None
    ask = f"{text}\n\nAnswer the last question. Show the computation briefly and finish with a line \"Final answer: <number>\"."
    last = next((line for line in reversed(text.splitlines()) if "?" in line), text[-300:])
    item = _plain(_user(ask), f"Final answer: {value}", {"type": "numeric", "answer": repr(value), "rel_tol": 0.01,
                                                         "abs_tol": 0.005, "percent_ok": bool(_PERCENT_WORDS.search(last))},
                  640, text[-600:])
    item["subskill"] = "turns_" + str(min(4, text.count("?")))
    return item


@source("fpb", dataset="AdaptLLM/finance-tasks", config="FPB", split="test", role="exam", skill="business.sentiment", module="business",
        license="unknown", split_share=0.4)
def _fpb(row, key, role):
    labels = [str(o) for o in row["options"]]
    # The published input is a few-shot prompt; only its last block is the sentence to classify.
    block = row["input"].strip().split("\n\n")[-1].split("\nOptions:")[0].split("\nQuestion:")[0]
    sentence = re.sub(r"^[^:\n]{0,90}\bsentence\s*:\s*", "", block.strip(), flags=re.I).strip()
    if len(sentence) < 15 or "\n" in sentence:
        return None
    if role == "train":
        ask = f"Sentence from a financial news report:\n{sentence}\n\nIs the sentiment for an investor Negative, Neutral or Positive? Answer with one word."
    else:
        ask = f"Classify the investor sentiment of this financial statement as Positive, Neutral or Negative.\n\n{sentence}\n\nReply with the single label only."
    label = labels[int(row["gold_index"])]
    item = _plain(_user(ask), label, {"type": "label", "answer": label, "labels": labels}, 6, sentence)
    item["subskill"] = label.lower()
    return item


@source("finance_alpaca", dataset="gbharti/finance-alpaca", split="train", role="train", skill="business.advice", module="business",
        license="mit", cap=4000)
def _finance_alpaca(row, key, role):
    output = (row.get("output") or "").strip()
    if not 120 <= len(output) <= 2200 or not row["instruction"].strip():
        return None
    extra = (row.get("input") or "").strip()
    item = _plain(_user(row["instruction"].strip() + ("\n\n" + extra if extra else "")), output, None, 0, row["instruction"])
    item["subskill"] = "finance_qa"
    return item


# --- documents and tools ---------------------------------------------------

# PIAF (Etalab, French Wikipedia, MIT): the training side of the FQuAD exam, same prompt and grader. Measured on
# 12 November: none of its 3 835 rows shares a context, a question, an article or a long sentence with the exam.
@source("piaf", dataset="AgentPublic/piaf", config="plain_text", split="train", role="train", skill="cowork.extract_qa_fr",
        module="cowork", license="mit", lang="fr")
@source("fquad_test", dataset="manu/fquad2_test", split="test_hasAns", role="exam", skill="cowork.extract_qa_fr", module="cowork", license="apache-2.0", lang="fr")
@source("fquad_valid", dataset="manu/fquad2_test", split="valid_hasAns", role="exam", skill="cowork.extract_qa_fr", module="cowork", license="apache-2.0", lang="fr")
def _fquad(row, key, role):
    answers = sorted({a.strip() for a in row["answers"]["text"] if a.strip()})
    if not answers or len(row["context"]) > 2600:
        return None
    ask = (f"Contexte :\n{row['context'].strip()}\n\nQuestion : {row['question'].strip()}\n\n"
           "Réponds par le passage exact du contexte qui répond à la question, le plus court possible, sans phrase d'introduction.")
    item = _plain(_user(ask), min(answers, key=len), {"type": "text", "answers": answers, "f1_threshold": 0.7}, 48, row["question"] + " " + row["title"])
    item["subskill"] = "fquad"
    return item


def _hermes_turns(row):
    turns = row["conversations"]
    if len(turns) != 3 or [t["from"] for t in turns] != ["system", "human", "gpt"]:
        return None
    return turns


@source("hermes_calls", dataset="NousResearch/hermes-function-calling-v1", config="func_calling_singleturn", split="train",
        role="exam", skill="cowork.tool_call", module="cowork", license="apache-2.0", split_share=0.7)
def _hermes_calls(row, key, role):
    turns = _hermes_turns(row)
    if not turns or len(turns[0]["value"]) > 5200:
        return None
    blocks = re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", turns[2]["value"], flags=re.S)
    calls = []
    for block in blocks:
        try:
            call = json.loads(block)
        except ValueError:
            try:
                import ast
                call = ast.literal_eval(block)
            except (ValueError, SyntaxError):
                return None
        if not isinstance(call, dict) or "name" not in call:
            return None
        calls.append({"name": call["name"], "arguments": call.get("arguments", {})})
    if not calls:
        return None
    target = "\n".join("<tool_call>\n" + json.dumps(c, ensure_ascii=False) + "\n</tool_call>" for c in calls)
    messages = [{"role": "system", "content": turns[0]["value"].strip()}, {"role": "user", "content": turns[1]["value"].strip()}]
    item = _plain(messages, target, {"type": "tool_call", "calls": calls}, 260, turns[1]["value"])
    item["subskill"] = row.get("category") or "tools"
    return item


@source("hermes_json", dataset="NousResearch/hermes-function-calling-v1", config="json_mode_singleturn", split="train",
        role="train", skill="cowork.json_schema", module="cowork", license="apache-2.0")
def _hermes_json(row, key, role):
    turns = _hermes_turns(row)
    if not turns or len(turns[0]["value"]) > 4000:
        return None
    try:
        value = json.loads(turns[2]["value"])
    except ValueError:
        return None
    messages = [{"role": "system", "content": turns[0]["value"].strip()}, {"role": "user", "content": turns[1]["value"].strip()}]
    item = _plain(messages, json.dumps(value, ensure_ascii=False), None, 0, turns[1]["value"])
    item["subskill"] = row.get("category") or "json"
    return item


@source("json_mode_eval", dataset="NousResearch/json-mode-eval", split="train", role="exam", skill="cowork.json_schema",
        module="cowork", license="unknown")
def _json_mode_eval(row, key, role):
    try:
        value = json.loads(row["completion"])
    except ValueError:
        return None
    messages = [{"role": m["role"], "content": m["content"]} for m in row["prompt"]]
    if not messages or messages[-1]["role"] != "user":
        return None
    item = _plain(messages, json.dumps(value, ensure_ascii=False), {"type": "json", "accept": [value]}, 260, messages[-1]["content"])
    item["subskill"] = "json_mode_eval"
    return item


# --- loading ---------------------------------------------------------------

def _rows(spec, revision):
    """Yield raw rows of one source. Imported lazily: only the cloud machines need ``datasets``."""
    if spec["files"]:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(spec["dataset"], spec["files"], repo_type="dataset", revision=revision)
        with open(path, encoding="utf-8") as stream:
            payload = json.load(stream)
        yield from payload[spec["split"]]
        return
    from datasets import load_dataset
    if spec["parquet"]:
        pattern = f"hf://datasets/{spec['dataset']}@~parquet/{spec['config'] or 'default'}/{spec['split']}/*.parquet"
        yield from load_dataset("parquet", data_files={spec["split"]: pattern}, split=spec["split"])
        return
    arguments = {"split": spec["split"], "revision": revision, "streaming": spec["streaming"]}
    data = load_dataset(spec["dataset"], spec["config"], **arguments) if spec["config"] else load_dataset(spec["dataset"], **arguments)
    yield from data


def source_role(spec, key):
    """Role of one row: sources with a single public split are divided by a stable hash."""
    share = spec["split_share"]
    if share is None:
        return spec["role"]
    return "exam" if bucket(key, "aurora-source-split") < int(share * 1000) else "train"


def load_source(name, *, revisions=None, limit=None):
    """Return ``(train_items, exam_items)`` of one source, each exam item tagged with its exam role."""
    spec = SOURCES[name]
    revision = (revisions or {}).get(spec["dataset"])
    train, exam = [], []
    for index, row in enumerate(_rows(spec, revision)):
        if limit is not None and index >= limit:
            break
        key = f"{name}:{index}"
        role = source_role(spec, key)
        built = spec["adapt"](row, key, "train" if role == "train" else "exam")
        if not built:
            continue
        item = {"id": f"hf:{key}", "module": spec["module"], "skill": built.pop("skill", spec["skill"]),
                "subskill": built.pop("subskill", name), "lang": built.pop("lang", spec["lang"]), "source": name,
                "question_hash": question_hash(built.pop("question")), **built}
        if role == "train":
            if item.get("grader") is None:
                item.pop("grader", None)      # free-form reference: usable for training, not for mining
            train.append(item)
        elif item.get("grader"):
            item["exam_role"] = exam_role(item["id"])
            exam.append(item)
    return train, exam
