"""Voiceover timing for the scene plan. Kyle records one take (audio/vo.wav) over the silent guide render.

usage: script/vo.py
  no audio/vo.wav: guide timing, each line read at the script's wpm (150), words spaced by length; no audio.
  audio/vo.wav:    normalise the take to -16 LUFS, whisper word timestamps, align them to the script, find where each
                   segment's first word starts, and cut the take there into audio/segN.wav (only silence between lines
                   is trimmed; the audio is never sped up). Captions use the words he actually said.
Writes out/stage/timing.json and out/stage/script.json.
"""
import difflib, json, os, re, subprocess, sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
FFMPEG = [str(ROOT / 'node_modules/.bin/remotion'), 'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y']
TAKE = ROOT / 'audio/vo.wav'
SPEECH, SOFT, DEAD = -50, -75, -70  # dB per 10 ms: speech level, soft attacks and decays, dead air
EDGE = 0.05  # kept beyond a line's soft attack and decay (pauses between lines stay ≤ 0.7 s)


def script():
    s = json.loads((ROOT / 'script/segments.json').read_text())
    scores = json.loads((REPO / f"runs/recorded/{s['run_id']}/scores.json").read_text())
    def fill(text):
        def value(m):
            a, b = m[1].split('.')
            return str(scores[a][b])
        return re.sub(r'\{([\w.]+)\}', value, text)
    for seg in s['segments']:
        seg.update(json.loads(fill(json.dumps(seg, ensure_ascii=False))))
    return s


def words(text):
    return re.findall(r"[\w'’.,:;!?-]+", text)


def norm(w):
    w = w.lower().replace('’', "'")
    w = re.sub(r"[^\w']", '', w)
    return {'three': '3', 'zero': '0', 'two': '2', 'six': '6', 'eight': '8', 'five': '5', 'one': '1'}.get(w, w)


def guide(sw, wpm):
    """Script words spaced at `wpm`: each word's share grows with its length, with a beat after commas and full stops."""
    weight = [len(w) + 2 for w in sw]
    pause = [4 if re.search(r'[.!?]$', w) else 2 if re.search(r'[,:;]$', w) else 0 for w in sw]
    k = (len(sw) * 60 / wpm) / (sum(weight) + sum(pause[:-1]))
    out, t = [], 0.0
    for w, a, p in zip(sw, weight, pause):
        out.append({'w': w, 'start': round(t, 3), 'end': round(t + a * k, 3)})
        t += (a + p) * k
    return out


def align(script_words, heard):
    """Give every script word a start/end from whisper's words; interpolate any it misheard. Returns (words, matched)."""
    a, b = [norm(w) for w in script_words], [norm(h['word']) for h in heard]
    times = [None] * len(a)
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = (heard[blk.b + k]['start'], heard[blk.b + k]['end'])
    matched = [t is not None for t in times]
    known = [i for i, t in enumerate(times) if t]
    for i, t in enumerate(times):
        if t:
            continue
        lo = max([k for k in known if k < i], default=None)
        hi = min([k for k in known if k > i], default=None)
        s0 = times[lo][1] if lo is not None else 0.0
        s1 = times[hi][0] if hi is not None else (heard[-1]['end'] if heard else s0 + 0.3)
        span_lo = lo if lo is not None else -1
        span_hi = hi if hi is not None else len(a)
        step = (s1 - s0) / max(span_hi - span_lo - 1, 1)
        j = i - span_lo - 1
        times[i] = (s0 + j * step, s0 + (j + 1) * step)
    return [{'w': w, 'start': t[0], 'end': t[1]} for w, t in zip(script_words, times)], matched


def master(raw: Path, out: Path):
    # Two-pass loudnorm: measure, then apply linearly to -16 LUFS / -1.5 dBTP, mono, 48 kHz.
    probe = subprocess.run(FFMPEG[:3] + ['-i', str(raw), '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json',
                           '-f', 'null', '-'], capture_output=True, text=True)
    m = json.loads(re.search(r'\{[^{}]*"input_i"[^{}]*\}', probe.stderr).group(0))
    af = (f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    subprocess.run(FFMPEG + ['-i', str(raw), '-af', af, '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', str(out)], check=True)


def transcribe(wav):
    from faster_whisper import WhisperModel
    from scipy.signal import resample_poly
    data, rate = sf.read(wav, dtype='float32')
    audio = resample_poly(data, 16000, rate).astype(np.float32)  # faster-whisper's own PyAV decoder breaks on newer av
    model = WhisperModel('large-v3', device='cuda', compute_type='float16')
    segs, _ = model.transcribe(audio, language='en', word_timestamps=True, beam_size=5)
    return [{'word': w.word.strip(), 'start': w.start, 'end': w.end} for s in segs for w in s.words]


def roomtone(audio, rate, env, quiet, seconds=8.0):
    """A loopable bed of the take's own room sound at its own level, so the gaps between lines never drop to dead silence
    and never sound different from the pauses inside a line. Built from the longest stretches that sit at the room's floor
    (no breath, no mouth noise), joined with 30 ms equal-power crossfades. Writes audio/roomtone.wav."""
    near = np.convolve(~quiet, np.ones(31), 'same') > 0  # within 150 ms of speech
    floor = np.percentile(env[quiet & ~near], 10)
    calm = (env < floor + 6) & ~near
    calm &= np.convolve(env > floor + 12, np.ones(21), 'same') == 0  # 100 ms clear of any breath or click
    runs, i = [], 0
    while i < len(calm):
        j = i
        while j < len(calm) and calm[j] == calm[i]: j += 1
        if calm[i] and j - i >= 30: runs.append((i + 3, j - 3))  # ≥ 0.3 s, edges trimmed
        i = j
    if not runs:
        raise SystemExit('room tone: no stretch of 0.3 s at the room floor in the take')
    hop, x = int(0.01 * rate), int(0.03 * rate)
    fade_in = np.sin(np.linspace(0, np.pi / 2, x, dtype=np.float32)) ** 2
    bed = np.zeros(0, np.float32)
    while len(bed) < seconds * rate + x:
        for a, b in sorted(runs, key=lambda r: r[0] - r[1]):
            piece = audio[a * hop:b * hop].astype(np.float32)
            if len(bed) < x: bed = piece.copy(); continue
            bed[-x:] = bed[-x:] * fade_in[::-1] + piece[:x] * fade_in  # equal power: noise level stays flat across the join
            bed = np.concatenate([bed, piece[x:]])
    bed = bed[:int(seconds * rate) + x]
    bed[:x] = bed[:x] * fade_in + bed[-x:] * fade_in[::-1]  # crossfade the loop seam
    bed = bed[:-x]
    sf.write(ROOT / 'audio/roomtone.wav', bed, rate, subtype='PCM_16')
    level = 10 * np.log10((bed ** 2).mean() + 1e-12)
    print(f"room tone: {sum(b - a for a, b in runs) * 10} ms of the take's floor ({floor:.0f} dB) in {len(runs)} stretches, looped to "
          f"{len(bed) / rate:.1f} s at {level:.0f} dB RMS", file=sys.stderr)


def tighten(piece, rate, env, longest=0.6, keep=0.25):
    """Shorten every pause inside a line that runs over `longest` s: remove only its middle, and only where it is dead air
    (under DEAD), keeping `keep` s at each side. Speech is never touched or sped up. Returns the piece and a function that
    maps a time in the original piece to the shortened one."""
    quiet = env < SPEECH
    cuts, i = [], 0
    while i < len(env):
        if not quiet[i]:
            i += 1; continue
        j = i
        while j < len(env) and quiet[j]: j += 1
        if i > 0 and j < len(env) and (j - i) / 100 > longest:  # inside the line, not at its edges
            a, b = i + int(keep * 100), j - int(keep * 100)
            dead = [k for k in range(a, b) if env[k] < DEAD]
            if dead: cuts.append((dead[0] / 100, (dead[-1] + 1) / 100))
        i = j
    out = piece
    f = int(0.005 * rate)
    ramp = np.linspace(0, 1, f, dtype=np.float32)
    for a, b in reversed(cuts):  # 5 ms fades either side of each splice (in dead air, over the room-tone bed): no click
        head, tail = out[:int(a * rate)].copy(), out[int(b * rate):].copy()
        head[-f:] *= ramp[::-1]; tail[:f] *= ramp
        out = np.concatenate([head, tail])
    shift = lambda t: t - sum(min(b, max(a, t)) - a for a, b in cuts)
    return out, shift


def take(s):
    """Kyle's take → one wav and word timing per segment."""
    normed = ROOT / 'audio/vo-norm.wav'
    master(TAKE, normed)
    audio, rate = sf.read(normed, dtype='float32')
    heard = transcribe(normed)
    segs = s['segments']
    per = [words(g['vo']) for g in segs]
    aligned, matched = align([w for p in per for w in p], heard)
    timing, i = {}, 0
    spans = []
    for p in per:
        spans.append((aligned[i]['start'], aligned[i + len(p) - 1]['end'], aligned[i:i + len(p)], matched[i:i + len(p)]))
        i += len(p)
    # Cut in the pause between lines as the waveform shows it: whisper's word edges drift by a few hundred ms, enough
    # to clip a soft first or last word.
    hop = int(0.01 * rate)
    frames = audio[:len(audio) // hop * hop].reshape(-1, hop)
    env = 10 * np.log10((frames ** 2).mean(axis=1) + 1e-12)  # dB per 10 ms
    quiet = env < SPEECH
    soft = env > SOFT
    def pause(lo, hi):
        """The longest quiet run in [lo, hi) seconds, as (first quiet, first loud again) in seconds."""
        i0, i1 = max(0, int(lo * 100)), min(len(env), int(hi * 100))
        best, run = (i0, i0), None
        for i in range(i0, i1 + 1):
            if i < i1 and quiet[i]:
                run = i if run is None else run
            elif run is not None:
                best, run = max(best, (run, i), key=lambda r: r[1] - r[0]), None
        if best[1] == best[0]:  # no quiet frame at all: cut at the softest one
            k = i0 + int(np.argmin(env[i0:i1])); best = (k, k)
        return best[0] / 100, best[1] / 100
    def onset(t, most=20):  # back through a soft attack (above SOFT) for up to 0.2 s
        i = int(t * 100)
        for _ in range(most):
            if i == 0 or not soft[i - 1]: break
            i -= 1
        return i / 100
    def decay(t, most=15):  # on through a soft decay for up to 0.15 s
        i = int(t * 100)
        for _ in range(most):
            if i >= len(env) or not soft[i]: break
            i += 1
        return i / 100
    total = len(audio) / rate
    starts, ends = [0.0] * len(spans), [total] * len(spans)
    # the take's own head and tail: the nearest settled silence (0.3 s) to the first and last words, so clicks from
    # starting and stopping the recorder stay out
    settled = np.convolve(quiet, np.ones(30), 'valid') == 30  # settled[i]: frames i … i+29 all quiet
    first, last = int(spans[0][0] * 100), int(spans[-1][1] * 100)
    head = [i for i in range(0, min(first + 30, len(settled))) if settled[i]]
    tail = [i for i in range(max(0, last - 10), len(settled)) if settled[i]]
    starts[0] = max(0.0, onset((head[-1] + 30) / 100 if head else 0.0) - EDGE)
    ends[-1] = min(total, decay(tail[0] / 100 if tail else total) + EDGE)
    for n in range(len(spans) - 1):
        t1, t0 = spans[n][1], spans[n + 1][0]
        q0, q1 = pause(min(t1, t0) - 0.6, max(t1, t0) + 0.6)
        mid = (q0 + q1) / 2
        ends[n], starts[n + 1] = min(decay(q0) + EDGE, mid), max(onset(q1) - EDGE, mid)
    roomtone(audio, rate, env, quiet)
    loud = [round(t, 2) for t in starts[1:] + ends[:-1] if soft[min(int(t * 100), len(soft) - 1)]]
    # a word is clipped only if audible sound lies between a cut and it (whisper's word edges run early and late)
    def clipped(h):
        if any(x <= h['start'] and h['end'] <= y for x, y in zip(starts, ends)): return False
        lo, hi = int(h['start'] * 100), int(h['end'] * 100)
        inside = np.zeros(hi - lo, bool)
        for x, y in zip(starts, ends):
            inside[max(0, int(x * 100) - lo):max(0, int(y * 100) - lo)] = True
        return bool((~quiet[lo:hi] & ~inside).any())  # speech-level sound outside every cut
    outside = [h['word'] for h in heard if clipped(h)]
    print(f"cuts on sound: {loud or 'none'} · words clipped by a cut: {', '.join(outside) or 'none'}", file=sys.stderr)
    for n, (g, (t0, t1, ws, ok)) in enumerate(zip(segs, spans)):
        a, b = starts[n], ends[n]
        piece, shift = tighten(audio[int(a * rate):int(b * rate)].copy(), rate, env[int(a * 100):int(b * 100)])
        ramp = np.linspace(0, 1, int(0.01 * rate), dtype=np.float32)  # 10 ms fades: no edge can click
        piece[:len(ramp)] *= ramp
        piece[-len(ramp):] *= ramp[::-1]
        sf.write(ROOT / f"audio/seg{g['id'][3:]}.wav", piece, rate, subtype='PCM_16')
        at = lambda t: round(shift(t - a), 3)
        said = [{'w': h['word'], 'start': at(h['start']), 'end': at(h['end'])} for h in heard if a <= h['start'] < b]
        timing[g['id']] = {'mode': 'vo', 'duration': round(len(piece) / rate, 3), 'vo': g['vo'], 'matched': round(sum(ok) / len(ok), 2),
                           'words': [{'w': w['w'], 'start': at(w['start']), 'end': at(w['end'])} for w in ws], 'heard': said}
        flag = '' if sum(ok) / len(ok) >= 0.6 else '   ← check: under 60% of the script words heard'
        print(f"{g['id']} {g['scene']}: {len(piece) / rate:5.2f} s at {a:7.2f} s · {sum(ok)}/{len(ok)} script words heard{flag}", file=sys.stderr)
    return timing


def main():
    s = script()
    stage = ROOT / 'out/stage'
    stage.mkdir(parents=True, exist_ok=True)
    if TAKE.exists() and not os.environ.get('GUIDE'):  # GUIDE=1: the 150 wpm guide timing even when a take exists
        timing = take(s)
    else:
        timing = {}
        for g in s['segments']:
            ws = guide(words(g['vo']), s['wpm'])
            timing[g['id']] = {'mode': 'guide', 'duration': ws[-1]['end'], 'vo': g['vo'], 'words': ws}
        print(f"guide timing at {s['wpm']} wpm (no audio/vo.wav yet)", file=sys.stderr)
    (stage / 'timing.json').write_text(json.dumps(timing, indent=1, ensure_ascii=False) + '\n')
    (stage / 'script.json').write_text(json.dumps(s, indent=1, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
