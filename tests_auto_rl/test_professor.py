"""Contracts of the professor loop that need no model, GPU or network."""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_rl.professor import generators, generators_domain  # noqa: F401
from auto_rl.professor.compare import GATE, compare, mcnemar_exact, wilson
from auto_rl.professor.graders import grade, parse_numbers, parse_single_json
from auto_rl.professor.records import bucket, exam_role, question_hash
from auto_rl.professor.suites import MODULES, build_exam, build_pool, skills, stratified
from auto_rl.professor.weakness import build_curriculum, profile, skill_weights


def item(kind, **grader):
    return {"grader": {"type": kind, **grader}}


class Graders(unittest.TestCase):
    def test_multiple_choice_needs_one_unambiguous_letter(self):
        mcq = item("mcq", answer="B", options=4)
        for answer in ("B", "b", "(B)", "B.", "B) Paris", "**B**", "La bonne réponse est B.", "Answer: B", "B\n\nParce que..."):
            self.assertTrue(grade(mcq, answer)["correct"], answer)
        for answer in ("", "A", "A or B", "The answer is A, not B... answer: A", "Paris", "A B C D", "Réponse : A ou réponse : B",
                       "Be careful", "<think>B"):
            self.assertFalse(grade(mcq, answer)["correct"], answer)
        self.assertTrue(grade(item("mcq", answer="K", options=12), "(K)")["correct"])

    def test_reasoning_block_is_not_the_answer(self):
        mcq = item("mcq", answer="C", options=4)
        self.assertTrue(grade(mcq, "<think>maybe A</think>C")["correct"])
        self.assertFalse(grade(mcq, "<think>the answer is C")["correct"])

    def test_numbers_french_and_english_notation(self):
        self.assertEqual(parse_numbers("1 234,56"), [1234.56])
        self.assertEqual(parse_numbers("1,234.56"), [1234.56])
        self.assertEqual(sorted(parse_numbers("1,234")), [1.234, 1234.0])
        self.assertEqual(parse_numbers("3/4"), [0.75])
        numeric = item("numeric", answer="1234.56", abs_tol=0.006)
        self.assertTrue(grade(numeric, "Calcul...\nRéponse finale : 1 234,56 €")["correct"])
        self.assertTrue(grade(numeric, "Final answer: 1,234.56")["correct"])
        self.assertFalse(grade(numeric, "Réponse finale : 1234.60")["correct"])
        self.assertFalse(grade(numeric, "Je ne sais pas.")["correct"])
        # The marked final answer wins over later numbers in the text.
        self.assertFalse(grade(numeric, "Réponse finale : 12 (et non 1234.56)")["correct"])
        self.assertTrue(grade(item("numeric", answer="0.153", rel_tol=0.01, percent_ok=True), "Final answer: 15.3%")["correct"])

    def test_json_must_be_a_single_document(self):
        self.assertEqual(parse_single_json('```json\n{"a": 1}\n```'), {"a": 1})
        for bad in ('{"a": 1}{"a": 2}', '{"a": 1} done', '{"a": 1, "a": 2}', "NaN", ""):
            with self.assertRaises(ValueError):
                parse_single_json(bad)
        check = item("json", accept=[{"n": 1, "tags": ["x", "y"]}], unordered=["/tags"])
        self.assertTrue(grade(check, '{"tags": ["y", "x"], "n": 1.0}')["correct"])
        self.assertFalse(grade(check, '{"tags": ["y"], "n": 1}')["correct"])
        self.assertFalse(grade(check, '{"tags": ["x", "y"], "n": true}')["correct"])

    def test_label_text_and_translation(self):
        cwe = item("label", answer="CWE-79", pattern=r"CWE-\d+")
        self.assertTrue(grade(cwe, "cwe-79 (XSS)")["correct"])
        self.assertFalse(grade(cwe, "CWE-79 ou CWE-89")["correct"])
        self.assertFalse(grade(cwe, "CWE-798")["correct"])
        sentiment = item("label", answer="Neutral", labels=["Negative", "Neutral", "Positive"])
        self.assertTrue(grade(sentiment, "Neutral.")["correct"])
        self.assertFalse(grade(sentiment, "Neutral or Positive")["correct"])
        text = item("text", answers=["par un mauvais état de santé", "mauvais état de santé"], f1_threshold=0.7)
        self.assertTrue(grade(text, "Mauvais état de santé.")["correct"])
        self.assertFalse(grade(text, "Il était riche.")["correct"])
        translation = item("chrf", references=["The cat sleeps on the blue sofa."], threshold=0.55)
        self.assertTrue(grade(translation, "The cat sleeps on the blue sofa")["correct"])
        self.assertFalse(grade(translation, "A dog runs in the garden.")["correct"])
        self.assertFalse(grade(translation, "The cat sleeps on the blue sofa. " * 8)["correct"])

    def test_sql_is_judged_by_its_result_not_its_text(self):
        context = "CREATE TABLE t (id INT, v INT); INSERT INTO t VALUES (1, 10), (2, 20), (3, 30);"
        sql = item("sql", context=context, rows=[[60]])
        self.assertTrue(grade(sql, "```sql\nSELECT SUM(v) FROM t;\n```")["correct"])
        self.assertTrue(grade(sql, "select 10 + 20 + 30")["correct"])
        self.assertFalse(grade(sql, "SELECT SUM(id) FROM t")["correct"])
        self.assertFalse(grade(sql, "SELECT nothing FROM nowhere")["correct"])
        self.assertFalse(grade(sql, "PRAGMA table_info(t)")["correct"])

    def test_generated_code_never_runs_without_explicit_permission(self):
        tests = item("python_tests", tests="assert add(1, 2) == 3", entry_point="add")
        with patch.dict(os.environ, {"AURORA_PROFESSOR_ALLOW_CODE_EXECUTION": ""}):
            with self.assertRaises(RuntimeError):
                grade(tests, "```python\ndef add(a, b):\n    return a + b\n```")

    @unittest.skipIf(os.name == "nt", "POSIX resource limits")
    def test_code_is_judged_by_running_its_tests(self):
        tests = item("python_tests", tests="assert add(1, 2) == 3\nassert add(-1, 1) == 0", entry_point="add")
        with patch.dict(os.environ, {"AURORA_PROFESSOR_ALLOW_CODE_EXECUTION": "1"}):
            self.assertTrue(grade(tests, "Voici :\n```python\ndef add(a, b):\n    return a + b\n```")["correct"])
            self.assertFalse(grade(tests, "```python\ndef add(a, b):\n    return a - b\n```")["correct"])
            self.assertFalse(grade(tests, "```python\ndef add(a, b):\n    while True: pass\n```" if False else "```python\nraise SystemExit(3)\n```")["correct"])

    def test_unknown_grader_is_an_error_not_a_score(self):
        with self.assertRaises(ValueError):
            grade(item("vibes"), "great")


class Generators(unittest.TestCase):
    def test_every_reference_passes_and_exam_never_repeats_training(self):
        train, exam = set(), set()
        for name, spec in generators.FAMILIES.items():
            for subskill in spec["subskills"]:
                for role in ("train", "diagnostic", "gate:0", "gate:1"):
                    for index in range(6):
                        built = generators.generate(name, role, index, subskill)
                        self.assertTrue(grade(built, built["target"])["correct"], built["id"])
                        (train if role == "train" else exam).add(built["question_hash"])
        self.assertFalse(train & exam)

    def test_generation_is_deterministic(self):
        first = generators.generate("mission.evidence", "gate:2", 5, "quantity")
        second = generators.generate("mission.evidence", "gate:2", 5, "quantity")
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        self.assertNotEqual(first["messages"], generators.generate("mission.evidence", "gate:3", 5, "quantity")["messages"])

    def test_evidence_oracle_is_the_production_comparator(self):
        built = generators.generate("mission.evidence", "gate:0", 3, "quantity")
        good = json.loads(built["target"])
        check = good["args"]["checks"][0]

        def answer(**changes):
            return json.dumps({"tool": "verify", "args": {"checks": [{**check, **changes}]}})
        self.assertTrue(grade(built, answer())["correct"])
        self.assertFalse(grade(built, answer(expressions=["1 == 1"]))["correct"])                       # tautology
        self.assertFalse(grade(built, answer(bindings=check["bindings"][:-1]))["correct"])              # unbound field
        dotted = [{**check["bindings"][0], "source_pointer": "result.url"}] + check["bindings"][1:]
        self.assertFalse(grade(built, answer(bindings=dotted))["correct"])                              # not RFC 6901
        written = next(r for r in built["grader"]["receipts"].values() if r["tool"] == "write_file")
        copied = [{"path": "/title", "evidence_id": written["id"], "source_pointer": "/result/content/title"}] + check["bindings"]
        self.assertFalse(grade(built, answer(bindings=copied))["correct"])                              # own output is no evidence
        failed = next(r for r in built["grader"]["receipts"].values() if r["ok"] is False)
        refused = [{"path": "/title", "evidence_id": failed["id"], "source_pointer": "/result/title"}] + check["bindings"]
        self.assertFalse(grade(built, answer(bindings=refused))["correct"])                             # failed receipt
        self.assertFalse(grade(built, built["target"] + built["target"])["correct"])                    # two JSON documents

    def test_pointer_and_action_use_real_contracts(self):
        pointer = generators.generate("mission.pointer", "train", 5, "escape")
        self.assertIn("~", pointer["target"])
        self.assertFalse(grade(pointer, pointer["target"].replace("~1", "/").replace("~0", "~"))["correct"])
        self.assertFalse(grade(pointer, "result.headers")["correct"])
        action = generators.generate("mission.action", "gate:0", 2, "browser_click")
        expected = json.loads(action["target"])
        self.assertTrue(grade(action, action["target"])["correct"])
        self.assertFalse(grade(action, json.dumps({**expected, "args": {**expected["args"], "invented": 1}}))["correct"])
        self.assertFalse(grade(action, json.dumps({"tool": "click", "args": expected["args"]}))["correct"])


class Statistics(unittest.TestCase):
    def rows(self, flags, skill="s", module="m"):
        return [{"id": f"{skill}:{i}", "module": module, "skill": skill, "subskill": "a", "status": "graded",
                 "correct": bool(flag), "output": "x"} for i, flag in enumerate(flags)]

    def test_exact_mcnemar_and_wilson(self):
        self.assertEqual(mcnemar_exact(0, 0), 1.0)
        self.assertAlmostEqual(mcnemar_exact(1, 9), 2 * (1 + 10) / 2 ** 10)
        low, high = wilson(50, 100)
        self.assertTrue(0.40 < low < 0.5 < high < 0.60)
        self.assertEqual(wilson(0, 0), (0.0, 1.0))

    def test_clear_gain_is_promoted_and_noise_is_not(self):
        base = self.rows([0] * 150 + [1] * 150, "a") + self.rows([0] * 150 + [1] * 150, "b")
        better = self.rows([1] * 120 + [0] * 30 + [1] * 150, "a") + self.rows([1] * 110 + [0] * 40 + [1] * 150, "b")
        self.assertEqual(compare(base, better)["verdict"], "promote")
        same = compare(base, base)
        self.assertEqual(same["verdict"], "inconclusive")
        self.assertEqual(same["overall"]["macro_gain"], 0.0)
        noisy = self.rows([0] * 148 + [1] * 152, "a") + self.rows([0] * 151 + [1] * 149, "b")
        self.assertNotEqual(compare(base, noisy)["verdict"], "promote")

    def test_a_gain_cannot_hide_a_broken_skill(self):
        base = self.rows([0] * 150 + [1] * 150, "a") + self.rows([1] * 300, "b")
        traded = self.rows([1] * 300, "a") + self.rows([0] * 60 + [1] * 240, "b")
        result = compare(base, traded)
        self.assertEqual(result["verdict"], "reject")
        self.assertEqual(result["regressions"], ["b"])

    def test_small_or_mismatched_exams_cannot_promote(self):
        base, better = self.rows([0] * 40), self.rows([1] * 40)
        self.assertEqual(compare(base, better)["verdict"], "inconclusive")
        with self.assertRaises(ValueError):
            compare(base, better[:-1])
        self.assertGreaterEqual(GATE["min_items"], 200)

    def test_more_empty_answers_is_a_rejection(self):
        base = self.rows([0] * 150 + [1] * 150)
        candidate = self.rows([1] * 300)
        for row in candidate[:20]:
            row["output"] = ""
        self.assertEqual(compare(base, candidate)["verdict"], "reject")


class Curriculum(unittest.TestCase):
    def test_exam_partition_is_stable_and_disjoint(self):
        self.assertEqual(bucket("x", "salt"), bucket("x", "salt"))
        roles = [exam_role(f"hf:demo:{i}") for i in range(2000)]
        self.assertTrue(0.25 < roles.count("diagnostic") / 2000 < 0.35)
        self.assertEqual(question_hash("  Où est le VÉLO ? "), question_hash("ou est le velo"))

    def test_gate_cycles_draw_disjoint_items(self):
        items = [{"id": f"i{n}", "subskill": f"s{n % 4}"} for n in range(400)]
        first, reused_first = stratified(items, 40, "seed", 0)
        second, reused_second = stratified(items, 40, "seed", 1)
        self.assertFalse({i["id"] for i in first} & {i["id"] for i in second})
        self.assertFalse(reused_first or reused_second)
        _, exhausted = stratified(items[:40], 40, "seed", 3)
        self.assertEqual(exhausted, 40)
        # Sub-skills of very different sizes: slices stay disjoint, and reuse is counted once the family runs out.
        uneven = [{"id": f"u{n}", "subskill": "small" if n < 10 else f"big{n % 2}"} for n in range(410)]
        slices = [stratified(uneven, 150, "seed", cycle) for cycle in range(3)]
        self.assertFalse({i["id"] for i in slices[0][0]} & {i["id"] for i in slices[1][0]})
        self.assertEqual([reused for _, reused in slices], [0, 0, 40])
        self.assertEqual(len({i["id"] for i in slices[2][0]}), 150)
        self.assertEqual(len({i["id"] for i in slices[2][0]} - {i["id"] for chosen, _ in slices[:2] for i in chosen}), 110)

    def test_gate_slices_stay_disjoint_when_cycles_ask_for_different_counts(self):
        from auto_rl.professor.suites import GATE_SLOT
        family = [{"id": f"hf:s:{n}", "subskill": f"s{n % 3}"} for n in range(1000)]
        taken = [{i["id"] for i in stratified(family, 150, "seed", c, slot=GATE_SLOT)[0]} for c in range(3)]
        later = {i["id"] for i in stratified(family, 120, "seed", 3, slot=GATE_SLOT)[0]}     # what the November runs ask next
        self.assertFalse(later & set().union(*taken))
        self.assertEqual(len(later), 120)
        small = {i["id"] for i in stratified(family, 100, "seed", 1, slot=GATE_SLOT)[0]}
        self.assertFalse(small & taken[0])                                                  # 100 after 150: no overlap
        self.assertTrue({i["id"] for i in stratified(family, 100, "seed", 1)[0]} & taken[0])  # the former positions overlapped
        with self.assertRaises(ValueError):
            stratified(family, GATE_SLOT + 1, "seed", 1, slot=GATE_SLOT)
        _, reused = stratified(family[:400], 150, "seed", 2, slot=GATE_SLOT)
        self.assertEqual(reused, 50)                                                        # positions 300-449 of 400 items

    def test_generated_gates_count_each_prompt_once_and_prefer_unused_prompts(self):
        """conversation.format_fr has about 18 distinct exam prompts for some sub-skills (2026-11-12 review)."""
        from auto_rl.professor.suites import _earlier_prompts
        with patch("auto_rl.professor.suites.Library.load", return_value=([], [])):
            for cycle in (1, 2):
                gate, notes = build_exam("gate", 150, modules=["conversation"], cycle=cycle, only=["conversation.format_fr"])
                hashes = [i["question_hash"] for i in gate]
                self.assertEqual(len(hashes), len(set(hashes)))                         # no prompt counted twice
                earlier = _earlier_prompts("conversation.format_fr", cycle)
                self.assertEqual(sum(h in earlier for h in hashes), notes["reused_items"].get("conversation.format_fr", 0))
                self.assertLess(len(gate), 150)                                         # the family is smaller than 150 prompts
            first, _ = build_exam("gate", 150, modules=["missions"], cycle=1, only=["mission.pointer"])
            zero, _ = build_exam("gate", 150, modules=["missions"], cycle=0, only=["mission.pointer"])
            self.assertFalse({i["question_hash"] for i in first} & {i["question_hash"] for i in zero})

    def test_generator_exams_and_pools_never_overlap(self):
        modules = ["missions", "engineering", "media"]
        with patch("auto_rl.professor.suites.Library.load", return_value=([], [])):
            diagnostic, _ = build_exam("diagnostic", 8, modules=modules)
            gate, _ = build_exam("gate", 8, modules=modules, cycle=1)
            pool, _ = build_pool(24, modules=modules)
        exam_hashes = {i["question_hash"] for i in diagnostic + gate}
        self.assertFalse(exam_hashes & {i["question_hash"] for group in pool.values() for i in group})
        self.assertFalse({i["id"] for i in diagnostic} & {i["id"] for i in gate})
        self.assertTrue(all("target" not in i for i in diagnostic + gate))
        self.assertEqual(set(skills(modules)) & set(pool), set(pool))

    def test_blocklist_removes_leaking_training_items(self):
        with patch("auto_rl.professor.suites.Library.load", return_value=([], [])):
            pool, _ = build_pool(12, modules=["engineering"])
            leaked = pool["engineering.calc"][0]["question_hash"][:20]
            filtered, notes = build_pool(12, modules=["engineering"], blocklist=[leaked])
        self.assertNotIn(leaked, {i["question_hash"][:20] for i in filtered["engineering.calc"]})
        self.assertEqual(notes["removed_by_blocklist"], 1)

    def test_budget_follows_measured_weakness_with_a_floor(self):
        summary = {"skills": {"weak": {"module": "m", "items": 100, "correct": 10, "accuracy": 0.1, "ci95": [0.05, 0.18]},
                              "strong": {"module": "m", "items": 100, "correct": 95, "accuracy": 0.95, "ci95": [0.89, 0.98]}},
                   "subskills": {"weak / a": {"items": 50, "correct": 1, "accuracy": 0.02}, "weak / b": {"items": 50, "correct": 9, "accuracy": 0.18}}}
        catalogue = {"weak": {"generator": True, "train_sources": []}, "strong": {"generator": False, "train_sources": ["x"]}}
        weak_points = profile(summary, catalogue)
        self.assertEqual(weak_points[0]["skill"], "weak")
        self.assertEqual(weak_points[0]["subskills"][0]["subskill"], "a")
        weights = skill_weights(weak_points, ["weak", "strong", "unexamined"])
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertGreater(weights["weak"], 5 * weights["strong"])
        self.assertGreater(weights["strong"], 0)
        self.assertGreater(weights["unexamined"], 0)

    def test_known_failures_are_taught_first(self):
        pool = {"weak": [{"id": f"w{n}", "module": "m", "skill": "weak"} for n in range(50)],
                "replay": [{"id": f"r{n}", "module": "m", "skill": "replay"} for n in range(50)]}
        mined = {"w3": False, "w7": False, "w9": True}
        chosen, plan = build_curriculum(pool, {"weak": 1.0}, 20, mined=mined, replay_skills=("replay",))
        ids = {i["id"] for i in chosen}
        self.assertTrue({"w3", "w7"} <= ids)
        self.assertNotIn("w9", ids)
        self.assertEqual(plan["skills"]["weak"]["known_failures_included"], 2)
        self.assertEqual(plan["skills"]["weak"]["subskills"], {"None": plan["skills"]["weak"]["selected"]})
        self.assertTrue(plan["skills"]["replay"]["replay"])
        self.assertEqual(len(chosen), plan["total"])

    def test_mining_probes_cover_every_subskill(self):
        from auto_rl.professor.run import mining_probes
        with patch("auto_rl.professor.suites.Library.load", return_value=([], [])):
            pool, _ = build_pool(120, modules=["missions"])
        for name, items in pool.items():
            wanted = {i["subskill"] for i in items if i.get("grader")}
            probed = {i["subskill"] for i in mining_probes({name: items}, 40)}
            self.assertEqual(probed, wanted, name)
            self.assertGreater(len(wanted), 1, name)
            self.assertLess(len({i["subskill"] for i in items[:40]}), len(wanted), name)   # the head alone misses sub-skills

    def test_a_later_cycle_trains_on_new_exercises(self):
        with patch("auto_rl.professor.suites.Library.load", return_value=([], [])):
            first, notes_first = build_pool(60, modules=["missions", "media"])
            later, notes_later = build_pool(60, modules=["missions", "media"], cycle=1)
            gate, _ = build_exam("gate", 12, modules=["missions", "media"], cycle=1)
        self.assertEqual((notes_first["cycle"], notes_later["cycle"]), (0, 1))
        for name in first:
            self.assertFalse({i["id"] for i in first[name]} & {i["id"] for i in later[name]}, name)
            repeated = {i["question_hash"] for i in first[name]} & {i["question_hash"] for i in later[name]}
            self.assertLess(len(repeated), 0.2 * len(later[name]), name)       # small generators may repeat a few questions
        self.assertFalse({i["question_hash"] for i in gate} & {i["question_hash"] for group in later.values() for i in group})
        sources = [{"id": f"hf:s:{n}", "subskill": "a", "skill": "k"} for n in range(30)]
        self.assertFalse({i["id"] for i in stratified(sources, 10, "aurora-pool", 0)[0]}
                         & {i["id"] for i in stratified(sources, 10, "aurora-pool", 1)[0]})

    def test_the_next_cycle_starts_from_the_candidate_scores_and_its_own_adapter(self):
        from auto_rl.professor.run import next_diagnosis, train_role
        rows = lambda marks, skill, sub: [{"id": f"{skill}{sub}{n}", "module": "missions", "skill": skill, "subskill": sub,
                                           "status": "graded", "correct": bool(m), "output": "x"} for n, m in enumerate(marks)]
        base = rows([0] * 40, "mission.pointer", "escape") + rows([1] * 40, "mission.action", "browser_open")
        candidate = rows([1] * 10 + [0] * 30, "mission.pointer", "escape") + rows([1] * 40, "mission.action", "browser_open")
        result = compare(base, candidate, gate={"min_items": 60})
        verdict = {"schema": 1, "student": {"tag": "qwen2.5-coder:7b", "hf": "Qwen/Qwen2.5-Coder-7B-Instruct"},
                   "profile": "standard", "modules": ["missions"], "skills": None, "cycle": 0, "hardware": {}, "versions": {},
                   "python": "3", "host": "h", "created_at": 0, **result, "exam_complete": True, "adapter_sha256": "a" * 64,
                   "exam": {"items": 80, "graded_both": 80, "notes": {}, "suite_sha256": "s", "candidate_receipt": "r"}}
        following = next_diagnosis(verdict, ["h2", "h1"])
        self.assertEqual(following["kind"], "aurora_professor_diagnosis")
        self.assertEqual(following["basis"], {"model": "candidate", "exam": "gate:0", "adapter_sha256": "a" * 64, "verdict": result["verdict"]})
        self.assertEqual(following["weak_points"][0]["skill"], "mission.pointer")       # the candidate's score, not the base's
        self.assertAlmostEqual(following["weak_points"][0]["accuracy"], 0.25)
        self.assertEqual(following["summary"]["overall"]["macro_accuracy"], result["overall"]["macro_candidate"])
        self.assertEqual(following["blocklist"], ["h1", "h2"])
        self.assertEqual(following["skills"], ["mission.action", "mission.pointer"])
        config = {"student": {"hf": "Qwen/Qwen2.5-Coder-7B-Instruct"}, "row_limit": None, "cycle": 1}
        with self.assertRaises(ValueError):       # the candidate's diagnosis without the candidate's adapter
            train_role(config, "unused", following, student=object(), library=object())
        with self.assertRaises(ValueError):       # an adapter the diagnosis does not describe
            train_role(config, "unused", {**following, "basis": None}, student=object(), library=object(), init_adapter="absent")
        with self.assertRaisesRegex(ValueError, "cycle >= 1"):     # examined again on the gate that steered its curriculum
            train_role({**config, "cycle": 0}, "unused", following, student=object(), library=object(), init_adapter="absent")

    def test_numeric_skills_train_only_on_the_students_own_verified_work(self):
        from auto_rl.professor.run import SELF_WORKED, keep_verified_answers
        with patch("auto_rl.professor.suites.Library.load", return_value=([], [])):
            pool, _ = build_pool(40, modules=["business", "media"])
        self.assertIn("business.fin_math", SELF_WORKED)
        asked = pool["business.fin_math"][:6]
        own = "Étape 1 : 100 × 0,2 = 20\nÉtape 2 : 100 + 20 = 120\nRéponse finale : 120.00"
        rows = [{"id": asked[0]["id"], "skill": "business.fin_math", "status": "graded", "correct": True, "output": own + "\n"},
                {"id": asked[1]["id"], "skill": "business.fin_math", "status": "graded", "correct": False, "output": "Réponse finale : 3"},
                {"id": asked[2]["id"], "skill": "business.fin_math", "status": "graded", "correct": True, "output": "  "},
                {"id": asked[3]["id"], "skill": "business.fin_math", "status": "skipped_prompt_too_long", "correct": False, "output": None}]
        untouched = list(pool["media.prompt_spec"])
        notes = keep_verified_answers(pool, {"business.fin_math": asked}, rows)
        self.assertEqual(notes, {"business.fin_math": {"asked": 6, "answered": 4, "verified": 1}})
        self.assertEqual([(i["id"], i["target"]) for i in pool["business.fin_math"]], [(asked[0]["id"], own)])   # the student's work, not the reference
        self.assertEqual(pool["media.prompt_spec"], untouched)
        notes = keep_verified_answers(pool, {"business.fin_math": asked}, rows[1:])       # nothing verified: no example at all
        self.assertNotIn("business.fin_math", pool)
        self.assertEqual(notes["business.fin_math"]["verified"], 0)

    def test_the_trainer_follows_explicit_replay_and_self_worked_choices(self):
        """Replay and self-worked skills are chosen per cycle; what was chosen is written in the curriculum."""
        import tempfile
        from auto_rl.professor import run as run_module, train as train_module
        from auto_rl.professor.students import resolve

        def free_form(skill):
            return [{"id": f"hf:{skill}:{n}", "module": skill.split(".")[0], "skill": skill, "subskill": "free", "lang": "fr",
                     "messages": [{"role": "user", "content": f"{skill} consigne {n}"}], "target": "Une réponse rédigée.",
                     "question_hash": f"{skill}{n}".encode().hex()[:40].ljust(40, "0"), "max_new_tokens": 32} for n in range(30)]

        class Student:
            def generate(self, conversations, tokens, batch_size=1):
                return ["Réponse finale : 0"] * len(conversations)       # every numeric answer wrong: nothing verified

            def describe(self):
                return {"backend": "fake"}

            def attach(self, adapter):
                raise AssertionError("a first cycle has no adapter to attach")

            def detach(self):
                pass
        captured = []

        def fake_train(student, items, folder, **options):
            captured.append(list(items))
            return {"steps": 0}
        diagnosis = {"student": {"hf": "Qwen/Qwen3-0.6B"}, "weak_points": [], "blocklist": [], "basis": None,
                     "summary": {"skills": {}}, "exam": {}}
        base = {**run_module.PROFILES["smoke"], "profile": "smoke", "student": resolve("qwen3:0.6b"), "modules": ["business", "conversation"],
                "skills": ["business.fin_math", "conversation.format_fr"], "cycle": 0, "budget_seconds": None, "allow_execution": False,
                "curriculum": 60, "self_worked_per_skill": 6, "mine_per_skill": 2}
        for choice, expected_replay in (({}, {"business.advice", "conversation.instruct_fr"}),
                                        ({"replay": ("business.advice",)}, {"business.advice"})):
            config = {**base, **choice}
            with tempfile.TemporaryDirectory() as work, \
                    patch.object(run_module.Library, "train_family", lambda self, skill, catalogue: free_form(skill)), \
                    patch.object(run_module.Library, "exam_family", lambda self, skill, catalogue: []), \
                    patch.object(train_module, "train", fake_train):
                run_module.train_role(config, work, diagnosis, student=Student(), library=run_module.Library())
                plan = json.loads((Path(work) / "curriculum.json").read_text())
            replayed = {name for name, entry in plan["plan"]["skills"].items() if entry.get("replay")}
            self.assertEqual(replayed, expected_replay)
            self.assertEqual(set(plan["choices"]["replay"]) & {"business.advice", "conversation.instruct_fr"}, expected_replay)
            self.assertEqual(plan["self_worked"]["business.fin_math"]["verified"], 0)
            self.assertNotIn("business.fin_math", plan["plan"]["skills"])       # no verified work: no example at all
            self.assertTrue(all(item["skill"] in expected_replay | {"conversation.format_fr"} for item in captured[-1]))
        # A self-worked skill whose training items cannot be graded is a configuration error, not a silent omission.
        with tempfile.TemporaryDirectory() as work, \
                patch.object(run_module.Library, "train_family", lambda self, skill, catalogue: free_form(skill)), \
                patch.object(run_module.Library, "exam_family", lambda self, skill, catalogue: []), \
                patch.object(train_module, "train", fake_train), self.assertRaises(ValueError):
            run_module.train_role({**base, "skills": ["business.finqa"], "self_worked": ("business.finqa",)}, work, diagnosis,
                                  student=Student(), library=run_module.Library())
        with self.assertRaises(SystemExit):
            run_module._names("conversation.unknown", run_module.REPLAY, "--replay")
        self.assertEqual(run_module._names("", run_module.REPLAY, "--replay"), ())
        self.assertEqual(run_module._names("code.sql, code.python", run_module.SELF_WORKED, "--self-worked"), ("code.python", "code.sql"))

    def test_sql_tasks_and_damaged_rows(self):
        from auto_rl.professor import sources
        from auto_rl.professor.records import question_hash
        context = "CREATE TABLE t (a INT); INSERT INTO t VALUES (1), (2);"
        first = sources._sql({"sql_context": context, "sql": "SELECT a FROM t WHERE a > 1", "sql_prompt": "Values above one on a given date?",
                              "sql_complexity": "basic SQL"}, "sql_test:0", "exam")
        second = sources._sql({"sql_context": context, "sql": "SELECT  a FROM t WHERE a > 1;", "sql_prompt": "Values above one on a particular date?",
                               "sql_complexity": "basic SQL"}, "sql_train:0", "train")
        self.assertEqual(question_hash(first["question"]), question_hash(second["question"]))   # reworded, same task
        self.assertIsNone(sources._trendyol({"user": None, "assistant": "x" * 100}, "t:0", "train"))

    def test_the_trainer_stops_when_an_exam_source_cannot_be_loaded(self):
        import tempfile
        from auto_rl.professor import run as run_module
        from auto_rl.professor.students import resolve
        diagnosis = {"student": {"hf": "Qwen/Qwen3-0.6B"}, "weak_points": [], "blocklist": [], "basis": None,
                     "summary": {"skills": {}}, "exam": {}}
        config = {**run_module.PROFILES["smoke"], "profile": "smoke", "student": resolve("qwen3:0.6b"), "modules": ["business"],
                  "skills": None, "cycle": 0, "budget_seconds": None, "allow_execution": False}

        def load(self, name):
            if name == "finqa_test":
                self.errors[name] = "ConnectionError: simulated"
            return [], []
        with tempfile.TemporaryDirectory() as work, patch.object(run_module.Library, "load", load), \
                self.assertRaisesRegex(ValueError, "finqa_test"):
            run_module.train_role(config, work, diagnosis, student=object(), library=run_module.Library())

    def test_mbpp_problems_are_blocked_by_task_identity_and_carry_their_tests(self):
        """MBPP+ rewords MBPP problems: 66 of the 108 shared tasks escaped a blocklist keyed on wording (2026-11-12)."""
        from auto_rl.professor import sources
        from auto_rl.professor.records import question_hash
        train_row = {"task_id": 603, "text": "Write a function to get a lucid number smaller than or equal to n.",
                     "code": "def get_ludic(n):\n    return [1, 2, 3][:n]", "test_list": ["assert get_ludic(2) == [1, 2]"],
                     "test_setup_code": "", "challenge_test_list": []}
        exam_row = {"task_id": "Mbpp/603", "prompt": "Write a function to get all lucid numbers smaller than or equal to a given integer.",
                    "code": "def get_ludic(n):\n    return []", "test_list": ["assert get_ludic(2) == [1, 2]"], "test_imports": [],
                    "test": "assert get_ludic(2) == [1, 2]"}
        train_item, exam_item = sources._mbpp(train_row, "mbpp_train:0", "train"), sources._mbpp_plus(exam_row, "mbpp_plus:0", "exam")
        self.assertEqual(question_hash(train_item["question"]), question_hash(exam_item["question"]))
        self.assertEqual(train_item["grader"]["type"], "python_tests")
        with patch.dict(os.environ, {"AURORA_PROFESSOR_ALLOW_CODE_EXECUTION": "1"}):
            self.assertTrue(grade(train_item, train_item["target"])["correct"])          # the reference passes its own tests
            self.assertFalse(grade(train_item, "```python\ndef get_ludic(n):\n    return []\n```")["correct"])

    def test_diagnoses_of_separate_modules_merge_without_hiding_their_origin(self):
        from auto_rl.professor.run import merge_diagnoses
        def diagnosis(module, skill, correct, basis=None):
            table = {"items": 60, "correct": correct, "accuracy": correct / 60, "ci95": [0.0, 1.0], "module": module}
            return {"student": {"hf": "Qwen/Qwen2.5-7B-Instruct"}, "modules": [module], "complete": True, "basis": basis,
                    "summary": {"skills": {skill: table}, "subskills": {f"{skill} / a": table}, "overall": {"skipped": 0}},
                    "blocklist": [skill[:3]], "exam": {"suite_sha256": skill}}
        candidate = diagnosis("media", "media.prompt_spec", 48, basis={"model": "candidate", "adapter_sha256": "a" * 64})
        merged = merge_diagnoses(candidate, diagnosis("conversation", "conversation.format_fr", 29))
        self.assertEqual(merged["modules"], ["conversation", "media"])
        self.assertEqual(merged["basis"]["adapter_sha256"], "a" * 64)                       # still the candidate's diagnosis
        self.assertEqual(merged["weak_points"][0]["skill"], "conversation.format_fr")
        self.assertEqual(merged["merged_from"][0]["measured_on"], {"model": "base"})        # and it says what came from the base
        self.assertEqual(merged["blocklist"], ["con", "med"])
        self.assertEqual(merged["summary"]["overall"]["items"], 120)
        with self.assertRaises(ValueError):
            merge_diagnoses(candidate, candidate)
        with self.assertRaises(ValueError):
            merge_diagnoses(candidate, {**diagnosis("conversation", "conversation.format_fr", 29), "student": {"hf": "other"}})

    def test_a_model_that_cannot_be_quantised_is_not_admitted_on_small_gpus(self):
        from auto_rl.professor.students import choose, fits, resolve
        coder, small = resolve("qwen3-coder:30b"), resolve("qwen2.5-coder:7b")
        self.assertTrue(coder["expert_tensors"])
        self.assertFalse(fits(coder, [14.7, 14.7], training=False))        # two T4s: refused, as observed on Kaggle
        self.assertTrue(fits(coder, [79.0], training=True))
        self.assertTrue(fits(small, [14.7], training=True))
        self.assertEqual(choose("missions", [14.7, 14.7])["tag"], "qwen2.5-coder:7b")

    def test_modules_cover_the_application_families(self):
        self.assertEqual(set(MODULES), {"missions", "code", "conversation", "academy", "cyber", "business", "cowork", "media", "engineering"})
        catalogue = skills()
        for module in MODULES:
            self.assertTrue(any(entry["module"] == module for entry in catalogue.values()), module)


if __name__ == "__main__":
    unittest.main()


class ReviewedGraders(unittest.TestCase):
    """Defects found by the adversarial review of 2026-11-12, each reproduced before being fixed."""

    def test_python_answers_must_let_the_tests_run_to_their_end(self):
        tests = {"type": "python_tests", "tests": "assert add(2, 3) == 5\nassert add(-1, 1) == 0", "timeout": 20}
        wrong = "```python\ndef add(a, b):\n    return a - b\n```"
        right = "```python\ndef add(a, b):\n    return a + b\n```"
        own_tests = ("```python\nimport unittest\n\ndef add(a, b):\n    return a + b\n\nclass T(unittest.TestCase):\n"
                     "    def test(self):\n        self.assertEqual(add(1, 1), 2)\n\nif __name__ == '__main__':\n    unittest.main()\n```")
        with patch.dict(os.environ, {"AURORA_PROFESSOR_ALLOW_CODE_EXECUTION": "1"}):
            self.assertTrue(grade({"grader": tests}, right)["correct"])
            for escape in ("import sys\nsys.exit(0)", "raise SystemExit", "import os\nos._exit(0)",
                           "import unittest\nunittest.main(exit=True, argv=['x'])"):
                answer = wrong.replace("\n```", "\n" + escape + "\n```")
                self.assertFalse(grade({"grader": tests}, answer)["correct"], escape)
            self.assertTrue(grade({"grader": tests}, own_tests)["correct"])            # its own __main__ block does not run
            self.assertFalse(grade({"grader": tests}, own_tests.replace("a + b", "a * b"))["correct"])

    def test_percentages_and_amounts(self):
        ratio = {"type": "numeric", "answer": "0.25", "rel_tol": 0.01, "abs_tol": 0.005, "percent_ok": True}
        self.assertFalse(grade({"grader": ratio}, "Final answer: 0")["correct"])          # passed before the review
        self.assertFalse(grade({"grader": ratio}, "Final answer: 0.003")["correct"])
        self.assertTrue(grade({"grader": ratio}, "Final answer: 25%")["correct"])
        self.assertTrue(grade({"grader": ratio}, "Final answer: 0.25")["correct"])
        amount = {"type": "numeric", "answer": "41932", "rel_tol": 0.01, "abs_tol": 0.005, "percent_ok": False}
        self.assertFalse(grade({"grader": amount}, "Final answer: 419.32")["correct"])
        self.assertTrue(grade({"grader": amount}, "Final answer: 41,932")["correct"])
        from auto_rl.professor import sources
        row = {"answer": "41932", "pre_text": ["text"], "table": [["a", "b"]], "post_text": ["more"], "question": "what was the total in 2018?",
               "id": "x-1", "gold_evidence": []}
        self.assertFalse(sources._finqa(row, "finqa_test:0", "exam")["grader"]["percent_ok"])
        self.assertTrue(sources._finqa({**row, "answer": "3.1%", "question": "what portion was paid in cash?"}, "k", "exam")["grader"]["percent_ok"])

    def test_hedged_and_negated_choices_are_not_answers(self):
        mcq = {"type": "mcq", "answer": "A", "options": 4}
        for hedge in ("A, B", "A) ou B)", "A, C ou D", "the answer is a guess: B"):
            self.assertFalse(grade({"grader": mcq}, hedge)["correct"], hedge)
        self.assertTrue(grade({"grader": mcq}, "A")["correct"])
        self.assertTrue(grade({"grader": {**mcq, "answer": "B"}}, "La réponse est B.")["correct"])
        label = {"type": "label", "answer": "positive", "labels": ["negative", "neutral", "positive"]}
        self.assertFalse(grade({"grader": label}, "Not positive")["correct"])
        self.assertTrue(grade({"grader": label}, "Positive")["correct"])

    def test_bbh_answers_keep_their_symbols_and_references_match_the_offered_options(self):
        from auto_rl.professor import sources
        adapt = lambda config, row: sources._bbh(config)(row, f"bbh:{config}:0", "exam")
        dyck = adapt("dyck_languages", {"input": "Complète la séquence : ( [ <", "target": "] ] >"})
        self.assertTrue(grade(dyck, "] ] >")["correct"])
        self.assertTrue(grade(dyck, "]]>")["correct"])
        for wrong in ("", ")", "] ] ] ]", "> ] ]"):
            self.assertFalse(grade(dyck, wrong)["correct"], wrong)
        arithmetic = adapt("multistep_arithmetic_two", {"input": "((-3 * 5) - 35) =", "target": "-50"})
        self.assertFalse(grade(arithmetic, "50")["correct"])
        self.assertTrue(grade(arithmetic, "-50")["correct"])
        fallacy = adapt("sophismes_formels", {"input": "Argument...\nOptions :\n- valide\n- invalide", "target": "invalidee"})
        self.assertTrue(grade(fallacy, "invalide")["correct"])
        self.assertNotIn("unusable", fallacy)
        boolean = adapt("expressions_booléennes", {"input": "not ( True ) and ( True ) est", "target": "Incorrect"})
        self.assertTrue(grade(boolean, "Faux")["correct"])
        self.assertFalse(grade(boolean, "Vrai")["correct"])
        sorting = adapt("tri_de_mots", {"input": "Trie ces mots par ordre alphabétique : Liste : sioux fortescue dérober percevoir timonier",
                                        "target": "fortescue timonier percept voler sioux"})
        self.assertEqual(sorting["unusable"], "reference_is_not_the_sorted_list")
        letter = adapt("noms_de_ruines", {"input": "Quelle est la parodie ? Options : (A) a (B) b (C) c (D) d", "target": "(A)"})
        self.assertEqual(letter["grader"]["type"], "mcq")
        self.assertFalse(grade(letter, "")["correct"])                                   # an empty answer passed (A) targets
        with patch("auto_rl.professor.suites.Library.exam_family", lambda self, skill, catalogue:
                   [{**sorting, "id": "hf:bbh:1", "skill": "conversation.reasoning_fr", "module": "conversation", "exam_role": "gate",
                     "question_hash": "1" * 40},
                    {**dyck, "id": "hf:bbh:2", "skill": "conversation.reasoning_fr", "module": "conversation", "exam_role": "gate",
                     "question_hash": "2" * 40}] if skill == "conversation.reasoning_fr" else []):
            exam, notes = build_exam("gate", 10, modules=["conversation"], only=["conversation.reasoning_fr"])
        self.assertEqual([i["id"] for i in exam], ["hf:bbh:2"])
        self.assertEqual(notes["unusable"], {"conversation.reasoning_fr": 1})

    def test_format_instructions_need_real_french_content(self):
        for sub in ("bullets", "lines_bounds", "json_keys", "uppercase"):
            exam = generators.generate("conversation.format_fr", "gate:2", 3, sub)
            self.assertTrue(grade(exam, exam["target"])["correct"], sub)
        bullets = generators.generate("conversation.format_fr", "gate:2", 3, "bullets")
        lines = bullets["target"].splitlines()
        placeholder = "\n".join("- x" for _ in lines[:-1]) + "\n" + lines[-1]
        self.assertFalse(grade(bullets, placeholder)["correct"])
        keys = generators.generate("conversation.format_fr", "gate:2", 3, "json_keys")
        empty = json.dumps({k: "" for k in json.loads(keys["target"])})
        self.assertFalse(grade(keys, empty)["correct"])

    def test_objects_keep_their_counts_and_relations_their_direction(self):
        for index in range(40):
            counts = generators.generate("media.prompt_translate", "gate:1", index, "counts_colors")
            self.assertTrue(grade(counts, counts["target"])["correct"])
            first, second = counts["target"].split(" and ")
            words_a, words_b = first.split(" "), second.split(" ")
            if words_a[0] != words_b[0] and words_a[0] != "a" and words_b[0] != "a":
                swapped = " ".join([words_b[0]] + words_a[1:]) + " and " + " ".join([words_a[0]] + words_b[1:])
                self.assertFalse(grade(counts, swapped)["correct"], swapped)
            relation = generators.generate("media.prompt_translate", "gate:1", index, "relations")
            self.assertTrue(grade(relation, relation["target"])["correct"])
        on = next(i for i in (generators.generate("media.prompt_translate", "gate:1", n, "relations") for n in range(200))
                  if " on " in i["target"] and " on top of " not in i["target"])
        subject, obj = on["target"].split(" on ")
        self.assertFalse(grade(on, f"{obj} on {subject}")["correct"])

    def test_a_path_seen_through_the_other_receipt_kind_is_observed(self):
        found = None
        for index in range(400):
            report = generators.generate("mission.grounded_report", "gate:0", index, "mostly_missing")
            if len(report["grader"]["accept"]) > 1:
                found = report
                break
        self.assertIsNotNone(found)
        for reading in found["grader"]["accept"]:
            self.assertTrue(grade(found, json.dumps(reading))["correct"])

    def test_results_are_never_resumed_under_another_identity(self):
        import tempfile
        from auto_rl.professor.evaluate import evaluate, read_results

        class Student:
            def __init__(self, name, answer):
                self.name, self.answer = name, answer

            def generate(self, conversations, tokens, batch_size=1):
                return [self.answer] * len(conversations)

            def describe(self):
                return {"backend": "fake", "adapter_sha256": self.name}
        items = [{"id": f"q{n}", "module": "m", "skill": "s", "subskill": "x", "messages": [{"role": "user", "content": f"{n}?"}],
                  "grader": {"type": "numeric", "answer": "1"}, "max_new_tokens": 8} for n in range(5)]
        with tempfile.TemporaryDirectory() as folder:
            evaluate(Student("A", "1"), items, folder)
            receipt = evaluate(Student("B", "2"), items, folder)            # same folder, another adapter
            self.assertEqual(receipt["summary"]["overall"]["correct"], 0)    # B's own answers, not A's
            self.assertTrue(all(row["output"] == "2" for row in read_results(folder)))
            self.assertEqual(len(list(Path(folder).glob("results.stale-*.jsonl"))), 1)
            again = evaluate(Student("B", "2"), items, folder)             # same identity: resumed, nothing regenerated
            self.assertEqual(again["graded_rows"], 5)


class ReviewedVerdicts(unittest.TestCase):
    """Second review of 2026-11-12: verdict statistics and installability."""

    def rows(self, marks, skill="s", prefix="i"):
        return [{"id": f"{prefix}{n}", "module": "m", "skill": skill, "subskill": "x", "status": "graded",
                 "correct": bool(m), "output": "x"} for n, m in enumerate(marks)]

    def test_thresholds_are_decided_exactly(self):
        # A gain of exactly 1/50 whose floating-point difference falls just below 0.02.
        n = 500
        k = next(k for k in range(n - 10) if (k + 10) / n - k / n < 0.02)
        base, candidate = self.rows([1] * k + [0] * (n - k)), self.rows([1] * (k + 10) + [0] * (n - k - 10))
        result = compare(base, candidate, gate={"min_items": 10})
        self.assertLess(result["overall"]["macro_gain"], 0.02)                      # the float, as computed
        self.assertGreater(result["overall"]["macro_gain_ci"][0], 0)
        self.assertEqual(result["verdict"], "promote")                              # the exact gain meets the rule
        # An empty-answer rise of exactly 0.02 (30 -> 32 of 100) is allowed; only a rise above it rejects.
        base = [dict(r, output="" if i < 30 else "x", correct=i >= 30) for i, r in enumerate(self.rows([1] * 100))]
        candidate = [dict(r, output="" if i < 32 else "x", correct=i >= 32) for i, r in enumerate(self.rows([1] * 100))]
        self.assertNotEqual(compare(base, candidate, gate={"min_items": 10})["verdict"], "reject")
        candidate = [dict(r, output="" if i < 33 else "x", correct=i >= 33) for i, r in enumerate(self.rows([1] * 100))]
        self.assertEqual(compare(base, candidate, gate={"min_items": 10})["verdict"], "reject")

    def verify_run(self, folder, *, previous_marks=None, continued=True, cut_previous=False, execution=True, profile="standard"):
        from auto_rl.professor import run as run_module
        from auto_rl.professor.students import resolve
        config = {**run_module.PROFILES[profile], "profile": profile, "student": resolve("qwen2.5-coder:7b"), "modules": ["missions"],
                  "skills": None, "cycle": 1, "budget_seconds": None, "allow_execution": execution, "export": "never",
                  "gate_per_skill": 60, "four_bit": None}
        with patch("auto_rl.professor.suites.Library.load", return_value=([], [])):
            items, _ = run_module._exam(config, "gate", run_module.Library())
        def target(item_id):                         # gen:<family>:<role, may hold ":">:<subskill>:<index>
            parts = item_id.split(":")
            return generators.generate(parts[1], ":".join(parts[2:-2]), int(parts[-1]), parts[-2])["target"]
        targets = {item["messages"][-1]["content"]: target(item["id"]) for item in items}
        adapters = {}
        for name in ("candidate", "previous"):
            path = Path(folder) / name
            path.mkdir()
            (path / "adapter_model.safetensors").write_bytes(name.encode())
            adapters[name] = path
        atomic = __import__("auto_rl.professor.records", fromlist=["atomic_json"]).atomic_json
        atomic(adapters["candidate"].parent / "train_receipt.json",
               {"steps": 1, "continued_from": {"adapter_sha256": __import__("hashlib").sha256(b"previous").hexdigest()} if continued else None})

        class Student:
            adapter = None

            def attach(self, adapter):
                self.adapter = Path(adapter).name

            def detach(self):
                self.adapter = None

            def describe(self):
                return {"backend": "fake", "adapter": self.adapter}

            def generate(self, conversations, tokens, batch_size=1):
                answers = []
                for messages in conversations:
                    prompt = messages[-1]["content"]
                    right = self.adapter == "candidate" or (self.adapter == "previous" and previous_marks and hash(prompt) % 3 == 0)
                    answers.append(targets[prompt] if right else "{}")
                return answers
        student = Student()
        original = run_module.evaluate

        def evaluate(student_, items_, folder_, **options):
            if cut_previous and Path(folder_).name == "previous":
                items_ = items_[:len(items_) // 3]
            return original(student_, items_, folder_, **{k: v for k, v in options.items() if k != "budget_seconds"})
        with patch("auto_rl.professor.suites.Library.load", return_value=([], [])), patch.object(run_module, "evaluate", evaluate):
            return run_module.verify(config, Path(folder) / "work", adapters["candidate"], student=student, library=run_module.Library(),
                                     previous=adapters["previous"] if previous_marks else None)

    def test_a_continued_candidate_needs_a_complete_comparison_with_the_adapter_it_continues(self):
        import tempfile
        from auto_rl.professor import install
        with tempfile.TemporaryDirectory() as folder:
            complete = self.verify_run(folder, previous_marks=True)
        self.assertEqual(complete["verdict"], "promote")
        self.assertTrue(complete["promotable"], complete["not_installable"])
        self.assertTrue(complete["versus_previous"]["complete"])
        with tempfile.TemporaryDirectory() as folder:
            missing = self.verify_run(folder, previous_marks=None)
        self.assertFalse(missing["promotable"])
        self.assertTrue(any("même examen" in p for p in missing["not_installable"]))
        with tempfile.TemporaryDirectory() as folder:
            cut = self.verify_run(folder, previous_marks=True, cut_previous=True)
        self.assertFalse(cut["promotable"])
        self.assertTrue(any("incomplète" in p for p in cut["not_installable"]))
        self.assertTrue(any("incomplète" in p for p in install.installable_problems(cut)))
        with tempfile.TemporaryDirectory() as folder:
            fresh = self.verify_run(folder, previous_marks=None, continued=False)
        self.assertTrue(fresh["promotable"], fresh["not_installable"])

    def test_a_rehearsal_sized_exam_never_authorises_an_installation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            small = self.verify_run(folder, previous_marks=None, continued=False, profile="smoke")
        self.assertFalse(small["promotable"])
        self.assertTrue(any("répétition" in p for p in small["not_installable"]))

    def test_the_report_prints_a_missing_loss_and_the_reasons(self):
        from auto_rl.professor.report import verdict_lines
        verdict = {"cycle": 1, "student": {"tag": "qwen2.5:7b"}, "verdict": "promote", "promotable": False,
                   "not_installable": ["examen incomplet"], "reasons": ["r"], "exam_complete": False,
                   "exam": {"notes": {"skipped_no_execution": ["code.python"]}},
                   "overall": {"items": 3, "macro_base": 0.1, "macro_candidate": 0.2, "macro_gain": 0.1, "macro_gain_ci": [0.0, 0.2],
                               "fixed": 1, "broken": 0, "mcnemar_p": 1.0},
                   "skills": {}, "regressions": [], "training": {"steps": 3, "stopped": "out_of_memory",
                                                                  "initial_dev_loss": 1.0, "selected_dev_loss": None}}
        text = "\n".join(verdict_lines(verdict))
        self.assertIn("n/a", text)
        self.assertIn("non installable : examen incomplet", text)
        self.assertIn("code.python", text)

    def test_results_survive_a_cut_last_line_and_identity_covers_the_answer_budget(self):
        import tempfile
        from auto_rl.professor.evaluate import read_results, run_identity

        class Student:
            def describe(self):
                return {"backend": "fake"}
        item_ = {"id": "q", "messages": [{"role": "user", "content": "?"}], "grader": {"type": "numeric", "answer": "1"}, "max_new_tokens": 8}
        self.assertNotEqual(run_identity(Student(), [item_]), run_identity(Student(), [{**item_, "max_new_tokens": 9}]))
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "results.jsonl").write_text('{"id": "a", "status": "graded"}\n{"id": "b", "stat')
            self.assertEqual([r["id"] for r in read_results(folder)], ["a"])


class ReviewedTraining(unittest.TestCase):
    """Second review of 2026-11-12: what the trainer really trains on."""

    def test_numbers_with_a_leading_point_and_unfinished_final_answers(self):
        five = {"type": "numeric", "answer": "5"}
        self.assertFalse(grade({"grader": five}, "Final answer: .5")["correct"])
        self.assertTrue(grade({"grader": {"type": "numeric", "answer": ".4"}}, "Final answer: .4")["correct"])
        self.assertTrue(grade({"grader": {"type": "numeric", "answer": "-0.62"}}, "Final answer: -.62")["correct"])
        cut = {"type": "numeric", "answer": "663750000", "rel_tol": 0.01, "abs_tol": 0.005}
        self.assertFalse(grade({"grader": cut}, "= $663,750,000\n\nFinal answer: $")["correct"])     # cut before its number

    def test_the_development_split_keeps_equal_prompts_together(self):
        from auto_rl.professor.train import development_split
        encoded = [{"id": f"e{n}", "prompt_key": f"p{n % 7}"} for n in range(140)]
        dev, fit = development_split(encoded, 0.05)
        self.assertFalse({e["prompt_key"] for e in dev} & {e["prompt_key"] for e in fit})
        self.assertGreaterEqual(len(dev), 7)

    def test_generated_training_pools_hold_distinct_exercises(self):
        with patch("auto_rl.professor.suites.Library.load", return_value=([], [])):
            pool, _ = build_pool(400, modules=["conversation"], only=["conversation.format_fr"])
        pairs = [(i["question_hash"], i["target"]) for i in pool["conversation.format_fr"]]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_replay_stays_at_its_share_of_what_is_trained(self):
        pool = {"weak": [{"id": f"w{n}", "module": "m", "skill": "weak"} for n in range(100)],
                "replay": [{"id": f"r{n}", "module": "m", "skill": "replay"} for n in range(1000)]}
        chosen, plan = build_curriculum(pool, {"weak": 1.0}, 4000, replay_skills=("replay",))
        share = sum(i["skill"] == "replay" for i in chosen) / len(chosen)
        self.assertLessEqual(share, 0.16)                       # 100 drill items: replay follows them, not the request

    def test_the_trainer_refuses_what_it_cannot_train_correctly(self):
        import tempfile
        from auto_rl.professor import run as run_module
        from auto_rl.professor.run import keep_verified_answers
        from auto_rl.professor.students import resolve
        notes = keep_verified_answers({"s": [{"id": "a"}, {"id": "b"}]}, {"s": [{"id": "a"}, {"id": "b"}]},
                                      [{"id": "a", "skill": "s", "correct": True, "output": "x", "cut": True},
                                       {"id": "b", "skill": "s", "correct": True, "output": "y"}])
        self.assertEqual(notes["s"]["verified"], 1)              # the answer cut by its budget is not a target
        base = {"student": {"hf": "Qwen/Qwen3-0.6B"}, "weak_points": [], "blocklist": [], "basis": None, "summary": {"skills": {}},
                "exam": {}, "complete": True}
        config = {**run_module.PROFILES["smoke"], "profile": "smoke", "student": resolve("qwen3:0.6b"), "modules": ["business"],
                  "skills": None, "cycle": 1, "budget_seconds": None, "allow_execution": False}
        with self.assertRaisesRegex(ValueError, "incomplete"):
            run_module.train_role(config, "unused", {**base, "complete": False}, student=object(), library=object())
        merged = {**base, "merged_from": [{"measured_on": {"model": "candidate", "exam": "gate:1"}}]}
        with self.assertRaisesRegex(ValueError, "cycle >= 2"):
            run_module.train_role(config, "unused", merged, student=object(), library=object())

        def load(self, name):
            if name == "finqa_train":
                self.errors[name] = "ConnectionError: simulated 429"
            return [], []
        with tempfile.TemporaryDirectory() as work, patch.object(run_module.Library, "load", load), \
                self.assertRaisesRegex(ValueError, "finqa_train"):
            run_module.train_role(config, work, base, student=object(), library=run_module.Library())

    def test_a_continued_cycle_in_the_same_folder_keeps_the_adapter_it_continues(self):
        import hashlib
        import tempfile
        from auto_rl.professor import run as run_module, train as train_module
        from auto_rl.professor.students import resolve
        with tempfile.TemporaryDirectory() as work:
            adapter = Path(work) / "training" / "adapter"
            adapter.mkdir(parents=True)
            (adapter / "adapter_model.safetensors").write_bytes(b"cycle-0 weights")
            (adapter / "adapter_config.json").write_text("{}")
            original = hashlib.sha256(b"cycle-0 weights").hexdigest()
            diagnosis = {"student": {"hf": "Qwen/Qwen3-0.6B"}, "weak_points": [], "blocklist": [], "complete": True,
                         "basis": {"model": "candidate", "exam": "gate:0", "adapter_sha256": original}, "summary": {"skills": {}}, "exam": {}}
            config = {**run_module.PROFILES["smoke"], "profile": "smoke", "student": resolve("qwen3:0.6b"), "modules": ["engineering"],
                      "skills": None, "cycle": 1, "budget_seconds": None, "allow_execution": False, "mine_per_skill": 1,
                      "self_worked": (), "replay": (), "curriculum": 20}
            seen = {}

            class Student:
                def attach(self, path):
                    seen["mined_with"] = hashlib.sha256((Path(path) / "adapter_model.safetensors").read_bytes()).hexdigest()

                def detach(self):
                    pass

                def describe(self):
                    return {"backend": "fake"}

                def generate(self, conversations, tokens, batch_size=1):
                    return ["0"] * len(conversations)

            def fake_train(student, items, folder, init_adapter=None, **options):
                seen["continued"] = hashlib.sha256((Path(init_adapter) / "adapter_model.safetensors").read_bytes()).hexdigest()
                (Path(folder) / "adapter" / "adapter_model.safetensors").write_bytes(b"cycle-1 weights")   # what train() does
                return {"steps": 1}
            with patch.object(run_module.Library, "load", lambda self, name: ([], [])), patch.object(train_module, "train", fake_train):
                run_module.train_role(config, work, diagnosis, student=Student(), library=run_module.Library(), init_adapter=adapter)
            kept = hashlib.sha256((Path(work) / "training" / "init_adapter" / "adapter_model.safetensors").read_bytes()).hexdigest()
        self.assertEqual(seen["continued"], original)
        self.assertEqual(kept, original)                          # the examiner compares with what was really continued


class ReviewedFixes(unittest.TestCase):
    """Third look, at the fixes themselves (2026-11-12)."""

    def test_explicit_percentages_and_small_references(self):
        ratio = {"type": "numeric", "answer": "-0.42424", "rel_tol": 0.01, "abs_tol": 0.005, "percent_ok": False}
        self.assertTrue(grade({"grader": ratio}, "Final answer: -42.42%")["correct"])
        self.assertTrue(grade({"grader": {**ratio, "answer": "0.3781"}}, "Final answer: 37.81 %")["correct"])
        self.assertFalse(grade({"grader": {**ratio, "answer": "0.003"}}, "Final answer: 0%")["correct"])
        self.assertFalse(grade({"grader": {**ratio, "answer": "0.003"}}, "Final answer: 0")["correct"])
        self.assertTrue(grade({"grader": {**ratio, "answer": "0"}}, "Final answer: 0.004")["correct"])     # a zero reference keeps it
        from auto_rl.professor import sources
        self.assertIsNone(sources._PERCENT_WORDS.search("what is the price of ball corporation in 2010?"))
        self.assertIsNone(sources._PERCENT_WORDS.search("how many shareholders were there?"))
        self.assertIsNotNone(sources._PERCENT_WORDS.search("what was the growth rate?"))

    def test_a_single_stated_answer_may_explain_the_other_options(self):
        mcq = {"type": "mcq", "answer": "C", "options": 4}
        for text in ("C\n\nExplication : les options A et B ignorent le frottement.",
                     "La bonne réponse est C ; A, B et D sont des distracteurs.",
                     "The correct answer is (C), because options A and B ignore friction."):
            self.assertTrue(grade({"grader": mcq}, text)["correct"], text)
        self.assertTrue(grade({"grader": {"type": "mcq", "answer": "B", "options": 10}}, "Answer: B, I think.")["correct"])
        self.assertFalse(grade({"grader": {"type": "mcq", "answer": "A", "options": 4}}, "A, B")["correct"])

    def test_correct_short_french_is_french(self):
        rule = {"type": "constraints", "rules": [{"kind": "content", "unit": "lines", "min_words": 3}]}
        for text in ("GARDE-LE SECRET.", "Réduisez vos dépenses non essentielles.", "N'oublie pas l'eau."):
            self.assertTrue(grade({"grader": rule}, text)["correct"], text)
        for text in ("X", "BUDGET GESTION", "x x x"):
            self.assertFalse(grade({"grader": rule}, text)["correct"], text)

    def test_only_exam_sources_count_as_exam_gaps(self):
        from auto_rl.professor.suites import Library

        def load(self, name):
            if name == "aya_fr":                                  # a training source
                self.errors[name] = "simulated"
            return [], []
        with patch.object(Library, "load", load):
            library = Library()
            library.load("aya_fr")
            _, notes = build_exam("gate", 10, modules=["conversation"], library=library)
        self.assertNotIn("aya_fr", notes["source_errors"])

    def test_a_verdict_on_the_gate_that_steered_its_training_is_not_installable(self):
        from auto_rl.professor.run import installable_problems
        verdict = {"verdict": "promote", "exam_complete": True, "student": {"tag": "qwen2.5:7b"}, "gate": {"min_items": 200},
                   "cycle": 1, "training": {"diagnosis_gate": 1}}
        self.assertTrue(any("orienté" in p for p in installable_problems(verdict)))
        self.assertEqual(installable_problems({**verdict, "cycle": 2}), [])
