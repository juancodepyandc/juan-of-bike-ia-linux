"""Automatic reading of an exam beyond its verdict (analysis.py), and its use by the autopilot.

The examiner output is a temporary folder with hand-written answers; items come from an in-memory table,
so nothing is downloaded. These tests prove the categories, the flags and the advice, not a real exam.
"""
import json
import tempfile
import unittest
from pathlib import Path

from auto_rl.professor import analysis, autopilot
from auto_rl.professor.records import atomic_json


class Table:
    """Items by identifier, in place of the generators and pinned sources."""

    def __init__(self, items):
        self.items = items

    def get(self, item_id):
        return self.items.get(item_id)


QA = {"grader": {"type": "text", "answers": ["Hans Asperger"], "f1_threshold": 0.7}}
CALL = {"grader": {"type": "tool_call", "calls": [{"name": "get_vm", "arguments": {"frame": "intraday"}}]}}
JSON = {"grader": {"type": "json", "accept": [{"total": 523}]}}
LABEL = {"grader": {"type": "label", "labels": ["positive", "neutral", "negative"], "answer": "neutral"}}


def row(item_id, skill, correct, output, reason="x"):
    return {"id": item_id, "skill": skill, "module": skill.split(".")[0], "subskill": "s", "status": "graded",
            "correct": correct, "reason": reason, "output": output}


def exam(folder, cycle, answers, *, skills_table=None):
    """Write an examiner output: verdict_N.json and gate_N/{base,previous,candidate}/results.jsonl."""
    work = Path(folder) / "aurora_professor"
    atomic_json(work / f"verdict_{cycle}.json", {"kind": "aurora_professor_verdict", "cycle": cycle, "verdict": "promote",
                                                "student": {"tag": "qwen2.5:7b"}, "versus_previous": {"verdict": "promote",
                                                "skills": skills_table or {}}})
    for model, rows in answers.items():
        path = work / f"gate_{cycle}" / model / "results.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    return Path(folder)


class Understanding(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def test_errors_are_explained_and_suspicious_ones_flagged(self):
        items, answers = {}, {"base": [], "previous": [], "candidate": []}
        for n in range(6):                                    # right answer buried in a sentence
            items[f"qa{n}"] = QA
            for model in answers:
                answers[model].append(row(f"qa{n}", "cowork.extract_qa_fr", False, "Hans Asperger avait noté cela.", "f1"))
        for n in range(6):                                    # differs by case only
            items[f"call{n}"] = CALL
            for model in answers:
                answers[model].append(row(f"call{n}", "cowork.tool_call", False,
                                          '<tool_call>\n{"name": "get_vm", "arguments": {"frame": "Intraday"}}\n</tool_call>', "call_differs"))
        for n in range(6):                                    # JSON wrapped under the schema title
            items[f"json{n}"] = JSON
            for model in answers:
                answers[model].append(row(f"json{n}", "cowork.json_schema", False, '{"Dashboard": {"total": 523}}', "json_differs"))
        report = analysis.analyse(exam(self.root / "e", 5, answers), items=Table(items))
        skills = report["skills"]
        self.assertEqual(skills["cowork.extract_qa_fr"]["errors"], {"reponse_juste_mais_verbeuse": 6})
        self.assertEqual(skills["cowork.tool_call"]["errors"], {"casse_seulement": 6})
        self.assertEqual(skills["cowork.json_schema"]["errors"], {"json_emballe_sous_une_cle": 6})
        self.assertTrue(any(f.startswith("concision") for f in skills["cowork.extract_qa_fr"]["flags"]))
        self.assertTrue(any("casse" in f for f in skills["cowork.tool_call"]["flags"]))
        self.assertTrue(any(f.startswith("format") for f in skills["cowork.json_schema"]["flags"]))
        advice = analysis.recommend([report])
        self.assertEqual(advice["concision"], ["cowork.extract_qa_fr"])
        self.assertIn("cowork.tool_call", advice["review_grader"])

    def test_a_label_shift_and_a_regression_are_reported_with_examples(self):
        items, answers = {}, {"base": [], "previous": [], "candidate": []}
        for n in range(20):
            items[f"s{n}"] = LABEL
            answers["base"].append(row(f"s{n}", "business.sentiment", True, "neutral", "label"))
            answers["previous"].append(row(f"s{n}", "business.sentiment", True, "neutral", "label"))
            broken = n < 6
            answers["candidate"].append(row(f"s{n}", "business.sentiment", not broken, "positive" if broken else "neutral", "label"))
        entry = analysis.analyse(exam(self.root / "e", 2, answers), items=Table(items))["skills"]["business.sentiment"]
        self.assertEqual(entry["broken_by_candidate"], 6)
        self.assertEqual(entry["labels"]["expected"], {"neutral": 20})
        self.assertEqual(entry["labels"]["candidate"], {"neutral": 14, "positive": 6})
        self.assertEqual(len(entry["broken_examples"]), analysis.EXAMPLES)
        self.assertTrue(any(f.startswith("baisse de 30.0 points") for f in entry["flags"]))

    def test_a_skill_stuck_two_cycles_is_dropped_but_one_near_its_ceiling_stays(self):
        def cycle(number, stuck_accuracy):
            items, answers = {}, {"base": [], "previous": [], "candidate": []}
            for n in range(20):
                for skill, accuracy in (("business.fin_math", stuck_accuracy), ("conversation.format_fr", 0.95)):
                    item_id = f"{skill}{n}"
                    items[item_id] = {"grader": {"type": "numeric"}}
                    right = n < int(20 * accuracy)
                    for model in answers:
                        answers[model].append(row(item_id, skill, right, "42", "number_compared"))
            curriculum = {"plan": {"skills": {"business.fin_math": {"selected": 300}, "conversation.format_fr": {"selected": 80}}}}
            return analysis.analyse(exam(self.root / f"e{number}", number, answers), curriculum=curriculum, items=Table(items))
        first, second = cycle(3, 0.2), cycle(4, 0.2)
        self.assertEqual([s["skill"] for s in first["side_effects"]["trained_stuck"]], ["business.fin_math"])
        self.assertEqual(analysis.recommend([first])["exclude"], [])                 # one cycle is not enough
        self.assertEqual(analysis.recommend([first, second])["exclude"], ["business.fin_math"])
        self.assertNotIn("conversation.format_fr", analysis.recommend([first, second])["exclude"])

    def test_the_autopilot_keeps_the_advice_and_the_next_plan_leaves_the_stuck_skill_out(self):
        plan = autopilot.plan("qwen2.5:7b", {"trained_modules": ["cowork"]}, exclude=["cowork.tool_call"])
        self.assertNotIn("cowork.tool_call", plan["skills"])
        self.assertIn("cowork.extract_qa_fr", plan["skills"])

        class Kaggle:
            def reference(self, owner, role, student, cycle):
                return f"{owner}/{role}-{cycle}"

            def curriculum(self, reference, folder):
                return {"plan": {"skills": {"cowork.extract_qa_fr": {"selected": 700}}}}
        items, answers = {}, {"base": [], "previous": [], "candidate": []}
        for n in range(6):
            items[f"qa{n}"] = QA
            for model in answers:
                answers[model].append(row(f"qa{n}", "cowork.extract_qa_fr", False, "Hans Asperger avait noté cela.", "f1"))
        folder = exam(self.root / "kernel", 6, answers)
        state = {"owner": "o", "events": []}
        entry = {}
        original = analysis.Items
        analysis.Items = lambda library=None: Table(items)
        try:
            with unittest.mock.patch.object(autopilot, "AUTOPILOT", self.root / "auto"):
                report = autopilot.understand(state, "qwen2.5:7b", entry, Kaggle(), folder, 6)
        finally:
            analysis.Items = original
        self.assertEqual(report["trained"], {"cowork.extract_qa_fr": 700})
        self.assertEqual(entry["advice"]["concision"], ["cowork.extract_qa_fr"])
        self.assertTrue((self.root / "auto" / "qwen2-5-7b" / "c6" / "analysis.json").is_file())
        self.assertTrue(any("concision" in e["message"] for e in state["events"]))

    def test_a_failed_analysis_is_reported_and_does_not_stop_the_loop(self):
        class Kaggle:
            def reference(self, *args):
                return "o/x"

            def curriculum(self, reference, folder):
                raise ConnectionError("down")
        state, entry = {"owner": "o", "events": []}, {}
        self.assertIsNone(autopilot.understand(state, "qwen2.5:7b", entry, Kaggle(), self.root, 1))
        self.assertIn("analyse des résultats impossible", state["events"][-1]["message"])


import unittest.mock  # noqa: E402  (used inside a test above)

if __name__ == "__main__":
    unittest.main()
