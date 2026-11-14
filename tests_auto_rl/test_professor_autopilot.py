"""The professor autopilot as a state machine.

Kaggle and the PC installer are SIMULATED (in-memory kernels, recorded calls): these tests prove the order
of the steps and the decisions, not that a real kernel ran or a model was installed.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_rl.professor import autopilot
from auto_rl.professor.records import atomic_json
from auto_rl.professor.students import resolve
from auto_rl.professor.suites import skills

NOW = 1_800_000_000.0


def served_tables(tag):
    modules = resolve(tag).get("modules") or []
    return {name: {"items": 120} for name, entry in skills(modules).items() if entry["generator"] or entry["exam_sources"]}


def verdict(tag, cycle, *, installable=True, continued=None):
    """A verdict the real installability rule accepts (or refuses, with ``installable=False``)."""
    tables = served_tables(tag)
    found = {"kind": "aurora_professor_verdict", "verdict": "promote" if installable else "reject", "exam_complete": True,
             "student": {"tag": tag}, "gate": {"min_items": 200}, "cycle": cycle, "skills": tables,
             "modules": {module: {"items": 100} for module in resolve(tag)["modules"]},
             "overall": {"macro_gain": 0.05, "macro_gain_ci": [0.02, 0.08]}, "adapter_sha256": f"sha-{cycle}",
             "training": {"continued_from": {"adapter_sha256": continued} if continued else None, "diagnosis_gate": cycle - 1}}
    if continued:
        found["versus_previous"] = {"verdict": "promote", "complete": True, "adapter_sha256": continued, "regressions": []}
    return found


class FakeKaggle:
    def __init__(self, tag, *, quota=100_000.0, refresh_at=NOW + 7200):
        self.tag = tag
        self.kernels = {}          # reference -> {"status", "verdict", "diagnosis"}
        self.quota_left, self.refresh_at = quota, refresh_at
        self.launched, self.published, self.fetched = [], [], []

    def owner(self):
        return "owner"

    def quota(self):
        return {"remaining_seconds": self.quota_left, "refresh_at": self.refresh_at}

    def reference(self, owner, role, student, cycle):
        kind = "entraineur" if role == "train" else "examinateur"
        return f"{owner}/{kind}-{autopilot.slug(student)}-c{cycle}"

    def add(self, role, cycle, status="complete", **content):
        self.kernels[self.reference("owner", role, self.tag, cycle)] = {"status": status, **content}

    def cycles(self, owner, student):
        found = {"train": set(), "verify": set()}
        for reference in self.kernels:
            kind, cycle = reference.split("/")[1].split("-")[0], int(reference.rsplit("-c", 1)[1])
            found["train" if kind == "entraineur" else "verify"].add(cycle)
        return found

    def status(self, reference):
        return self.kernels[reference]["status"]

    def trained_modules(self, reference, folder):
        return self.kernels[reference].get("trained_modules", [])

    def curriculum(self, reference, folder):
        return self.kernels.get(reference, {}).get("curriculum")

    def verdict(self, reference, folder):
        return self.kernels.get(reference, {}).get("verdict")

    def fetch(self, reference, folder):
        self.fetched.append(reference)
        folder = Path(folder)
        kernel = self.kernels[reference]
        work = folder / "aurora_professor"
        if kernel.get("verdict"):
            cycle = kernel["verdict"]["cycle"]
            atomic_json(work / f"verdict_{cycle}.json", kernel["verdict"])
            (work / "training" / "adapter").mkdir(parents=True)
            (work / "training" / "adapter" / "adapter_model.safetensors").write_bytes(b"w")
            if kernel.get("diagnosis_next", True):
                atomic_json(work / f"diagnosis_next_{cycle}.json", {"trained_modules": ["cowork"]})
        if kernel.get("diagnosis"):
            atomic_json(work / "diagnosis.json", kernel["diagnosis"])
        atomic_json(folder / "aurora_professor_manifest.json", {"files": {}})
        return {"files": {}}

    def publish(self, owner, training, student, extra, note):
        self.published.append((Path(training).name, [Path(path).name for path in extra]))
        return f"{owner}/adapters-{autopilot.slug(student)}"

    def launch(self, folder, owner, role, student, **options):
        reference = self.reference(owner, "train" if role == "train" else "verify", student, options["cycle"])
        self.kernels[reference] = {"status": "running"}
        self.launched.append((role, options["cycle"], options))
        return reference


class FakeInstaller:
    def __init__(self, *, reachable=True, deployment="promote"):
        self.reachable, self.deployment = reachable, deployment
        self.installed, self.activated = {}, []

    def check_ollama(self):
        if not self.reachable:
            raise ConnectionError("refused")

    def installed_cycles(self, student):
        return dict(self.installed)

    def install(self, folder):
        cycle = int(Path(folder).parent.name[1:])
        self.installed[cycle] = False
        return {"candidate_tag": f"x-aurora-renforce-c{cycle}", "deployment": {"verdict": self.deployment}}

    def activate(self, tag, candidate):
        self.activated.append((tag, candidate))


class Autopilot(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        root = Path(self.folder.name)
        self.patches = [patch.object(autopilot, "AUTOPILOT", root), patch.object(autopilot, "STATE_FILE", root / "state.json"),
                        patch.object(autopilot, "STOP_FILE", root / "STOP")]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.folder.cleanup()

    def state(self, tag):
        state = autopilot.load()
        state.update(enabled=True, order=[tag])
        return state

    def test_it_resumes_the_real_situation_delivers_the_best_cycle_first_and_waits_for_the_quota(self):
        tag = "qwen2.5:7b"
        kaggle, installer = FakeKaggle(tag, quota=6053.0), FakeInstaller()
        for cycle in range(4):
            kaggle.add("train", cycle)
        kaggle.add("train", 4, trained_modules=["business", "conversation", "cowork", "media"])
        kaggle.add("verify", 1, verdict=verdict(tag, 1, installable=False))
        kaggle.add("verify", 2, verdict=verdict(tag, 2, installable=False))
        kaggle.add("verify", 3, verdict=verdict(tag, 3, continued="sha-1"))
        state = self.state(tag)
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "discovered")
        entry = state["students"][tag]
        self.assertEqual((entry["phase"], entry["cycle"], entry["best_cycle"], entry["deliveries"]), ("trained", 4, 3, [3]))
        # The verified cycle reaches the PC before any new GPU work.
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "delivered")
        self.assertEqual(installer.activated, [("qwen2.5:7b", "x-aurora-renforce-c3")])
        self.assertEqual(entry["installed_cycle"], 3)
        # 6 053 s left: the three-model exam waits for the renewal instead of being cut.
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "waiting_quota")
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW + 60), "idle")
        self.assertEqual(kaggle.launched, [])
        kaggle.quota_left = 108_000.0
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW + 7300), "launched")
        role, cycle, options = kaggle.launched[-1]
        self.assertEqual((role, cycle), ("verify", 4))
        self.assertEqual(options["modules"], "business,conversation,cowork,media")      # cycle 4 trained Cowork: it is examined
        self.assertEqual(options["overrides"], {"gate_per_skill": "120"})

    def test_a_won_exam_becomes_the_next_starting_point_and_is_activated(self):
        tag = "qwen2.5:7b"
        kaggle, installer = FakeKaggle(tag), FakeInstaller()
        kaggle.add("train", 3)
        kaggle.add("verify", 3, verdict=verdict(tag, 3, continued="sha-1"))
        installer.installed = {3: True}
        state = self.state(tag)
        autopilot.tick(state, kaggle, installer, now=NOW)
        entry = state["students"][tag]
        self.assertEqual((entry["phase"], entry["next_cycle"], entry["deliveries"]), ("ready", 4, []))
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "launched")
        role, cycle, options = kaggle.launched[-1]
        self.assertEqual((role, cycle), ("train", 4))
        self.assertTrue(options["continue_adapter"])
        self.assertEqual(options["modules"], "business,conversation,cowork,media")      # the diagnosis names cowork as trained
        self.assertIn("cowork.extract_qa_fr", options["skills"])
        self.assertNotIn("conversation.translation", options["skills"])
        self.assertEqual(kaggle.published, [("training", ["diagnosis_next_3.json"])])
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW + 300), "running")
        kaggle.kernels[kaggle.reference("owner", "train", tag, 4)]["status"] = "complete"
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW + 600), "advanced")
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW + 600), "launched")
        exam = kaggle.reference("owner", "verify", tag, 4)
        kaggle.kernels[exam].update(status="complete", verdict=verdict(tag, 4, continued="sha-3"))
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW + 900), "concluded")
        self.assertEqual((entry["best_cycle"], entry["deliveries"], entry["next_cycle"]), (4, [4], 5))
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW + 900), "delivered")
        self.assertEqual(installer.activated[-1], ("qwen2.5:7b", "x-aurora-renforce-c4"))

    def test_refused_verdicts_keep_the_model_in_use_and_pause_the_student(self):
        tag = "qwen2.5-coder:7b"
        kaggle, installer = FakeKaggle(tag), FakeInstaller()
        kaggle.add("train", 0)
        kaggle.add("verify", 0, verdict=verdict(tag, 0))
        installer.installed = {0: True}
        state = self.state(tag)
        autopilot.tick(state, kaggle, installer, now=NOW)
        entry = state["students"][tag]
        for cycle in (1, 2):
            self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "launched")
            self.assertEqual(kaggle.launched[-1][2]["skills"], "code.python,code.sql,mission.action,mission.evidence,mission.pointer")
            kaggle.kernels[kaggle.reference("owner", "train", tag, cycle)]["status"] = "complete"
            autopilot.tick(state, kaggle, installer, now=NOW)
            autopilot.tick(state, kaggle, installer, now=NOW)
            exam = kaggle.reference("owner", "verify", tag, cycle)
            kaggle.kernels[exam].update(status="complete", verdict=verdict(tag, cycle, installable=False))
            result = autopilot.tick(state, kaggle, installer, now=NOW)
        self.assertEqual(result, "stalled")
        self.assertEqual((entry["phase"], entry["best_cycle"], entry["deliveries"]), ("stalled", 0, []))
        self.assertEqual(installer.activated, [])
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "idle")
        autopilot.save(state)
        autopilot.resume(tag)
        self.assertEqual(autopilot.load()["students"][tag]["phase"], "new")

    def test_a_failed_kernel_is_tried_again_on_the_same_unseen_cycle_then_pauses(self):
        tag = "qwen2.5:7b"
        kaggle, installer = FakeKaggle(tag), FakeInstaller()
        kaggle.add("train", 3)
        kaggle.add("verify", 3, verdict=verdict(tag, 3, continued="sha-1"))
        installer.installed = {3: True}
        state = self.state(tag)
        autopilot.tick(state, kaggle, installer, now=NOW)
        entry = state["students"][tag]
        for attempt in (1, 2):
            self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "launched")
            self.assertEqual(kaggle.launched[-1][1], 4)
            kaggle.kernels[kaggle.reference("owner", "train", tag, 4)]["status"] = "error"
            result = autopilot.tick(state, kaggle, installer, now=NOW)
        self.assertEqual(result, "stalled")
        self.assertEqual(entry["failures_in_a_row"], 2)

    def test_an_unreachable_ollama_postpones_the_delivery_without_blocking_the_gpu_work(self):
        tag = "qwen2.5:7b"
        kaggle, installer = FakeKaggle(tag), FakeInstaller(reachable=False)
        kaggle.add("train", 3)
        kaggle.add("verify", 3, verdict=verdict(tag, 3, continued="sha-1"))
        state = self.state(tag)
        autopilot.tick(state, kaggle, installer, now=NOW)
        entry = state["students"][tag]
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "waiting_ollama")
        self.assertEqual(entry["deliveries"], [3])
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW + 60), "launched")    # the next cycle still starts
        installer.reachable = True
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW + autopilot.RETRY_SECONDS + 1), "delivered")

    def test_a_model_that_loses_the_exam_as_served_is_installed_beside_the_current_one_only(self):
        tag = "qwen2.5:7b"
        kaggle, installer = FakeKaggle(tag), FakeInstaller(deployment="reject")
        kaggle.add("train", 3)
        kaggle.add("verify", 3, verdict=verdict(tag, 3, continued="sha-1"))
        state = self.state(tag)
        autopilot.tick(state, kaggle, installer, now=NOW)
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "delivered")
        self.assertEqual(installer.activated, [])
        self.assertFalse(state["students"][tag]["history"][-1]["activated"])

    def test_without_any_installable_cycle_it_diagnoses_the_base_then_trains_a_new_adapter(self):
        tag = "qwen2.5:7b"
        kaggle, installer = FakeKaggle(tag), FakeInstaller()
        state = self.state(tag)
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "discovered")
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "launched")
        self.assertEqual(kaggle.launched[-1][0], "diagnose")
        reference = state["students"][tag]["kernel"]
        kaggle.kernels[reference].update(status="complete", diagnosis={"trained_modules": []})
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "advanced")
        self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "launched")
        role, cycle, options = kaggle.launched[-1]
        self.assertEqual((role, cycle), ("train", 0))
        self.assertTrue(str(options["diagnosis"]).endswith("diagnosis.json"))
        self.assertNotIn("continue_adapter", options)

    def test_an_examiner_older_than_diagnosis_next_has_its_diagnosis_rebuilt_from_the_verdict(self):
        tag = "qwen2.5-coder:7b"
        kaggle, installer = FakeKaggle(tag), FakeInstaller()
        kaggle.add("train", 0)
        kaggle.add("verify", 0, verdict=verdict(tag, 0), diagnosis_next=False)
        installer.installed = {0: True}
        state = self.state(tag)
        autopilot.tick(state, kaggle, installer, now=NOW)
        with patch("auto_rl.professor.suites.exam_blocklist", return_value=["h1"]) as blocklist, \
                patch("auto_rl.professor.run.next_diagnosis", return_value={"trained_modules": []}) as rebuilt:
            self.assertEqual(autopilot.tick(state, kaggle, installer, now=NOW), "launched")
        self.assertEqual(rebuilt.call_args[0][1], ["h1"])
        self.assertEqual(sorted(blocklist.call_args.kwargs["modules"]), ["code", "missions"])
        self.assertEqual(kaggle.published[-1], ("training", ["diagnosis_next_0.json"]))

    def test_the_runner_stops_on_request_and_refuses_a_second_one(self):
        tag = "qwen2.5:7b"
        kaggle, installer = FakeKaggle(tag), FakeInstaller()
        self.assertEqual(autopilot.run(students=[tag], once=True, kaggle=kaggle, installer=installer), "discovered")
        state = autopilot.load()
        state["runner"] = {"pid": -1, "heartbeat": autopilot.time.time(), "busy": None}
        autopilot.save(state)
        with self.assertRaises(SystemExit):
            autopilot.run(students=[tag], once=True, kaggle=kaggle, installer=installer)
        state["runner"]["heartbeat"] = 0
        autopilot.save(state)
        autopilot.stop()                                 # a stop left from an earlier session does not block a new start
        result = autopilot.run(students=[tag], kaggle=kaggle, installer=installer,
                               sleep=lambda seconds: autopilot.STOP_FILE.write_text("stop"))
        self.assertEqual(result, "stopped")
        self.assertEqual(kaggle.launched[-1][0], "diagnose")     # it did work before the request arrived
        status = autopilot.status()
        self.assertFalse(status["enabled"])
        self.assertIn(tag, status["students"])

    def test_the_plan_never_trains_outside_the_tag_and_what_was_trained(self):
        plan = autopilot.plan("qwen2.5:7b")
        self.assertEqual(plan["modules"], ["business", "conversation", "media"])
        self.assertNotIn("cowork.extract_qa_fr", plan["skills"])
        self.assertEqual(autopilot.plan("qwen2.5:7b", {"trained_modules": ["cowork"]})["modules"],
                         ["business", "conversation", "cowork", "media"])


if __name__ == "__main__":
    unittest.main()
