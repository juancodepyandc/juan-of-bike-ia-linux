import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice_clone
import cosyvoice3_adapter


class VoiceCloneContractsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.cache = self.root / "cache"
        self.library = self.root / "library"
        self.cache.mkdir()
        self.library.mkdir()
        self.cache_patch = mock.patch.object(voice_clone, "CACHE_DIR", self.cache)
        self.library_patch = mock.patch.object(voice_clone, "LIBRARY_DIR", self.library)
        self.cache_patch.start()
        self.library_patch.start()

    def tearDown(self):
        self.library_patch.stop()
        self.cache_patch.stop()
        self.temp_dir.cleanup()

    def test_isolated_runtime_compares_venv_roots_not_python_symlink_targets(self):
        current = Path(voice_clone.sys.prefix) / "bin" / "python"
        separate = Path(voice_clone.sys.prefix).parent / "cosyvoice3" / "bin" / "python"
        self.assertFalse(voice_clone._is_isolated_python(current))
        self.assertTrue(voice_clone._is_isolated_python(separate))

    def test_cosyvoice3_absent_is_reported_without_install(self):
        missing_python = self.root / "missing-cosyvoice-python"
        with mock.patch.dict(
            voice_clone.os.environ,
            {"AURORA_COSYVOICE3_PYTHON": str(missing_python)},
            clear=False,
        ):
            status = voice_clone.cosyvoice3_status()
        self.assertFalse(status["ok"])
        self.assertIn("venv CosyVoice3 isole absent", status["error"])

    def test_quality_chain_prefers_cosyvoice3(self):
        reference = self.root / "reference.wav"
        reference.write_bytes(b"reference")
        output = self.root / "output.wav"

        def cosy(*_args, **_kwargs):
            output.write_bytes(b"audio")
            return {
                "ok": True,
                "wav": str(output),
                "duration_s": 1.25,
                "engine": "cosyvoice3",
                "model": "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
            }

        with (
            mock.patch.object(voice_clone, "synthesize_cosyvoice3", side_effect=cosy) as cosy_mock,
            mock.patch.object(voice_clone, "synthesize_xtts") as xtts_mock,
            mock.patch.object(voice_clone, "synthesize_f5") as f5_mock,
        ):
            result = voice_clone.synthesize(
                "Bonjour Aurora",
                str(reference),
                str(output),
                lang="fr",
                prompt_text="Bonjour, ceci est ma voix.",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["engine"], "cosyvoice3")
        cosy_mock.assert_called_once()
        xtts_mock.assert_not_called()
        f5_mock.assert_not_called()

    def test_fallback_is_explicit_when_cosyvoice3_is_unavailable(self):
        reference = self.root / "reference.wav"
        reference.write_bytes(b"reference")
        output = self.root / "output.wav"

        def xtts(*_args, **_kwargs):
            output.write_bytes(b"audio")
            return {"ok": True, "wav": str(output), "duration_s": 1.0, "engine": "xtts-v2"}

        with (
            mock.patch.object(
                voice_clone,
                "synthesize_cosyvoice3",
                return_value={"ok": False, "engine": "cosyvoice3", "error": "runtime absent"},
            ),
            mock.patch.object(voice_clone, "synthesize_xtts", side_effect=xtts),
            mock.patch.object(voice_clone, "synthesize_f5") as f5_mock,
        ):
            result = voice_clone.synthesize(
                "Bonjour Aurora",
                str(reference),
                str(output),
                lang="fr",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["engine"], "xtts-v2")
        self.assertEqual([a["engine"] for a in result["fallback_chain"]], ["cosyvoice3", "xtts-v2"])
        self.assertEqual(result["warnings"][0]["code"], "voice_engine_fallback")
        f5_mock.assert_not_called()

    def test_registration_keeps_exact_reference_transcript(self):
        source = self.root / "source.wav"
        import numpy as np
        import soundfile as sf

        sample_rate = 22050
        timeline = np.arange(sample_rate * 6, dtype=np.float32) / sample_rate
        mono = 0.2 * np.sin(2 * np.pi * 220 * timeline)
        stereo = np.stack([mono, mono * 0.95], axis=1)
        sf.write(source, stereo, sample_rate)
        blocked_module = {"speechbrain.inference.speaker": None}
        with mock.patch.dict(sys.modules, blocked_module):
            result = voice_clone.register_voice(
                "Personnage test",
                str(source),
                lang="fr",
                transcript="Ceci est la transcription exacte.",
            )

        self.assertTrue(result["ok"])
        metadata = json.loads(
            (self.library / "personnage_test" / "metadata.json").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["transcript"], "Ceci est la transcription exacte.")
        self.assertEqual(metadata["reference_audio"]["sample_rate"], 16000)
        self.assertEqual(metadata["reference_audio"]["channels"], 1)
        self.assertTrue(metadata["reference_audio"]["ok"])
        self.assertGreater(metadata["reference_quality_score"], 0)

    def test_silent_reference_is_rejected_before_library_overwrite(self):
        import numpy as np
        import soundfile as sf

        source = self.root / "silent.wav"
        sf.write(source, np.zeros(16000 * 6, dtype=np.float32), 16000)
        result = voice_clone.register_voice("Silence", str(source), lang="fr")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "reference_audio_rejected")
        self.assertIn("reference_nearly_silent", result["audio_quality"]["failures"])
        self.assertFalse((self.library / "silence" / "reference.wav").exists())

    def test_official_cosyvoice3_yaml_is_a_valid_model_marker(self):
        repo = self.root / "CosyVoice"
        model = self.root / "Fun-CosyVoice3"
        (repo / "cosyvoice").mkdir(parents=True)
        model.mkdir()
        (model / "cosyvoice3.yaml").write_text("sample_rate: 24000", encoding="utf-8")
        with mock.patch.dict(
            cosyvoice3_adapter.os.environ,
            {
                "AURORA_COSYVOICE3_REPO": str(repo),
                "AURORA_COSYVOICE3_MODEL": str(model),
            },
            clear=False,
        ):
            status = cosyvoice3_adapter.check_runtime(import_modules=False)
        self.assertTrue(status["model_ready"])
        self.assertTrue(status["repo_ready"])
        self.assertTrue(status["ok"])

    def test_offline_cold_directory_is_never_treated_as_model_storage(self):
        fake_home = self.root / "home"
        fake_cold = self.root / "cold"
        cold_model = fake_cold / "models" / "Fun-CosyVoice3-0.5B-2512"
        cold_model.mkdir(parents=True)
        (cold_model / "cosyvoice3.yaml").write_text("sample_rate: 24000", encoding="utf-8")
        expected_internal = (
            fake_home / ".local/share/auroraia/models/Fun-CosyVoice3-0.5B-2512"
        )
        with (
            mock.patch.object(cosyvoice3_adapter.Path, "home", return_value=fake_home),
            mock.patch.object(cosyvoice3_adapter.os.path, "ismount", return_value=False),
            mock.patch.dict(
                cosyvoice3_adapter.os.environ,
                {"AURORA_COLD_STORAGE": str(fake_cold)},
                clear=False,
            ),
            mock.patch.dict(
                cosyvoice3_adapter.os.environ,
                {
                    "AURORA_COSYVOICE3_MODEL": "",
                    "AURORA_COSYVOICE3_REPO": "",
                },
                clear=False,
            ),
        ):
            resolved = cosyvoice3_adapter.resolve_model()
        self.assertEqual(resolved, expected_internal)


if __name__ == "__main__":
    unittest.main()
