"""Offline contract tests; never consume ElevenLabs credits."""
import base64
import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from elevenlabs_tts import settings, synthesize, word_times


def alignment(text):
    return {"characters": list(text),
            "character_start_times_seconds": [i / 10 for i in range(len(text))],
            "character_end_times_seconds": [(i + 1) / 10 for i in range(len(text))]}


class ElevenLabsTests(unittest.TestCase):
    def test_original_tokens_include_unicode_punctuation_and_numbers(self):
        text = "Ngày  xưa,\n1831!"
        result = word_times(text, alignment(text))
        self.assertEqual(result, [{"start": 0, "end": 0.4},
                                  {"start": 0.6, "end": 1.0},
                                  {"start": 1.1, "end": 1.6}])

    def test_rejects_mismatched_normalized_or_invalid_alignment(self):
        for value in (None, alignment("one"),
                      {**alignment("1"), "character_end_times_seconds": []},
                      {**alignment("1"), "character_start_times_seconds": [-1]},
                      {**alignment("1"), "character_end_times_seconds": [float("nan")]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                word_times("1", value)

    def test_api_request_and_response_contract(self):
        data = {"alignment": alignment("Hi!"),
                "audio_base64": base64.b64encode(b"fake mp3").decode()}
        options = settings({"model_id": "eleven_flash_v2_5", "language_code": "vi", "speed": 0.9})
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(data).encode())) as call:
            result = synthesize("secret-test", "voice/id", "Hi!", options)
        request = call.call_args.args[0]
        self.assertIn("voice%2Fid/with-timestamps", request.full_url)
        self.assertEqual(request.get_header("Xi-api-key"), "secret-test")
        self.assertEqual(json.loads(request.data), {"text": "Hi!", **options})
        self.assertEqual(result["words"], [{"start": 0, "end": 0.3}])
        self.assertEqual(result["engine"], "elevenlabs")

    def test_http_errors_do_not_leak_key_or_response_body_or_retry(self):
        error = urllib.error.HTTPError("https://api.elevenlabs.io", 401, "secret-test", {}, None)
        with patch("urllib.request.urlopen", side_effect=error) as call:
            with self.assertRaisesRegex(RuntimeError, "HTTP 401") as caught:
                synthesize("secret-test", "voice", "Hi", settings({}))
        self.assertNotIn("secret-test", str(caught.exception))
        self.assertEqual(call.call_count, 1)

    def test_missing_key_does_not_make_request(self):
        with patch("urllib.request.urlopen") as call, self.assertRaises(ValueError):
            synthesize("", "voice", "Hi", settings({}))
        call.assert_not_called()

    def test_invalid_audio_rejected(self):
        data = {"alignment": alignment("Hi"), "audio_base64": "invalid!"}
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(data).encode())):
            with self.assertRaisesRegex(ValueError, "base64 audio"):
                synthesize("test-key", "voice", "Hi", settings({}))

    def test_speed_limits(self):
        for speed in (0, 1.3, float("nan")):
            with self.subTest(speed=speed), self.assertRaises(ValueError):
                settings({"speed": speed})


if __name__ == "__main__":
    unittest.main()
