"""Exercise real FFmpeg decoding, output timing, cache reuse and local compatibility offline."""
import base64
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np
import voice_local


class VoicePipelineTests(unittest.TestCase):
    def test_outputs_cache_invalidation_and_local_compatibility(self):
        raw = io.BytesIO()
        samples = (np.sin(np.arange(48000) * 2 * np.pi * 220 / 48000) * 8000).astype("<i2")
        with wave.open(raw, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(48000)
            wav.writeframes(samples.tobytes())
        response = {"engine": "elevenlabs", "audio": base64.b64encode(raw.getvalue()).decode(),
                    "duration": 1, "words": [{"start": 0.1, "end": 0.4}, {"start": 0.5, "end": 0.9}]}
        cfg = {"provider": "elevenlabs", "voice": "test-voice", "lines": [
            {"text": "Xin chào", "pause": 0}, {"text": "Xin chào", "pause": 0.3}]}
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            out = Path(tmp)
            def run():
                (out / "narration.json").write_text(json.dumps(cfg))
                with patch("sys.argv", ["voice_local.py", str(out)]):
                    voice_local.main()
            with patch.object(voice_local, "CACHE", out / "cache"), \
                    patch("elevenlabs_tts.synthesize", return_value=response) as api, \
                    patch("dotenv.load_dotenv"):
                run()
                run()
                self.assertEqual(api.call_count, 1)
                cfg["model_id"] = "eleven_flash_v2_5"
                run()
                self.assertEqual(api.call_count, 2)
                cfg["voice_settings"] = {"stability": 0.7}
                run()
                self.assertEqual(api.call_count, 3)
                self.assertNotIn("api_key", next((out / "cache").glob("*.json")).read_text())
            words = json.loads((out / "words.json").read_text())
            lines = json.loads((out / "lines.json").read_text())
            self.assertEqual([w["w"] for w in words], ["Xin", "chào", "Xin", "chào"])
            self.assertEqual([w["line"] for w in words], [1, 1, 2, 2])
            self.assertAlmostEqual(lines[1]["s"] - lines[0]["e"], 0.3)
            self.assertTrue(all(w["s"] < w["e"] for w in words))
            with wave.open(str(out / "voice.wav")) as wav:
                self.assertEqual(wav.getframerate(), 48000)
                self.assertGreater(wav.getnframes(), 96000)
            self.assertTrue((out / "report.txt").exists())
            cfg = {"engine": "legacy", "port": 7871, "voice": "old-voice", "lines": [{"text": "Xin chào"}]}
            with patch.object(voice_local, "CACHE", out / "cache"), \
                    patch.object(voice_local, "tts", return_value={**response, "engine": "legacy"}) as local:
                run()
                local.assert_called_once_with(7871, "Xin chào", "old-voice", 1.0)


if __name__ == "__main__":
    unittest.main()
