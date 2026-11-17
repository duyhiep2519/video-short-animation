#!/bin/zsh
# Did a change to src/engine/ alter a finished episode? Renders 12 half-size stills per episode on this machine and compares
# them byte for byte with the saved baseline (backup/engine-baseline/). No frame is looked at: identical files = identical
# picture. About 2 minutes for three episodes.
# usage: scripts/qa/engine-check.sh            compare with the baseline (exit 1 and a list if any frame differs)
#        scripts/qa/engine-check.sh save       save a new baseline (after an intended change, or for a new episode)
#        scripts/qa/engine-check.sh BridgeShort  compare one episode only
# A new episode: add its line to EPISODES (composition id, 12 frames spread over the film), then `save`.
set -e
cd "$(dirname "$0")/../.."
EPISODES=(
  "BridgeShort 40,200,380,560,740,920,1100,1280,1460,1640,1820,2000"
)
base=backup/engine-baseline; tmp=out/engine-check/now
mode=compare; only=""
[[ $1 == save ]] && mode=save || only=$1
pnpm exec tsc --noEmit || { echo "engine-check: typecheck failed"; exit 1; }
rm -rf $tmp; mkdir -p $tmp $base
bad=0
for e in $EPISODES; do
  comp=${e%% *}; frames=${e#* }
  [[ -n $only && $only != $comp ]] && continue
  COMP=$comp node scripts/render/bridge-stills.mjs $tmp/${comp}_ $frames 0.5 > $tmp/$comp.log 2>&1 || { echo "$comp: render failed (see $tmp/$comp.log)"; exit 1; }
  for f in ${(s:,:)frames}; do
    n=${comp}_$f.jpg
    if [[ $mode == save ]]; then cp $tmp/$n $base/$n
    elif [[ ! -f $base/$n ]]; then echo "$comp frame $f: no baseline (run: scripts/qa/engine-check.sh save)"; bad=1
    elif ! cmp -s $tmp/$n $base/$n; then echo "$comp frame $f: DIFFERENT  ($tmp/$n vs $base/$n)"; bad=1
    fi
  done
  [[ $mode == save ]] && echo "$comp: baseline saved" || echo "$comp: checked"
done
(( bad )) && { echo "engine-check: the picture changed"; exit 1; }
[[ $mode == save ]] || echo "engine-check: every frame is identical to the baseline"
