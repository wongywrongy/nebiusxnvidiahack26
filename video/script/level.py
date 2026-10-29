"""Set a cut's loudness to -16 LUFS with one fixed gain (no compression), copying the video untouched.
usage: level.py out/speccheck.mp4"""
import json, re, subprocess, sys
from pathlib import Path

FF = str(Path.home() / '.local/opt/ffmpeg-deb/ffmpeg')
mp4 = Path(sys.argv[1])
def measure(path):
    log = subprocess.run([FF, '-nostdin', '-hide_banner', '-i', str(path), '-af', 'loudnorm=I=-16:TP=-1.5:print_format=json', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    m = json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', log).group(0))
    return float(m['input_i']), float(m['input_tp'])
i, tp = measure(mp4)
gain = -16 - i
assert tp + gain <= -1.0, f'peak would reach {tp + gain:.1f} dBTP'
tmp = mp4.with_suffix('.level.mp4')
subprocess.run([FF, '-nostdin', '-loglevel', 'error', '-y', '-i', str(mp4), '-c:v', 'copy', '-af', f'volume={gain:.2f}dB', '-c:a', 'aac', '-b:a', '192k',
                '-movflags', '+faststart', str(tmp)], check=True)
tmp.replace(mp4)
print(f'{mp4.name}: {i:.1f} → {measure(mp4)[0]:.1f} LUFS (gain {gain:+.2f} dB), true peak {tp + gain:.1f} dBTP')
