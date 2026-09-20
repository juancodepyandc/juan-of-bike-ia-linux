"""Check VRAM reporting without importing or starting the model stack."""

import ast
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class HardwareReportingTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / "application/python-services/aurora_hunyuan/pipeline_hunyuan_robust.py"
        tree = ast.parse(source.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "check_hardware")
        self.cuda = Mock()
        self.cuda.is_available.return_value = True
        self.logger = logging.getLogger("hardware_fixture")
        context = {
            "torch": SimpleNamespace(cuda=self.cuda), "log": self.logger,
            "psutil": SimpleNamespace(virtual_memory=lambda: SimpleNamespace(available=16e9, total=32e9)),
        }
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), context)
        self.check = context["check_hardware"]

    def test_busy_large_card_is_not_reported_as_small(self):
        self.cuda.mem_get_info.return_value = (1e9, 16e9)
        with self.assertLogs(self.logger, level="INFO") as captured:
            self.check()
        output = "\n".join(captured.output)
        self.assertIn("VRAM: 1.00 GB free / 16.00 GB total", output)
        self.assertNotIn("GPU has < 15GB", output)

    def test_small_card_warns_based_on_total_capacity(self):
        self.cuda.mem_get_info.return_value = (7e9, 8e9)
        with self.assertLogs(self.logger, level="INFO") as captured:
            self.check()
        self.assertIn("GPU has < 15GB", "\n".join(captured.output))

    def test_cpu_only_machine_does_not_read_cuda_memory(self):
        self.cuda.is_available.return_value = False
        self.check("cpu")
        self.cuda.mem_get_info.assert_not_called()


if __name__ == "__main__":
    unittest.main()
