"""Render a Remotion composition on Modal: frame ranges fan out to containers, each returns an H.264 chunk.

Normally driven by scripts/render/render-cloud.sh (bundle locally -> `render` entrypoint -> concat + audio mux).
Direct use (from the project folder; env CLOUD_GPU picks the GPU type(s) when the app is launched):

  modal run cloud/remotion_modal.py::render --bundle out/cloud/render-X/bundle --comp BridgeShort --frames 2025 \
      --out out/cloud/render-X/chunks [--scale 1.3333] [--workers 0=auto] [--mode gpu|cpu] [--episode bridge]
  modal run cloud/remotion_modal.py::stills --bundle <dir> --comp BridgeShort --frames-list 100,600,1200 --out out/cloud/x_
  modal run cloud/remotion_modal.py::bench --bundle <dir> --comp BridgeShort --configs T4:4:3,A10G:8:4,cpu:16:8
  modal run cloud/remotion_modal.py::probe          (GPU / WebGL diagnostics: nvidia-smi, Vulkan/EGL, `remotion gpu`)

What works (measured 2026-11-08, Remotion 4.0.290, Chrome Headless Shell 133): on Modal GPU containers the NVIDIA
driver's graphics libraries are mounted, and Chrome's ANGLE-on-Vulkan (`gl: "vulkan"`) or ANGLE-on-EGL (`angle-egl`)
runs WebGL on the GPU; `egl` falls back to SwiftShader. CPU-only containers use SwiftShader (`swangle`).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path

import modal

APP_NAME = "remotion-cloud-render"
VOLUME_NAME = "remotion-render"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# Modal list prices, USD per hour (`modal billing rates`, 2026-11-08). CPU is billed per physical core, memory per GiB.
PRICE = {"T4": 0.59, "L4": 0.80, "A10G": 1.10, "L40S": 1.95, "A100": 2.10, "H100": 3.95, "core": 0.0473, "GiB": 0.008}

# GPU type(s) for the GPU functions, read when the app is launched: a comma list is a fallback order (first available).
GPU_TYPES = [g.strip().upper() for g in os.environ.get("CLOUD_GPU", "A10G,T4").split(",") if g.strip()]
GPU_CPU = float(os.environ.get("CLOUD_GPU_CPU", "4"))      # physical cores next to the GPU (Chrome JS, JPEG, x264)
GPU_MEM = int(os.environ.get("CLOUD_GPU_MEM", "8192"))     # MiB
CPU_CORES = float(os.environ.get("CLOUD_CPU", "32"))       # CPU-only (SwiftShader) containers
CPU_MEM = int(os.environ.get("CLOUD_CPU_MEM", "32768"))

# Chrome flags per mode, and the steady throughput of ONE container (frames/s) used to size the fan-out (`--workers 0`).
# Measured with the `bench` entrypoint on BridgeShort frames 600-719 at 1440x2560 (2026-11-09):
#   A10G + 4 cores, 3 tabs: 3.7-4.0 (8 cores/4 tabs: 3.9-4.3)   T4 + 4 cores, 2-3 tabs: 1.0-2.8 (varies by host)
#   L4 + 4-8 cores: 1.9-2.1 (and 6-9 min waits for capacity)     CPU-only SwiftShader, 32 cores/16 tabs: ~0.1
# The table uses slightly conservative values (heavier shorts such as MaDa render slower than BridgeShort).
# OVERHEAD_S: container start (~4 s with the image cached) + Chrome + bundle/GLB load + shader compile until the first
# frame (10-25 s) + encoder tail, rounded up.
MODES = {
    "gpu": {"gl": "vulkan", "chromeMode": "headless-shell", "concurrency": 3, "fps": {"A10G": 3.5, "T4": 1.6, "L4": 1.9}},
    "cpu": {"gl": "swangle", "chromeMode": "headless-shell", "concurrency": 16, "fps": {"cpu": 0.09}},
}
OVERHEAD_S = 45

# Chrome Headless Shell / Chrome for Testing runtime libraries (Remotion's Linux list) + GL/EGL/Vulkan loaders.
# Modal's GPU runtime mounts the NVIDIA user-space driver incl. graphics libs (libEGL_nvidia, libGLX_nvidia) and the
# Vulkan/EGL manifests (/etc/vulkan/icd.d/nvidia_icd.json, glvnd 10_nvidia.json): nothing to add for the driver.
APT = [
    "libnss3", "libdbus-1-3", "libatk1.0-0", "libgbm1", "libasound2", "libxrandr2", "libxkbcommon0", "libxfixes3",
    "libxcomposite1", "libxdamage1", "libatk-bridge2.0-0", "libpango-1.0-0", "libcairo2", "libcups2",
    "libgtk-3-0", "libxshmfence1", "libx11-xcb1", "libdrm2", "libxss1", "fonts-liberation", "ca-certificates",
    "libegl1", "libgl1", "libgles2", "libglvnd0", "libvulkan1", "vulkan-tools", "procps",
]

image = (
    modal.Image.from_registry("node:22-bookworm-slim", add_python="3.12")
    .apt_install(*APT)
    .env({"NVIDIA_DRIVER_CAPABILITIES": "all", "NVIDIA_VISIBLE_DEVICES": "all"})
    .add_local_file(ROOT / "package.json", "/app/package.json", copy=True)
    .add_local_file(ROOT / "pnpm-lock.yaml", "/app/pnpm-lock.yaml", copy=True)
    .add_local_file(ROOT / "pnpm-workspace.yaml", "/app/pnpm-workspace.yaml", copy=True)
    # Linux binaries (compositor, ffmpeg) come from the lockfile's optional linux-x64 packages; no dev deps needed
    .run_commands("corepack enable", "cd /app && pnpm install --prod --frozen-lockfile --ignore-scripts")
    .run_commands(
        "cd /app && node -e \"require('@remotion/renderer').ensureBrowser({chromeMode:'headless-shell'}).then(console.log)\"",
        "cd /app && node -e \"require('@remotion/renderer').ensureBrowser({chromeMode:'chrome-for-testing'}).then(console.log)\"",
    )
    .add_local_file(HERE / "worker.mjs", "/app/worker.mjs")
)

app = modal.App(APP_NAME, image=image)
vol = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

# ------------------------------------------------------------------------------------------- container side

_BOOT = time.time()  # module import time in the container (~ container start)
_CALLS = 0


def _gpu_name() -> str:
    try:
        return subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True,
                              timeout=20).stdout.strip() or "none"
    except Exception:
        return "none"


def _run_worker(job: dict, progress=None, key=None) -> tuple[list[dict], float]:
    """Run worker.mjs with one job; forward progress to a modal.Dict (at most ~1/s). Returns (events, seconds)."""
    t0 = time.time()
    p = subprocess.Popen(["node", "/app/worker.mjs", json.dumps(job)], cwd="/app", stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, bufsize=1)
    events, other, last_put = [], [], 0.0
    for line in p.stdout:
        line = line.rstrip()
        try:
            ev = json.loads(line)
        except ValueError:
            other.append(line)
            print(line, flush=True)
            continue
        ev["wall"] = round(time.time() - t0, 2)
        events.append(ev)
        if ev.get("ev") != "progress":
            print(json.dumps(ev), flush=True)
        if progress is not None and ev.get("ev") == "progress" and time.time() - last_put > 1.0:
            last_put = time.time()
            try:
                progress[key] = int(ev.get("rendered", 0))
            except Exception:  # progress is best-effort
                pass
    rc = p.wait()
    if rc != 0:
        raise RuntimeError(f"worker exited {rc}: " + "\n".join(other[-40:]))
    return events, time.time() - t0


def _ensure_bundle(path: str) -> None:
    if not os.path.exists(os.path.join(path, "index.html")):
        vol.reload()  # a warm container may predate the upload
    if not os.path.exists(os.path.join(path, "index.html")):
        raise FileNotFoundError(f"bundle not on volume: {path}")


def _render(job: dict, progress=None) -> dict:
    global _CALLS
    _CALLS += 1
    start = time.time()
    _ensure_bundle(job["serveUrl"])
    job = dict(job, output=f"/tmp/chunk_{job['index']:03d}.mp4")
    events, secs = _run_worker(job, progress, job["index"])
    data = Path(job["output"]).read_bytes()
    os.remove(job["output"])
    if progress is not None:
        progress[job["index"]] = job["frameRange"][1] - job["frameRange"][0] + 1
    return {"index": job["index"], "bytes": data, "seconds": round(secs, 2), "events": [e for e in events if e["ev"] != "progress"],
            "bootAt": _BOOT, "startAt": start, "endAt": time.time(), "cold": _CALLS == 1, "gpu": _gpu_name(),
            "nproc": os.cpu_count()}


def _stills(job: dict) -> dict:
    _ensure_bundle(job["serveUrl"])
    os.makedirs("/tmp/stills", exist_ok=True)
    job = dict(job, output="/tmp/stills/s_")
    events, secs = _run_worker(job)
    files = {f: Path("/tmp/stills", f).read_bytes() for f in sorted(os.listdir("/tmp/stills"))}
    for f in files:
        os.remove(Path("/tmp/stills", f))
    return {"files": files, "events": events, "seconds": round(secs, 2), "gpu": _gpu_name()}


_COMMON = dict(volumes={"/vol": vol}, timeout=3600, scaledown_window=2, retries=modal.Retries(max_retries=1, initial_delay=1.0))


@app.function(gpu=GPU_TYPES, cpu=GPU_CPU, memory=GPU_MEM, **_COMMON)
def render_gpu(job: dict, progress=None) -> dict:
    return _render(job, progress)


@app.function(cpu=CPU_CORES, memory=CPU_MEM, **_COMMON)
def render_cpu(job: dict, progress=None) -> dict:
    return _render(job, progress)


@app.function(gpu=GPU_TYPES, cpu=GPU_CPU, memory=GPU_MEM, **_COMMON)
def stills_gpu(job: dict) -> dict:
    return _stills(job)


@app.function(cpu=CPU_CORES, memory=CPU_MEM, **_COMMON)
def stills_cpu(job: dict) -> dict:
    return _stills(job)


@app.function(gpu=GPU_TYPES, cpu=GPU_CPU, memory=GPU_MEM, volumes={"/vol": vol}, timeout=1200, scaledown_window=2)
def diagnose(gls: list[str], cmd: str = "") -> str:
    """GPU/WebGL diagnostics: what the container sees and what Chrome reports for each gl/chromeMode."""
    sh = lambda c: subprocess.run(c, shell=True, capture_output=True, text=True, timeout=600)  # noqa: E731
    if cmd:
        r = sh(cmd)
        return r.stdout + r.stderr
    out = []
    for c in ["nvidia-smi -L; nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv",
              "env | grep -i -E 'nvidia|cuda' | sort", "nproc; free -g | head -2",
              "ls /usr/lib/x86_64-linux-gnu | grep -i -E 'nvidia|libcuda|libEGL|libGLX|libvulkan' | sort",
              "ls -la /usr/share/vulkan/icd.d /usr/share/glvnd/egl_vendor.d /etc/vulkan/icd.d 2>&1",
              "vulkaninfo --summary 2>/dev/null | grep -E 'deviceName|driverName'"]:
        r = sh(c)
        out.append(f"$ {c}\n{r.stdout}{r.stderr}")
    for g in gls:
        gl, mode = g.split("@") if "@" in g else (g, "chrome-for-testing")
        r = sh(f"cd /app && timeout 120 pnpm exec remotion gpu --gl={gl} --chrome-mode={mode} 2>&1 | head -60")
        out.append(f"$ remotion gpu --gl={gl} --chrome-mode={mode}\n{r.stdout}{r.stderr}")
    return "\n".join(out)


# ----------------------------------------------------------------------------------------------- local side


def _fn(kind: str, mode: str, gpu: str = "", cpu: float = 0, memory: int = 0, max_containers: int | None = None):
    """render_gpu/render_cpu (or stills_*) with optional overrides; gpu="" keeps the CLOUD_GPU list."""
    f = {"render": {"gpu": render_gpu, "cpu": render_cpu}, "stills": {"gpu": stills_gpu, "cpu": stills_cpu}}[kind][mode]
    opts = {}
    if mode == "gpu" and gpu:
        opts["gpu"] = gpu
    if cpu:
        opts["cpu"] = cpu
    if memory:
        opts["memory"] = memory
    if max_containers:
        opts["max_containers"] = max_containers
    return f.with_options(**opts) if opts else f


def _upload_bundle(bundle: str) -> str:
    """Upload the local bundle dir to the volume once per content hash; returns the container path."""
    root = Path(bundle).resolve()
    h = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file())  # incl. source maps: Remotion reads bundle.js.map
    for p in files:
        h.update(str(p.relative_to(root)).encode())
        h.update(p.read_bytes())
    key = h.hexdigest()[:16]
    remote = f"/bundles/{key}"
    try:
        have = any(e.path.endswith("index.html") for e in vol.listdir(remote))
    except Exception:
        have = False
    if not have:
        t0 = time.time()
        with vol.batch_upload(force=True) as batch:
            for p in files:
                batch.put_file(str(p), f"{remote}/{p.relative_to(root)}")
        size = sum(p.stat().st_size for p in files) / 1e6
        print(f"[cloud] bundle uploaded ({size:.1f} MB, {time.time() - t0:.1f}s) -> {VOLUME_NAME}:{remote}", flush=True)
    else:
        print(f"[cloud] bundle already on volume: {remote}", flush=True)
    return "/vol" + remote


def _xuong(args: list[str]) -> None:
    try:
        subprocess.run(["python3", str(ROOT / "scripts" / "xuong.py"), *args], timeout=20, capture_output=True)
    except Exception as e:  # progress must never break the render
        print(f"[cloud] xuong.py failed: {e}", flush=True)


def split(total: int, chunks: int) -> list[tuple[int, int]]:
    """[0, total) into `chunks` contiguous inclusive ranges whose sizes differ by at most one frame."""
    chunks = max(1, min(chunks, total))
    base, extra = divmod(total, chunks)
    out, a = [], 0
    for i in range(chunks):
        n = base + (1 if i < extra else 0)
        out.append((a, a + n - 1))
        a += n
    return out


def _price_key(gpu_name: str) -> str | None:
    n = gpu_name.upper()
    for k in ("A10G", "L40S", "A100", "H100", "T4", "L4"):
        if k in n:
            return k
    return "A10G" if "A10" in n else None


def container_cost(seconds: float, gpu_name: str, cores: float, mem_mib: int) -> float:
    """USD for one container alive `seconds` (requested cores/memory; Modal bills max(request, use)). Checked against
    `modal billing report`: real cost ~ worker time + ~14 s per container (start before Python, scaledown)."""
    g = PRICE.get(_price_key(gpu_name) or "", 0.0)
    return seconds / 3600 * (g + cores * PRICE["core"] + mem_mib / 1024 * PRICE["GiB"])


def auto_workers(frames: int, mode: str, target_min: float) -> int:
    """Fewest containers that finish `frames` in ~target_min minutes (each container pays its own cold start)."""
    fps = MODES[mode]["fps"].get(GPU_TYPES[0] if mode == "gpu" else "cpu", 1.0)
    per = fps * max(60.0, target_min * 60 - OVERHEAD_S)
    return max(1, min(100, math.ceil(frames / per)))


def _local_progress(log: str) -> int:
    try:
        m = re.findall(r"rendered (\d+)/(\d+)", Path(log).read_text(errors="ignore"))
        return int(m[-1][0]) if m else 0
    except OSError:
        return 0


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@app.local_entrypoint()
def render(bundle: str, comp: str, frames: int, out: str, scale: float = 1.3333, workers: int = 0, chunks: int = 0,
           mode: str = "gpu", gpu: str = "", cpu: float = 0, memory: int = 0, gl: str = "", chrome_mode: str = "",
           concurrency: int = 0, crf: int = 16, episode: str = "", stats: str = "", start: int = 0, target_min: float = 10,
           local_frames: int = 0, local_log: str = "", local_pid: int = 0, keep_bundle: bool = False):
    """Render frames [start, start + frames) of `comp` on Modal as chunks into `out`/chunk_NNN.mp4 + list.txt.
    --workers 0 = auto (fewest containers that finish in ~--target-min minutes). --local-* describe a range rendered on
    this machine at the same time (scripts/render/render-cloud.sh LOCAL_SHARE): it is reported as the last progress lane."""
    m = MODES[mode]
    workers = workers or auto_workers(frames, mode, target_min)
    # ~3 chunks per container (>= 60 frames each): shots differ a lot in cost (BridgeShort: 4 to 11 frames/s on one
    # A10G), so a container that finishes early takes the next queued chunk (warm, ~10 s Chrome start-up) instead of
    # idling while one heavy half finishes
    chunks = chunks or max(workers, min(3 * workers, frames // 60))
    ranges = [(a + start, b + start) for a, b in split(frames, chunks)]
    serve = _upload_bundle(bundle)
    outdir = Path(out)
    outdir.mkdir(parents=True, exist_ok=True)
    fn = _fn("render", mode, gpu, cpu, memory, max_containers=workers)
    jobs = [{"mode": "render", "index": i, "serveUrl": serve, "comp": comp, "frameRange": [a, b], "scale": scale, "crf": crf,
             "gl": gl or m["gl"], "chromeMode": chrome_mode or m["chromeMode"], "concurrency": concurrency or m["concurrency"]}
            for i, (a, b) in enumerate(ranges)]
    machine = (gpu or ",".join(GPU_TYPES)) if mode == "gpu" else f"{cpu or CPU_CORES:g}-core CPU"
    lanes = [b - a + 1 for a, b in ranges] + ([local_frames] if local_frames else [])
    total = frames + local_frames
    desc = (f"{comp}: {frames} frames on Modal -> {len(jobs)} chunks on <= {workers} x {machine} "
            f"({jobs[0]['gl']}, {jobs[0]['concurrency']} tabs each)" + (f" + {local_frames} on this machine (lane {len(jobs)})" if local_frames else ""))
    if mode == "gpu" and workers > 10:
        print("[cloud] note: Modal's Starter plan runs at most 10 GPU containers at once; extra chunks wait for a free one", flush=True)
    print(f"[cloud] {desc}", flush=True)
    if episode:
        _xuong(["log", episode, "render", f"Modal: {len(jobs)} lane x {machine}" + (f" + local (lane {len(jobs)})" if local_frames else "")])
    t0 = time.time()
    results: dict[int, dict] = {}
    spawned: dict[int, float] = {}
    with modal.Dict.ephemeral() as progress:
        calls = []
        for j in jobs:
            spawned[j["index"]] = time.time()
            calls.append(fn.spawn(j, progress))
        last_report, last_print = 0.0, 0.0
        while len(results) < len(calls) or (local_pid and _alive(local_pid)):
            for i, c in enumerate(calls):
                if i in results:
                    continue
                try:
                    res = c.get(timeout=0)
                except (TimeoutError, modal.exception.TimeoutError):
                    continue
                Path(outdir, f"chunk_{i:03d}.mp4").write_bytes(res.pop("bytes"))
                res["spawnToStart"] = round(res["startAt"] - spawned[i], 1)
                results[i] = res
                print(f"[cloud] chunk {i} done: frames {jobs[i]['frameRange']} in {res['seconds']:.0f}s on {res['gpu']} "
                      f"({'cold' if res['cold'] else 'warm'}, started {res['spawnToStart']:.0f}s after spawn)", flush=True)
            now = time.time()
            if now - last_report >= 1.0:
                last_report = now
                try:
                    done = {int(k): int(v) for k, v in progress.items()}
                except Exception:
                    done = {}
                for i in results:
                    done[i] = lanes[i]
                if local_frames:
                    done[len(jobs)] = _local_progress(local_log) if local_log else 0
                total_done = sum(done.values())
                if episode:
                    ch = [f"--chunk={i}:{min(done.get(i, 0), n)}/{n}" for i, n in enumerate(lanes)]
                    _xuong(["render", episode, "--frame", str(total_done), "--total", str(total), "--where", "modal",
                            "--workers", str(workers + (1 if local_frames else 0)), *ch])
                if now - last_print >= 15:
                    last_print = now
                    print(f"[cloud] {total_done}/{total} frames, {now - t0:.0f}s", flush=True)
            time.sleep(0.5)
    wall = time.time() - t0
    Path(outdir, "list.txt").write_text("".join(f"file 'chunk_{i:03d}.mp4'\n" for i in range(len(jobs))))
    res = [results[i] for i in range(len(jobs))]
    cores = cpu or (GPU_CPU if mode == "gpu" else CPU_CORES)
    mem = memory or (GPU_MEM if mode == "gpu" else CPU_MEM)
    cost = sum(container_cost(r["endAt"] - r["bootAt"] + 12, r["gpu"], cores, mem) for r in res if r["cold"]) + \
        sum(container_cost(r["endAt"] - r["startAt"], r["gpu"], cores, mem) for r in res if not r["cold"]) + \
        sum(Path(outdir, f"chunk_{i:03d}.mp4").stat().st_size for i in range(len(jobs))) / 1e9 * 0.04  # egress
    summary = {"comp": comp, "frames": frames, "chunks": len(jobs), "workers": workers, "mode": mode, "machine": machine,
               "wall": round(wall, 1), "estCostUSD": round(cost, 3), "jobs": jobs, "results": res,
               "text": f"Modal {len(jobs)} chunk x {machine}, {wall:.0f}s, ~${cost:.2f}"}
    if stats:
        Path(stats).write_text(json.dumps(summary, indent=1))
    if not keep_bundle:  # bundles change with every edit: don't let them pile up on the volume
        try:
            vol.remove_file(serve.removeprefix("/vol"), recursive=True)
        except Exception as e:
            print(f"[cloud] could not remove {serve} from the volume: {e}", flush=True)
    print(f"[cloud] Modal part: {len(jobs)} chunks in {wall:.0f}s ({frames / wall:.2f} frames/s), est. ${cost:.2f}", flush=True)


@app.local_entrypoint()
def stills(bundle: str, comp: str, frames_list: str, out: str, scale: float = 1.3333, mode: str = "gpu", gpu: str = "",
           cpu: float = 0, gl: str = "", chrome_mode: str = "", image_format: str = "jpeg", variants: str = ""):
    """Render a few stills in one container (jpeg q88 like scripts/render/bridge-stills.mjs) to out<frame>.jpg.
    --variants "vulkan@headless-shell,angle-egl@headless-shell" renders the same frames once per gl/chromeMode."""
    m = MODES[mode]
    serve = _upload_bundle(bundle)
    f = _fn("stills", mode, gpu, cpu)
    frames = [int(x) for x in frames_list.split(",")]
    vs = variants.split(",") if variants else [f"{gl or m['gl']}@{chrome_mode or m['chromeMode']}"]
    for v in vs:
        g, cm = v.split("@") if "@" in v else (v, "headless-shell")
        job = {"mode": "stills", "serveUrl": serve, "comp": comp, "frames": frames, "scale": scale, "gl": g, "chromeMode": cm,
               "imageFormat": image_format, "jpegQuality": 88}
        t0 = time.time()
        try:
            res = f.remote(job)
        except Exception as e:
            print(f"[cloud] {v}: FAILED {e}", flush=True)
            continue
        tag = "" if len(vs) == 1 else f"{g}-{cm}_"
        for name, data in res["files"].items():
            Path(f"{out}{tag}{name[2:]}").write_bytes(data)
        st = [(e["frame"], e["s"]) for e in res["events"] if e["ev"] == "still"]
        warn = [e["text"][:160] for e in res["events"] if e["ev"] == "browserlog"][:5]
        print(f"[cloud] {v} on {res['gpu']}: stills {st}, worker {res['seconds']}s, call {time.time() - t0:.0f}s, warnings {warn}",
              flush=True)


@app.local_entrypoint()
def bench(bundle: str, comp: str, configs: str = "T4:4:3", start: int = 600, frames: int = 120, scale: float = 1.3333,
          out: str = ""):
    """Speed/cost of one container per config, all in parallel. config = <T4|L4|A10G|cpu>:<cores>:<tabs>[:<gl>].
    Prints cold start, setup, steady frames/s and USD/frame (container lifetime at list price)."""
    serve = _upload_bundle(bundle)
    calls = []
    for k, cfg in enumerate(configs.split(",")):
        parts = cfg.split(":")
        kind, cores, tabs = parts[0].upper(), float(parts[1]), int(parts[2])
        mode = "cpu" if kind == "CPU" else "gpu"
        gl = parts[3] if len(parts) > 3 else MODES[mode]["gl"]
        mem = max(4096, 2048 + 1536 * tabs) if mode == "gpu" else max(8192, 1024 * int(cores))
        f = _fn("render", mode, "" if mode == "cpu" else kind, cores, mem)
        job = {"mode": "render", "index": k, "serveUrl": serve, "comp": comp, "frameRange": [start, start + frames - 1],
               "scale": scale, "crf": 16, "gl": gl, "chromeMode": "headless-shell", "concurrency": tabs}
        calls.append((cfg, cores, mem, time.time(), f.spawn(job)))
    rows = []
    for cfg, cores, mem, t_spawn, c in calls:
        try:
            r = c.get()
        except Exception as e:
            print(f"[bench] {cfg}: FAILED {str(e)[:300]}", flush=True)
            continue
        if out:
            Path(f"{out}{cfg.replace(':', '_')}.mp4").write_bytes(r["bytes"])
        ev = {e["ev"]: e for e in r["events"]}
        first = ev.get("firstframe", {}).get("wall", 0)
        work = r["seconds"]
        steady = (frames - 1) / max(0.1, work - first)
        life = r["endAt"] - r["bootAt"] + 12
        usd = container_cost(life, r["gpu"], cores, mem)
        per_frame = container_cost(1 / steady, r["gpu"], cores, mem)
        rows.append((cfg, r["gpu"], round(r["startAt"] - t_spawn, 1), round(r["startAt"] - r["bootAt"], 1),
                     ev.get("composition", {}).get("wall"), first, round(work, 1), round(steady, 2), round(per_frame * 1000, 3),
                     round(usd, 4)))
        print(f"[bench] {cfg} on {r['gpu']} ({r['nproc']} vCPU): spawn->start {rows[-1][2]}s, setup {rows[-1][4]}s, first frame "
              f"{first}s, {frames} frames in {work:.0f}s -> steady {steady:.2f} fps, ${per_frame * 1000:.3f}/1000 frames, "
              f"container ${usd:.4f}", flush=True)
    print(json.dumps(rows))


@app.local_entrypoint()
def probe(gls: str = "vulkan@chrome-for-testing,angle-egl@chrome-for-testing", cmd: str = "", cmd_file: str = ""):
    """Print what a GPU container sees (GPU, driver libs, Vulkan) and Chrome's GPU report per gl flag (`remotion gpu`
    needs chrome-for-testing: the headless shell has no chrome://gpu page). --cmd / --cmd-file: run that shell instead."""
    if cmd_file:
        cmd = Path(cmd_file).read_text()
    print(diagnose.remote(gls.split(","), cmd))
