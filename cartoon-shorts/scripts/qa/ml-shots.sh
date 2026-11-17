#!/bin/zsh
# Dump the long cut's shot table (ids, names, frames, camera key frames) to out/ml/shots.json. usage: scripts/qa/ml-shots.sh [episode=madalong]
cd "$(dirname "$0")/../.."
ep=${1:-madalong}; mkdir -p out/ml
cat > out/ml/shots.entry.mts <<EOF
import { SHOTS, TOTAL } from "../../src/videos/$ep/film";
console.log(JSON.stringify({ total: TOTAL, shots: SHOTS.map((s) => ({ id: s.id, k: s.k, a: s.a, b: s.b, keys: s.cam.map((c) => c.f), x: s.x ?? 0, light: s.light, kicks: s.kicks ?? [], flood: !!s.flood })) }));
EOF
pnpm exec esbuild out/ml/shots.entry.mts --bundle --platform=node --format=esm --outfile=out/ml/shots.bundle.mjs --log-level=error --external:three --external:remotion \
  --banner:js='globalThis.document={createElement:()=>({getContext:()=>null,width:0,height:0,style:{}})};' && node out/ml/shots.bundle.mjs > out/ml/shots.json
rm -f out/ml/shots.entry.mts out/ml/shots.bundle.mjs
