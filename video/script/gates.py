"""Gates for a cut: duration, voiceover unchanged against a reference cut, static stretches, inset first/last frames,
highlights (first/middle/last frame), headlines readable 12 frames after their cue (OCR), frame-edge margins, blank
screenshots, banned words (OCR of every second), whisper diff against the script (only with Kyle's take), 1 fps audit
sheets and a one-frame-per-scene contact sheet.
usage: gates.py [out/speccheck.mp4] [reference.mp4]   Writes out/gates/report.txt."""
import difflib, hashlib, json, re, subprocess, sys
from pathlib import Path
import numpy as np, soundfile as sf
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FF = str(Path.home() / '.local/opt/ffmpeg-deb/ffmpeg')
sys.path.insert(0, str(ROOT / 'script'))
from vo import norm, words  # noqa: E402

plan = json.loads((ROOT / 'out/stage/data.json').read_text())
fps, fade = plan['fps'], plan['fade']
starts, t = {}, 0
for s in plan['scenes']:
    starts[s['id']] = t
    t += s['frames'] - fade
mp4 = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / 'out/speccheck.mp4'
out = ROOT / 'out/gates'
out.mkdir(parents=True, exist_ok=True)
report = []
def say(line=''):
    print(line, flush=True); report.append(line)

probe = json.loads(subprocess.run([str(Path(FF).with_name('ffprobe')), '-v', 'error', '-show_entries', 'format=duration:stream=codec_name,width,height,r_frame_rate,bit_rate',
                                   '-of', 'json', str(mp4)], capture_output=True, text=True).stdout)
dur = float(probe['format']['duration'])
say(f"{mp4.name}: duration {dur:.2f} s ({int(dur // 60)}:{dur % 60:05.2f}) · within 1 s of 2:30 {'PASS' if 149 <= dur <= 151 else 'FAIL'} · hard limit 2:55 {'PASS' if dur <= 175 else 'FAIL'}")
# The voiceover must be the reference cut's, untouched: the same AAC stream bytes and the same decoded samples.
ref = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
if ref and plan['vo']:
    def audio(f, *codec):
        return hashlib.sha256(subprocess.run([FF, '-nostdin', '-loglevel', 'error', '-i', str(f), '-map', '0:a', *codec, '-'], capture_output=True, check=True).stdout).hexdigest()
    same = [audio(mp4, '-c', 'copy', '-f', 'data') == audio(ref, '-c', 'copy', '-f', 'data'), audio(mp4, '-f', 's16le') == audio(ref, '-f', 's16le')]
    say(f"voiceover vs {ref.name}: stream bytes {'identical' if same[0] else 'DIFFER'}, decoded samples {'identical' if same[1] else 'DIFFER'} · {'PASS' if all(same) else 'FAIL'}")
say('streams ' + ', '.join(f"{x['codec_name']} {x.get('width', '')}x{x.get('height', '')} {x.get('r_frame_rate', '')}" for x in probe['streams']))
say(subprocess.run([sys.executable, str(ROOT / 'script/static.py'), str(mp4), '5'], capture_output=True, text=True).stdout.strip())

STILLS = []
def still(frame, name):  # queued, then rendered from one bundle
    STILLS.append(f'{frame}:{Path(name).stem}')
def render_stills():
    subprocess.run(['npx', 'tsx', str(ROOT / 'remotion/stills.ts'), str(out), *STILLS], check=True, stdin=subprocess.DEVNULL, cwd=ROOT, capture_output=True)
    STILLS.clear()

# Insets: the first frame they are fully in and the last before they leave; crop edges must not touch text.
for s in plan['scenes']:
    for n, ins in enumerate(s.get('insets', [])):
        a = starts[s['id']] + ins['at'] + int(0.6 * fps)
        z = starts[s['id']] + min(ins['out'], s['frames'] - fade) - 2
        still(a, f"{s['id']}-inset{n}-first.png"); still(z, f"{s['id']}-inset{n}-last.png")
        say(f"{s['id']} inset {n} {ins['shot']} crop {ins['crop']} at {ins['scale']}x · edge text px {ins['edgeInk']} · frames {a}, {z}")
    if s['type'] == 'trace':
        i = s['inset']
        still(starts[s['id']] + i['at'] + int(0.6 * fps), f"{s['id']}-pan-first.png"); still(starts[s['id']] + s['frames'] - fade - 2, f"{s['id']}-pan-last.png")
        say(f"{s['id']} panning inset {i['shot']} crop {i['crop']} at {i['scale']}x")

# Highlights: the first frame fully in, the middle and the last frame before the fade-out, each for a look by eye.
lights = []
for s in plan['scenes']:
    for n, h in enumerate(s.get('highlights', [])):
        a, z = h['at'] + 8, min(h['out'], s['frames'] - fade) - 9
        for tag, fr in (('first', a), ('mid', (a + z) // 2), ('last', z)):
            still(starts[s['id']] + fr, f"hl-{s['id']}-{n}-{tag}.png")
        lights.append((s['id'], n, h.get('shot') or f"{h['clip']} clip", [starts[s['id']] + x for x in (a, (a + z) // 2, z)]))

# Headlines and overlays: a still 12 frames after each cue; OCR must find the whole line.
HEAD = []
def head(sid, text, at):
    HEAD.append((sid, text, at)); still(starts[sid] + at + 12, f"head-{len(HEAD):02d}.png")
for s in plan['scenes']:
    sid, c = s['id'], s.get('cues') or {}
    if s['type'] == 'title':
        head(sid, 'SpecCheck', 2); head(sid, ' '.join(w for w, _ in s['tag']), min(a for _, a in s['tag'])); head(sid, 'and says what to send instead', s['send'])
    if s['type'] == 'context':
        for k, t in (('specLabel', 'The spec'), ('productLabel', 'The submittal'), ('match', 'Must match'), ('stamp', 'REVISE AND RESUBMIT'), ('weeks', '+ weeks')):
            head(sid, t, c[k])
    if s['type'] == 'live':
        head(sid, 'Nebius Token Factory', c['label']); [head(sid, n['note'], n['at']) for n in s['nodes']]
    if s.get('headline'):
        head(sid, s['headline']['text'], s['headline']['at'])
    if s.get('detail'):
        head(sid, s['detail']['text'], s['detail']['at'])
    if s['type'] == 'gate':
        head(sid, 'Models read and quote. Code decides.', c['head']); head(sid, 'Unproven values go to a person, never faked', c['unproven'])
    if s['type'] == 'trace':
        head(sid, 'How this was checked', 0)
    if s['type'] == 'arch':
        head(sid, 'How it runs', 0); head(sid, ' '.join(b['title'] for b in s['boxes']), s['boxes'][0]['at'] + 3 * (len(s['boxes']) - 1))
    if s['type'] == 'memo':
        head(sid, 'One memo for the package', 0); head(sid, 'Print view', s['chip']['at'])
    if s['type'] == 'results':
        head(sid, f"Caught of {s['number']['of']} planted problems", 0); head(sid, 'on real manufacturer documents', s['number']['at'] + int(0.6 * fps))
    if s['type'] == 'close':
        head(sid, ' '.join(w for w, _ in s['words']), s['words'][0][1]); head(sid, ' '.join(w for w, _ in s['words2']), s['words2'][0][1])
        head(sid, plan['base_url'].replace('https://', ''), c['end'] + 4)

# Frame-edge margins: the box of everything that isn't page background, at 10/50/90% of each scene.
for s in plan['scenes']:
    for f in (0.1, 0.5, 0.9):
        still(starts[s['id']] + int(s['frames'] * f), f"edge-{s['id']}-{f}.png")
render_stills()

from rapidocr_onnxruntime import RapidOCR  # noqa: E402
ocr = RapidOCR()
key = lambda t: re.sub(r'[^a-z0-9]', '', t.lower())
say(f"highlights: {len(lights)}, each checked on its first, middle and last frame (sheet: out/gates/highlights.png)")
for sid, n, what, frs in lights:
    say(f"  {sid} #{n} on {what}: frames {frs[0]}, {frs[1]}, {frs[2]}")
rows = [[Image.open(out / f"hl-{sid}-{n}-{t}.png").resize((640, 360)) for t in ('first', 'mid', 'last')] for sid, n, _, _ in lights]
sheet = Image.new('RGB', (1920, 360 * len(rows)), (11, 12, 15))
for r, row in enumerate(rows):
    for i, im in enumerate(row):
        sheet.paste(im, (640 * i, 360 * r))
sheet.save(out / 'highlights.png')
misses = []
for i, (sid, text, at) in enumerate(HEAD, 1):
    seen = key(' '.join(t for _, t, _ in (ocr(str(out / f'head-{i:02d}.png'))[0] or [])))
    ok = all(key(w) in seen for w in text.split() if key(w))
    misses += [] if ok else [text]
    say(f"  headline {sid} @ frame {starts[sid] + at} (+12): “{text}” {'readable' if ok else 'NOT FOUND'}")
say(f"headlines fully readable 12 frames (0.2 s) after their cue: {len(HEAD) - len(misses)} of {len(HEAD)} {'PASS' if not misses else 'FAIL'}")
edges = {}
for s in plan['scenes']:
    m = [9999] * 4
    for f in (0.1, 0.5, 0.9):
        g = np.abs(np.asarray(Image.open(out / f"edge-{s['id']}-{f}.png").convert('RGB'), dtype=np.int16) - np.array([11, 12, 15])).max(-1) > 16
        ys, xs = np.nonzero(g)
        m = [min(m[0], xs.min()), min(m[1], 1919 - xs.max()), min(m[2], ys.min()), min(m[3], 1079 - ys.max())]
    edges[s['id']] = m
    need = 96 if s['type'] in ('context', 'arch') else 1
    say(f"  margins {s['id']} {s['type']}: left {m[0]}, right {m[1]}, top {m[2]}, bottom {m[3]} px · {'PASS' if min(m[:2]) >= need and min(m) >= 1 else 'FAIL'}" + (' (sides ≥ 96)' if need > 1 else ''))

# Blank screenshots: fully white 64-px tiles (CSS px) in each PNG, and the largest flat (single-colour) tile run.
for png in sorted((ROOT / 'out/stage').glob('*.png')):  # the screenshots this cut uses
    g = np.asarray(Image.open(png).convert('L').resize((1440, 900)), dtype=np.int16)
    tiles = [(y, x) for y in range(0, 900 - 63, 64) for x in range(0, 1440 - 63, 64)]
    white = sum(g[y:y + 64, x:x + 64].min() > 245 for y, x in tiles)
    say(f'{png.name}: {white} of {len(tiles)} tiles blank white ({100 * white / len(tiles):.1f}%)')

# Banned words: OCR of one frame per second of the cut.
BANNED = re.compile(r"couldn.?t confirm|not confirmed|false alarm|\b0 of\b|ultra|no alternate", re.I)
frames = out / 'ocr'
frames.mkdir(exist_ok=True)
for old in frames.glob('*.png'):
    old.unlink()
subprocess.run([FF, '-nostdin', '-loglevel', 'error', '-y', '-i', str(mp4), '-vf', 'fps=1', str(frames / '%04d.png')], check=True)
hits = [(png.stem, text) for png in sorted(frames.glob('*.png')) for _, text, _ in (ocr(str(png))[0] or []) if BANNED.search(text)]
say(f"banned phrases (Couldn't confirm, Not confirmed, false alarm, 0 of, Ultra, No alternate) in {len(list(frames.glob('*.png')))} frames: {len(hits)} {'PASS' if not hits else 'FAIL'}")
[say(f'  {int(sec) - 1} s: {text}') for sec, text in hits]

# Speed chips: one per time-lapse, one value each.
chips = [(s['id'], u['id'], c['text']) for s in plan['scenes'] for u in (s.get('clips') or []) + ([s['lead']] if s.get('lead') else []) for c in u['chips']]
uses = {(sid, uid) for sid, uid, _ in chips}
say(f"speed chips: {', '.join(f'{sid}/{uid} {t}' for sid, uid, t in chips)} · {'PASS' if len(uses) == len(chips) else 'FAIL'} (one per time-lapse)")
# Crop edges of pages, matrix and memo crops (insets are checked above).
crops = [(s['id'], c.get('shot', ''), c.get('edgeInk', 0)) for s in plan['scenes'] for c in ([s['page']] if s.get('page') else []) + (s.get('crops') or []) + (s.get('pages') or []) if 'edgeInk' in c]
say('crop edges (text px on the edge): ' + ', '.join(f'{sid} {shot} {n}' for sid, shot, n in crops))
# Pauses: no silence over 0.7 s between the first and last words (the room-tone bed is −60 dB; under −50 dB counts as silence).
if plan['vo'] and mp4.name == 'speccheck.mp4':
    log = subprocess.run([FF, '-nostdin', '-hide_banner', '-i', str(mp4), '-af', 'silencedetect=noise=-50dB:d=0.7', '-f', 'null', '-'], capture_output=True, text=True).stderr
    close = plan['scenes'][-1]  # the end of the last spoken word; the end card's hold follows it
    said = json.loads((ROOT / 'out/stage/timing.json').read_text())[close['id']]['heard']
    last_word = (starts[close['id']] + close['audioAt']) / fps + said[-1]['end'] + 0.1
    gaps = [(float(a), float(b)) for a, b in re.findall(r'silence_start: ([\d.]+)[\s\S]*?silence_end: ([\d.]+)', log) if 1.0 < float(a) < last_word]
    say(f"pauses over 0.7 s between the first and last word: {len(gaps)} {'PASS' if not gaps else 'FAIL'}" + ''.join(f' · {a:.2f}–{b:.2f} s' for a, b in gaps))
# Mostly-white frames, for a look by eye (a blank, still-loading PDF would show here; memo pages and PDF pages are white too).
white = []
for png in sorted(frames.glob('*.png')):
    g = np.asarray(Image.open(png).convert('L').resize((480, 270)), dtype=np.int16)
    tiles = [g[y:y + 30, x:x + 30].min() > 235 for y in range(0, 270, 30) for x in range(0, 480, 30)]
    if sum(tiles) / len(tiles) > 0.12:
        white.append(int(png.stem) - 1)
say(f'frames with large white areas (check by eye): {white}')

# Whisper on the final mix, one slice per scene, against the script (only once the cut carries Kyle's take).
if plan['vo'] and mp4.name == 'speccheck.mp4':
    from faster_whisper import WhisperModel  # noqa: E402
    subprocess.run([FF, '-nostdin', '-loglevel', 'error', '-y', '-i', str(mp4), '-vn', '-ac', '1', '-ar', '16000', str(ROOT / 'out/final-audio.wav')], check=True)
    audio, _ = sf.read(ROOT / 'out/final-audio.wav', dtype='float32')
    model = WhisperModel('large-v3', device='cuda', compute_type='float16')
    script = json.loads((ROOT / 'out/stage/script.json').read_text())
    diff = []
    for seg, s in zip(script['segments'], plan['scenes']):
        part = audio[int(starts[s['id']] / fps * 16000):int((starts[s['id']] + s['frames']) / fps * 16000)]
        heard = ' '.join(x.text.strip() for x in model.transcribe(part, language='en', beam_size=5)[0])
        a, b = words(seg['vo']), words(heard)
        diff += [f"{seg['id']}: script “{' '.join(a[i1:i2])}” → heard “{' '.join(b[j1:j2])}”"
                 for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, [norm(w) for w in a], [norm(w) for w in b], autojunk=False).get_opcodes() if op != 'equal']
    say(f'whisper: {len(diff)} differences from the script'); [say('  ' + d) for d in diff]
else:
    say('whisper: skipped (no voice in this cut)')

# 1 fps audit sheets (every second of the cut) and one frame per scene.
subprocess.run([FF, '-nostdin', '-loglevel', 'error', '-y', '-i', str(mp4), '-vf', 'fps=1,scale=480:-1,tile=6x5', str(out / 'audit-%02d.png')], check=True)
for s in plan['scenes']:
    still(starts[s['id']] + int(s['frames'] * 0.9), f"scene-{s['id']}.png")
render_stills()
imgs = [Image.open(out / f"scene-{s['id']}.png").resize((640, 360)) for s in plan['scenes']]
sheet = Image.new('RGB', (1920, 360 * ((len(imgs) + 2) // 3)), (11, 12, 15))
for i, im in enumerate(imgs):
    sheet.paste(im, ((i % 3) * 640, (i // 3) * 360))
sheet.save(ROOT / 'out/contact-sheet.png')
sheet_hits = [text for _, text, _ in (ocr(str(ROOT / 'out/contact-sheet.png'))[0] or []) if BANNED.search(text)]
say(f"contact sheet: out/contact-sheet.png · banned phrases: {len(sheet_hits)} {'PASS' if not sheet_hits else 'FAIL'} {sheet_hits or ''}· audit sheets: out/gates/audit-*.png")
(out / 'report.txt').write_text('\n'.join(report) + '\n')
