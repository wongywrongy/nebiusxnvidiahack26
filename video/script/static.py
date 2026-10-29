"""Longest fully static stretches of a video (mpdecimate): static.py <mp4> [n]."""
import re, subprocess, sys
from pathlib import Path
FF = Path.home() / '.local/opt/ffmpeg-deb/ffmpeg'
mp4, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 6
dur = float(subprocess.run([str(FF.with_name('ffprobe')), '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', mp4], capture_output=True, text=True).stdout)
log = subprocess.run([str(FF), '-hide_banner', '-nostats', '-i', mp4, '-vf', 'mpdecimate,showinfo', '-f', 'null', '-'], capture_output=True, text=True).stderr
k = [float(x) for x in re.findall(r'pts_time:([\d.]+)', log)]
gaps = sorted(((b - a, a) for a, b in zip(k, k[1:] + [dur])), reverse=True)
print(f'{mp4}: {dur:.2f} s, {len(k)} changing frames; longest static: ' + ', '.join(f'{g:.2f} s at {a:.2f}' for g, a in gaps[:n]))
