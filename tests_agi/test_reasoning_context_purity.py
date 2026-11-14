import unittest
from unittest.mock import patch

from agi_core import cognitive_reasoner as reasoner
from agi_core.mission_agent import AutonomousMissionAgent


class ReasoningContextPurity(unittest.TestCase):
    def setUp(self):
        reasoner._REASONING_CACHE.clear()

    def test_prompt_assembly_cannot_issue_hidden_llm_request(self):
        agent = AutonomousMissionAgent("context-purity", "Inspect the supplied inputs", ".", "fixture")
        with patch.object(reasoner, "reason_first_principles", return_value={}) as reason:
            agent._domain_guidance()
        self.assertIs(reason.call_args.kwargs["allow_llm"], False)

    def test_long_requests_keep_distinct_suffixes(self):
        prefix = "x" * 512
        first = reasoner.reason_first_principles(prefix + " first", allow_llm=False)
        second = reasoner.reason_first_principles(prefix + " second", allow_llm=False)
        self.assertNotEqual(first["explicit_requirements"], second["explicit_requirements"])

    def test_context_identity_and_returned_mutations_cannot_poison_cache(self):
        first = reasoner.reason_first_principles("request", context={"input_revision": 1}, allow_llm=False)
        first["explicit_requirements"].clear()
        second = reasoner.reason_first_principles("request", context={"input_revision": 1}, allow_llm=False)
        reasoner.reason_first_principles("request", context={"input_revision": 2}, allow_llm=False)
        self.assertEqual(second["explicit_requirements"], ["request"])
        self.assertEqual(len(reasoner._REASONING_CACHE), 2)
