#!/usr/bin/env python3
"""Narration from a local text-to-speech server or ElevenLabs (provider: "elevenlabs").

Reads <voice dir>/narration.json:
  {"engine": "<model name>", "port": 7871, "voice": "<voice id>", "speed": 1.0, "lead": 0.12, "tail": 0.6, "lufs": -16.6,
   "lines": [{"pause": 0.0, "text": "..."}, ...]}            (pause = silence before the line, seconds)
Writes voice.wav (48 kHz mono), words.json ({w, s, e, line}), lines.json ({i, text, s, e}), report.txt next to it.
Each line is cached in out/cache/voice-local/ by synthesis settings and text.
ElevenLabs: set provider="elevenlabs", voice (or ELEVENLABS_VOICE_ID), model_id,
optional language_code / voice_settings, and ELEVENLABS_API_KEY in .env or environment.

For the default local provider, the server is not part of this repo. It must answer
POST http://127.0.0.1:<port>/api/tts with JSON
  request:  {"text": "...", "voice": "...", "speed": 1.0}
  response: {"audio": "<base64 audio file>", "duration": <seconds>, "engine": "<model name>",
             "words": [{"start": <s>, "end": <s>}, ...]}      (one entry per whitespace-separated token of the text)

usage: python3 scripts/voice/voice_local.py shorts/<ep>/voice [--ep <ep>]     (--ep reports progress via scripts/xuong.py)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "audio"))
from dsp import integrated, st, write_wav  # noqa: E402

SR = 48000
CACHE = ROOT / "out" / "cache" / "voice-local"


def xuong(ep: str | None, *args: str) -> None:
    if ep:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "xuong.py"), *args], check=False, stderr=subprocess.DEVNULL)


def tts(port: int, text: str, voice: str, speed: float) -> dict:
    body = json.dumps({"text": text, "voice": voice, "speed": speed}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/tts", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def decode(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, "<f4").astype(np.float64)


def speech_bounds(x: np.ndarray) -> tuple[int, int]:
    if not len(x) or not np.isfinite(x).all() or not np.any(x):
        raise ValueError("TTS returned empty, silent or invalid audio")
    w = int(0.01 * SR)
    rms = np.sqrt(np.convolve(x * x, np.ones(w) / w, "same"))
    on = np.nonzero(rms > rms.max() * 10 ** (-42 / 20))[0]
    return max(0, on[0] - int(0.02 * SR)), min(len(x), on[-1] + int(0.06 * SR))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--ep", default=None)
    a = ap.parse_args()
    out = Path(a.dir)
    cfg = json.loads((out / "narration.json").read_text())
    provider = cfg.get("provider", "local")
    if provider not in ("local", "elevenlabs"):
        raise ValueError("provider must be local or elevenlabs")
    speed = float(cfg.get("speed", 1.0))
    if provider == "elevenlabs":
        from dotenv import load_dotenv
        from elevenlabs_tts import settings, synthesize
        load_dotenv(ROOT / ".env")
        engine, port = "elevenlabs", None
        voice = cfg.get("voice") or os.environ.get("ELEVENLABS_VOICE_ID", "")
        if not isinstance(voice, str) or not voice.strip():
            raise ValueError("Set voice in narration.json or ELEVENLABS_VOICE_ID in .env")
        options = settings(cfg)
    else:
        engine, port, voice = cfg["engine"], int(cfg["port"]), cfg["voice"]
    if not cfg.get("lines") or any(not line.get("text", "").strip() for line in cfg["lines"]):
        raise ValueError("narration.json must contain non-empty lines of text")
    lead, tail, lufs = float(cfg.get("lead", 0.12)), float(cfg.get("tail", 0.6)), float(cfg.get("lufs", -16.6))
    CACHE.mkdir(parents=True, exist_ok=True)
    pieces, words, lines, report, warn = [], [], [], [], []
    t = lead
    n = len(cfg["lines"])
    xuong(a.ep, "log", a.ep or "", "giong", f"Đọc {n} câu bằng {engine} · {voice} (tốc độ {speed})")
    for li, line in enumerate(cfg["lines"], 1):
        text = line["text"].strip()
        key = hashlib.sha1(f"{engine}|{voice}|{speed}|{text}".encode()).hexdigest()[:16]
        if provider == "elevenlabs":
            key = hashlib.sha256(json.dumps({"provider": provider, "voice": voice,
                "text": text, **options}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
        wav, meta = CACHE / f"{key}.wav", CACHE / f"{key}.json"
        if not (wav.exists() and meta.exists()):
            r = (synthesize(os.environ.get("ELEVENLABS_API_KEY", ""), voice, text, options)
                 if provider == "elevenlabs" else tts(port, text, voice, speed))
            if r.get("engine") and r["engine"] != engine:
                raise SystemExit(f"server on port {port} runs {r['engine']}, narration.json asks for {engine}")
            wav.write_bytes(base64.b64decode(r["audio"]))
            meta.write_text(json.dumps({"text": text, "words": r["words"], "duration": r["duration"]}, ensure_ascii=False))
        m = json.loads(meta.read_text())
        toks = text.split()
        if len(m["words"]) != len(toks):
            raise SystemExit(f"line {li}: {len(toks)} tokens but the aligner returned {len(m['words'])} words")
        x = decode(wav)
        a0, b0 = speech_bounds(x)
        y = x[a0:b0]
        t += float(line.get("pause", 0)) if li > 1 else 0
        s0 = t
        off = a0 / SR
        e_line = s0 + len(y) / SR
        for i, (tok, w) in enumerate(zip(toks, m["words"])):
            s = s0 + max(0.0, w["start"] - off)
            e = s0 + min(len(y) / SR, w["end"] - off)
            if e - s < 0.05:
                warn.append(f"L{li:02d} '{tok}' only {1000 * (e - s):.0f} ms")
            words.append({"w": tok, "s": round(s, 3), "e": round(max(e, s + 0.05), 3), "line": li})
        pieces.append((s0, y))
        lines.append({"i": li, "text": text, "s": round(s0, 3), "e": round(e_line, 3)})
        report.append(f"L{li:02d} {s0:6.2f}-{e_line:6.2f} ({e_line - s0:4.2f} s, {len(toks)} syl, {len(toks) / (e_line - s0):.2f} syl/s) {text}")
        t = e_line
        xuong(a.ep, "progress", a.ep or "", "giong", f"{li}/{n}", f"Câu {li}/{n}: {text[:48]}")
    total = t + tail
    track = np.zeros(int(round(total * SR)))
    for s0, y in pieces:
        i0 = int(round(s0 * SR))
        k = min(len(y), len(track) - i0)
        f = min(int(0.004 * SR), k // 4)
        y = y[:k].copy()
        y[:f] *= np.linspace(0, 1, f)
        y[k - f:] *= np.linspace(1, 0, f)
        track[i0:i0 + k] += y
    track *= 10 ** ((lufs - integrated(st(track))) / 20)
    write_wav(str(out / "voice.wav"), track)
    (out / "words.json").write_text(json.dumps(words, ensure_ascii=False, indent=1))
    (out / "lines.json").write_text(json.dumps(lines, ensure_ascii=False, indent=1))
    report.append(f"total {total:.3f} s, {len(words)} words, {engine} · {voice} · speed {speed}")
    report += [f"warn: {w}" for w in warn]
    (out / "report.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))
    xuong(a.ep, "metric", a.ep or "", "giong", f"thời lượng={total:.1f}s", f"số chữ={len(words)}", f"giọng={voice}")


if __name__ == "__main__":
    main()
