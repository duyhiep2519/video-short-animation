#!/bin/zsh
# Dump the shot table of a film made with the long-cut framework (ids, names, frames, light, camera key frames).
# usage: scripts/qa/film-shots.sh caygaolong long|short|both   -> out/cgl/shots.json (long), out/cgl/shotsS.json (short)
#        scripts/qa/film-shots.sh quynhaptrang long|short|both -> out/qnt/shots.json, out/qnt/shotsS.json
#        scripts/qa/film-shots.sh madalong                     -> out/ml/shots.json (same as scripts/qa/ml-shots.sh)
# Each shot: { id, k, a (first frame), b (first frame of the next shot), last (b - 1), keys [camera key frames], x, light,
# kicks, + the episode's switches }. Also prints a readable table. The audio script and long_qa.py read these files.
cd "$(dirname "$0")/../.."
ep=${1:-caygaolong}; which=${2:-both}
[[ $ep == madalong ]] && { scripts/qa/ml-shots.sh madalong; exit $?; }
dir=out/cgl; [[ $ep != caygaolong ]] && dir=out/$ep
[[ $ep == quynhaptrang ]] && dir=out/qnt
mkdir -p $dir
cat > $dir/shots.entry.mts <<EOT
import { LONG, SHORT } from "../../src/videos/$ep/film";
import { writeFileSync } from "node:fs";
const dump = (F: typeof LONG) => ({ film: F.name, w: F.W, h: F.H, total: F.TOTAL, shots: F.SHOTS.map((s) => ({ id: s.id, k: s.k, a: s.a, b: s.b, last: s.b - 1,
  keys: s.cam.map((c) => Math.max(s.a, Math.min(s.b - 1, c.f))), x: s.x ?? 0, light: s.light, kicks: s.kicks ?? [], bolts: (s as any).bolts ?? [], warm: typeof s.warm === "number" ? s.warm : s.warm ? 1 : 0,
  lamp: s.light === "lamp", fallen: !!(s as any).fallen, bare: !!(s as any).bare, tilt: !!(s as any).tilt, vision: (s as any).vision !== undefined,
  flood: !!(s as any).flood, peek: !!(s as any).peek, coop: (s as any).coop !== undefined, lampSwitch: !!s.lamp, png: (s.png ?? []).map((p) => [p.src, p.f0, Math.min(p.f1, F.TOTAL)]) })) });
const which = process.argv[2];
for (const [n, F, file] of [["long", LONG, "shots.json"], ["short", SHORT, "shotsS.json"]] as const) {
  if (which !== "both" && which !== n) continue;
  const d = dump(F); writeFileSync("$dir/" + file, JSON.stringify(d));
  console.log(\`\${n}: \${d.shots.length} shots, \${d.total} frames (\${(d.total / 30).toFixed(1)} s) -> $dir/\${file}\`);
  for (const s of d.shots) console.log(\`  \${String(s.id).padStart(3)} \${s.k.padEnd(16)} \${String(s.a).padStart(5)}-\${String(s.last).padEnd(5)} \${s.light.padEnd(7)} keys \${s.keys.join(",")}\`);
}
EOT
pnpm exec esbuild $dir/shots.entry.mts --bundle --platform=node --format=esm --outfile=$dir/shots.bundle.mjs --log-level=error --external:three --external:remotion \
  --banner:js='globalThis.document={createElement:()=>({getContext:()=>null,width:0,height:0,style:{}})};' && node $dir/shots.bundle.mjs $which
r=$?; rm -f $dir/shots.entry.mts $dir/shots.bundle.mjs; exit $r
