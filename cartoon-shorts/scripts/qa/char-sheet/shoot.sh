#!/bin/zsh
# Contact sheets of the character drawing options (gestures, talk, back view, outfits, props, fx) straight from
# src/engine/toon.ts, without rendering the 3D scene. Output: out/char-sheet/<sheet>.png (temporary files stay in out/).
# usage: scripts/qa/char-sheet/shoot.sh "<sheet>[&k=0.4&cols=7]" ...      sheets: see the top of sheet.src.txt
#   e.g. scripts/qa/char-sheet/shoot.sh gestA_ti gestB_ba outfits props fx
cd "$(dirname "$0")"
out=../../../out/char-sheet; mkdir -p $out
pnpm exec esbuild sheet.src.txt --loader:.txt=ts --bundle --format=iife --outfile=$out/sheet.js --log-level=warning || exit 1
echo '<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#a9bcc6}canvas{display:block}</style><body><script src="sheet.js"></script></body>' > $out/sheet.html
for s in "$@"; do
  nm=${s%%&*}
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --hide-scrollbars --window-size=${W:-1680},${H:-1600} --screenshot=$PWD/$out/$nm.png "file://$PWD/$out/sheet.html#sheet=$s" >/dev/null 2>&1
  echo out/char-sheet/$nm.png
done
