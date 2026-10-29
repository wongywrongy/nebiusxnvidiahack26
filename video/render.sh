#!/usr/bin/env bash
# Rebuild the SpecCheck video: the recording guide (teleprompter, 150 wpm timing) and the silent cut; with audio/vo.wav
# (Kyle's one take) also align it, fit the scenes to it and render the final cut with captions; then the gates.
# CLIPS=1 retakes the clips and screenshots first (k1, k4, k5 make live calls; see capture/README.md).
set -euo pipefail
cd "$(dirname "$0")"
[ -d node_modules ] || npm ci
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q soundfile faster-whisper scipy pillow rapidocr_onnxruntime; }
if [ "${CLIPS:-0}" = 1 ]; then npx playwright install chromium; for k in k2 k3 k4 k1 k5; do npx tsx capture/clips.ts $k; done; npx tsx capture/shots.ts; fi
rm -rf out/stage && mkdir -p out
R="npx remotion render remotion/index.ts --public-dir out/stage --codec h264 --crf 18"
# the recording guide always uses the 150 wpm script timing, so a new take can be read against it
GUIDE=1 .venv/bin/python script/vo.py
npx tsx remotion/prepare.ts
$R Guide out/speccheck-guide.mp4 --muted
.venv/bin/python script/vo.py
npx tsx remotion/prepare.ts
$R Silent out/speccheck-silent.mp4 --muted
if [ -f audio/vo.wav ]; then
  $R SpecCheck out/speccheck.mp4 --audio-codec aac --audio-bitrate 192k
  .venv/bin/python script/level.py out/speccheck.mp4
  .venv/bin/python script/gates.py out/speccheck.mp4 ${REF:-}  # REF=<earlier cut>: also check the voiceover is unchanged
else
  .venv/bin/python script/gates.py out/speccheck-silent.mp4
fi
npx remotion still remotion/index.ts Thumbnail out/thumbnail.png --public-dir out/stage
cp script/youtube.txt out/youtube.txt
