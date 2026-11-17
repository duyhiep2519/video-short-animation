"""ElevenLabs timestamp API adapter for the narration pipeline (standard library only)."""

import base64
import binascii
import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request


def word_times(text: str, alignment: dict) -> list[dict]:
    """Use original-text alignment: normalized text can expand numbers into extra words."""
    if not isinstance(alignment, dict):
        raise ValueError("ElevenLabs did not return original-text alignment")
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])
    if not chars or any(not isinstance(c, str) or len(c) != 1 for c in chars):
        raise ValueError("ElevenLabs returned invalid alignment characters")
    if "".join(chars) != text or len(chars) != len(starts) or len(chars) != len(ends):
        raise ValueError("ElevenLabs alignment does not match the original narration text")
    previous = 0.0
    for start, end in zip(starts, ends):
        if (not isinstance(start, (int, float)) or not isinstance(end, (int, float))
                or not math.isfinite(start) or not math.isfinite(end)
                or start < previous or end < start):
            raise ValueError("ElevenLabs returned invalid character timestamps")
        previous = start
    return [{"start": starts[m.start()], "end": max(ends[m.start():m.end()])}
            for m in re.finditer(r"\S+", text)]


def settings(cfg: dict) -> dict:
    speed = float(cfg.get("speed", 1.0))
    if not math.isfinite(speed) or not 0.7 <= speed <= 1.2:
        raise ValueError("ElevenLabs speed must be between 0.7 and 1.2")
    model = cfg.get("model_id", "eleven_multilingual_v2")
    if not isinstance(model, str) or not model.strip():
        raise ValueError("model_id must be a non-empty string")
    voice_settings = cfg.get("voice_settings", {})
    if not isinstance(voice_settings, dict):
        raise ValueError("voice_settings must be an object")
    result = {"model_id": model, "voice_settings": {**voice_settings, "speed": speed}}
    if cfg.get("language_code"):
        result["language_code"] = cfg["language_code"]
    return result


def synthesize(api_key: str, voice: str, text: str, options: dict) -> dict:
    if not api_key:
        raise ValueError("Set ELEVENLABS_API_KEY in cartoon-shorts/.env or the environment")
    url = ("https://api.elevenlabs.io/v1/text-to-speech/"
           + urllib.parse.quote(voice, safe="")
           + "/with-timestamps?output_format=mp3_44100_128")
    req = urllib.request.Request(url, data=json.dumps({"text": text, **options}).encode(),
                                 headers={"Content-Type": "application/json", "xi-api-key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=600) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        hints = {401: "check API key", 403: "check key permissions and voice access",
                 402: "check credits/subscription", 429: "check credits or rate limits",
                 422: "check model, language and voice settings"}
        raise RuntimeError(f"ElevenLabs HTTP {exc.code}: "
                           + hints.get(exc.code, "check service status and request settings")) from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("Cannot reach ElevenLabs; check network and retry manually") from None
    words = word_times(text, data.get("alignment"))
    try:
        audio = data["audio_base64"]
        if not base64.b64decode(audio, validate=True):
            raise ValueError("empty audio")
    except (KeyError, TypeError, ValueError, binascii.Error):
        raise ValueError("ElevenLabs returned invalid base64 audio") from None
    return {"audio": audio, "duration": max(w["end"] for w in words),
            "engine": "elevenlabs", "words": words}
