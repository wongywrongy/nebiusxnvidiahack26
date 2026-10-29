"""Render one still per scene at fractions of its length: stills.py [frac ...] → out/check/<seg>-<frac>.png"""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
plan = json.loads((ROOT / 'out/stage/data.json').read_text())
fracs = [float(x) for x in sys.argv[1:]] or [0.66]
only = None
out = ROOT / 'out/check'; out.mkdir(parents=True, exist_ok=True)
t, frames = 0, []
for s in plan['scenes']:
    frames += [(s['id'], f, t + int(s['frames'] * f)) for f in fracs]
    t += s['frames'] - plan['fade']
for seg, f, fr in frames:
    subprocess.run([str(ROOT / 'node_modules/.bin/remotion'), 'still', str(ROOT / 'remotion/index.ts'), 'SpecCheck', str(out / f'{seg}-{f}.png'),
                    f'--frame={fr}', '--public-dir', str(ROOT / 'out/stage'), '--log=error'], check=True, stdin=subprocess.DEVNULL)
    print(seg, f, fr, flush=True)
