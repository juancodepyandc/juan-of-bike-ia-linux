import base64
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import studio_voix
import cinema.voice_clone as voice_clone


class StudioVoixTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.voix_dir = self.root / "output" / "voix"
        self.echantillons_dir = self.voix_dir / "echantillons"
        self.profils_dir = self.voix_dir / "profils"
        self.generations_dir = self.voix_dir / "generations"
        self.sessions_dir = self.voix_dir / "sessions"

        for d in (self.voix_dir, self.echantillons_dir, self.profils_dir, self.generations_dir, self.sessions_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.patches = [
            mock.patch.object(studio_voix, "VOIX_DIR", self.voix_dir),
            mock.patch.object(studio_voix, "ECHANTILLONS_DIR", self.echantillons_dir),
            mock.patch.object(studio_voix, "PROFILS_DIR", self.profils_dir),
            mock.patch.object(studio_voix, "GENERATIONS_DIR", self.generations_dir),
            mock.patch.object(studio_voix, "SESSIONS_DIR", self.sessions_dir),
            mock.patch.object(voice_clone, "LIBRARY_DIR", self.profils_dir),
            mock.patch.object(voice_clone, "DROPBOX_DIR", self.echantillons_dir),
            mock.patch.object(studio_voix.voice_clone, "LIBRARY_DIR", self.profils_dir),
            mock.patch.object(studio_voix.voice_clone, "DROPBOX_DIR", self.echantillons_dir),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp_dir.cleanup()

    def test_tree_summary_structure(self):
        summary = studio_voix.get_tree_summary()
        self.assertTrue(summary["ok"])
        self.assertEqual(summary["root"], str(self.voix_dir))
        self.assertIn("echantillons", summary["directories"])
        self.assertIn("profils", summary["directories"])
        self.assertIn("generations", summary["directories"])
        self.assertIn("sessions", summary["directories"])
        self.assertEqual(summary["counts"]["profils"], 0)

    def test_replicate_voice_permanent_workflow(self):
        import numpy as np
        import soundfile as sf

        sample_path = self.echantillons_dir / "test_voice.wav"
        sr = 16000
        t = np.arange(sr * 4, dtype=np.float32) / sr
        audio = 0.25 * np.sin(2 * np.pi * 240 * t) + 0.1 * np.sin(2 * np.pi * 480 * t)
        sf.write(str(sample_path), audio, sr)

        def mock_synth(text, reference_wav, output_wav, **kwargs):
            Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_wav), audio[:int(sr * 2.5)], sr)
            return {
                "ok": True,
                "wav": str(output_wav),
                "duration_s": 2.5,
                "engine": "cosyvoice3",
                "model": "FunAudioLLM/Fun-CosyVoice3-0.5B-2512",
            }

        with mock.patch.object(studio_voix.voice_clone, "synthesize", side_effect=mock_synth):
            res = studio_voix.replicate_voice(
                sample_path=sample_path,
                text="Bonjour, ceci est un test de réplication.",
                name="Professeur Tournesol",
                save_permanent=True,
                lang="fr",
            )

        self.assertTrue(res["ok"])
        self.assertEqual(res["name"], "Professeur Tournesol")
        self.assertEqual(res["slug"], "professeur_tournesol")
        self.assertTrue(res["is_permanent"])
        self.assertTrue(Path(res["wav"]).is_file())
        self.assertTrue(Path(res["meta"]).is_file())

        profile_ref = self.profils_dir / "professeur_tournesol" / "reference.wav"
        self.assertTrue(profile_ref.is_file())

        summary = studio_voix.get_tree_summary()
        self.assertEqual(summary["counts"]["profils"], 1)
        self.assertEqual(summary["profils"][0]["slug"], "professeur_tournesol")
        self.assertEqual(summary["counts"]["generations"], 1)

    def test_replicate_voice_ephemeral_session_workflow(self):
        import numpy as np
        import soundfile as sf

        sample_path = self.echantillons_dir / "ephemeral_sample.wav"
        sr = 16000
        t = np.arange(sr * 3, dtype=np.float32) / sr
        audio = 0.2 * np.sin(2 * np.pi * 300 * t)
        sf.write(str(sample_path), audio, sr)

        def mock_synth(text, reference_wav, output_wav, **kwargs):
            Path(output_wav).parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_wav), audio[:int(sr * 1.8)], sr)
            return {
                "ok": True,
                "wav": str(output_wav),
                "duration_s": 1.8,
                "engine": "cosyvoice3",
            }

        with mock.patch.object(studio_voix.voice_clone, "synthesize", side_effect=mock_synth):
            res = studio_voix.replicate_voice(
                sample_path=sample_path,
                text="Message temporaire non conservé.",
                name="Voix Éphémère",
                save_permanent=False,
                lang="fr",
            )

        self.assertTrue(res["ok"])
        self.assertFalse(res["is_permanent"])
        self.assertTrue(Path(res["wav"]).is_file())
        profile_ref = self.profils_dir / "voix_ephemere" / "reference.wav"
        self.assertFalse(profile_ref.exists())

        summary = studio_voix.get_tree_summary()
        self.assertEqual(summary["counts"]["profils"], 0)
        self.assertEqual(summary["counts"]["sessions"], 1)

    def test_bridge_routes_sample_upload_and_stream(self):
        import bridge_server
        import numpy as np
        import soundfile as sf

        sr = 16000
        t = np.arange(sr * 3.2, dtype=np.float32) / sr
        audio = 0.25 * np.sin(2 * np.pi * 320 * t)
        buf = io.BytesIO()
        sf.write(buf, audio, sr, format="WAV")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("ascii")

        client = bridge_server.app.test_client()

        # POST sample
        r = client.post("/api/voice/studio/sample", json={"wavBase64": b64})
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertTrue(data.get("ok"))
        sample_id = data.get("sampleId")
        self.assertTrue(bool(sample_id))

        # GET sample audio stream
        r_stream = client.get(f"/api/voice/studio/sample/{sample_id}/audio")
        self.assertEqual(r_stream.status_code, 200)
        self.assertEqual(r_stream.content_type, "audio/wav")
        self.assertGreater(len(r_stream.data), 1000)

        # GET tree & profiles
        r_tree = client.get("/api/voice/studio/tree")
        self.assertEqual(r_tree.status_code, 200)
        self.assertTrue(r_tree.get_json().get("ok"))

        r_prof = client.get("/api/voice/studio/profiles")
        self.assertEqual(r_prof.status_code, 200)
        self.assertTrue(r_prof.get_json().get("ok"))


if __name__ == "__main__":
    unittest.main()
