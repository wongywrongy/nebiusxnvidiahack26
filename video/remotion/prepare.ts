// Scene plan for the 60 fps cut. Every cue in script/segments.json names a spoken phrase and becomes a frame from the
// whisper word timings: "@phrase" = its first word starts, "@@phrase" = its last word ends, "~phrase" = [start, end].
// Insets are cropped from the 2880 px screenshots around a saved box, trimmed to the text they contain (never through it).
import { execFileSync, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const STAGE = path.join(ROOT, 'out/stage')
const FFMPEG = process.env.FFMPEG_X11 || path.join(os.homedir(), '.local/opt/ffmpeg-deb/ffmpeg')
const FPS = 60
const FADE = 10 // scene crossfade, frames
const f = (s: number) => Math.round(s * FPS)

type Word = { w: string; start: number; end: number }
type Box = { x: number; y: number; w: number; h: number }

const script = JSON.parse(fs.readFileSync(path.join(STAGE, 'script.json'), 'utf8'))
const PAD_S: number = script.line_pad_s // after each scene's voiceover
const timing = JSON.parse(fs.readFileSync(path.join(STAGE, 'timing.json'), 'utf8'))
const shotMeta = (id: string) => JSON.parse(fs.readFileSync(path.join(ROOT, 'shots', `${id}.json`), 'utf8'))

const norm = (w: string) => w.toLowerCase().replace(/[’]/g, "'").replace(/[^\w']/g, '')
function find(words: Word[], text: string, seg: string) {
  const want = text.split(/\s+/).map(norm).filter(Boolean), have = words.map(w => norm(w.w))
  for (let i = 0; i + want.length <= have.length; i++)
    if (want.every((w, k) => have[i + k] === w)) return { start: words[i].start, end: words[i + want.length - 1].end }
  throw new Error(`${seg}: cue not in voiceover: “${text}”`)
}
// Resolve every cue string in a scene spec into frames (a little before the word, so the element lands on it).
function resolve(v: unknown, words: Word[], seg: string, off = 0): unknown {
  if (typeof v === 'string') {
    if (v.startsWith('@@')) return off + f(find(words, v.slice(2), seg).end)
    if (v.startsWith('@')) return off + Math.max(0, f(find(words, v.slice(1), seg).start) - 4)
    if (v.startsWith('~')) { const p = find(words, v.slice(1), seg); return [off + f(p.start), off + f(p.end)] }
    return v
  }
  if (Array.isArray(v)) return v.map(x => resolve(x, words, seg, off))
  if (v && typeof v === 'object') return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, k === 'vo' ? x : resolve(x, words, seg, off)]))
  return v
}

// Ink map of a screenshot at CSS resolution: 1 where a pixel sits on a strong luminance edge (text, rules, borders).
const inkCache = new Map<string, { m: Uint8Array; W: number; H: number }>()
function ink(id: string) {
  if (inkCache.has(id)) return inkCache.get(id)!
  const W = 1440, H = 900
  const g = execFileSync(FFMPEG, ['-nostdin', '-loglevel', 'error', '-i', path.join(ROOT, 'shots', `${id}.png`), '-vf', `scale=${W}:${H},format=gray`,
    '-f', 'rawvideo', '-'], { maxBuffer: 1 << 28 })
  const m = new Uint8Array(W * H)
  for (let y = 1; y < H - 1; y++) for (let x = 1; x < W - 1; x++) {
    const i = y * W + x
    m[i] = Math.max(Math.abs(g[i + 1] - g[i - 1]), Math.abs(g[i + W] - g[i - W])) > 40 ? 1 : 0
  }
  const r = { m, W, H }
  inkCache.set(id, r)
  return r
}
// Inset crop: the element's box plus up to 10 px of clear space on each side (cards sit 12 px apart and their faint
// borders read as no ink), narrowed to the ink it contains, so a crop
// edge sits on empty pixels or a border line, never through text. Scale 2–2.5x, capped so the card fits the frame.
function inset(id: string, box: Box) {
  const { m, W, H } = ink(id)
  const x0 = Math.max(0, Math.floor(box.x - 16)), x1 = Math.min(W, Math.ceil(box.x + box.w + 16))
  // a crop edge may sit on a straight border line (≥ 80% inked), a hairline crossing (≤ 3 px) or empty pixels, never on text
  const isText = (n: number, len: number) => n > 3 && n < 0.8 * len
  const rowText = (y: number, a: number, b: number) => { let n = 0; for (let x = a; x < b; x++) n += m[y * W + x]; return isText(n, b - a) ? n : 0 }
  const colText = (x: number, a: number, b: number) => { let n = 0; for (let y = a; y < b; y++) n += m[y * W + x]; return isText(n, b - a) ? n : 0 }
  // grow out of any text the box edge cuts through, then take up to 16 px of clear space
  let top = Math.floor(box.y), bot = Math.ceil(box.y + box.h)
  for (let k = 0; k < 40 && top > 0 && rowText(top - 1, x0, x1); k++) top--
  for (let k = 0; k < 40 && bot < H && rowText(bot, x0, x1); k++) bot++
  // clear space only: stop at any ink, including another card's border
  const rowInk = (y: number, a: number, b: number) => { let n = 0; for (let x = a; x < b; x++) n += m[y * W + x]; return n > 3 }
  const colInk = (x: number, a: number, b: number) => { let n = 0; for (let y = a; y < b; y++) n += m[y * W + x]; return n > 3 }
  for (let k = 0; k < 10 && top > 0 && !rowInk(top - 1, x0, x1); k++) top--
  for (let k = 0; k < 10 && bot < H && !rowInk(bot, x0, x1); k++) bot++
  const col = (x: number) => { for (let y = top; y < bot; y++) if (m[y * W + x]) return true; return false }
  let a = Math.floor(box.x), b = Math.ceil(box.x + box.w) - 1
  while (a < b && !col(a)) a++
  while (b > a && !col(b)) b--
  let left = a, right = b + 1
  for (let k = 0; k < 40 && left > 0 && colText(left - 1, top, bot); k++) left--
  for (let k = 0; k < 40 && right < W && colText(right, top, bot); k++) right++
  for (let k = 0; k < 10 && left > 0 && !colInk(left - 1, top, bot); k++) left--
  for (let k = 0; k < 10 && right < W && !colInk(right, top, bot); k++) right++
  const crop = { x: left, y: top, w: right - left, h: bot - top }
  if (process.env.INSET_DEBUG) console.log(id, crop, 'top', rowText(crop.y, crop.x, crop.x + crop.w), 'bottom', rowText(crop.y + crop.h - 1, crop.x, crop.x + crop.w),
    'left', colText(crop.x, crop.y, crop.y + crop.h), 'right', colText(crop.x + crop.w - 1, crop.y, crop.y + crop.h))
  const edgeInk = rowText(crop.y, crop.x, crop.x + crop.w) + rowText(crop.y + crop.h - 1, crop.x, crop.x + crop.w)
    + colText(crop.x, crop.y, crop.y + crop.h) + colText(crop.x + crop.w - 1, crop.y, crop.y + crop.h)
  // 2.5x of the row's own bounds, less only if the card would not fit the frame (1640 × 640 px)
  const scale = +Math.min(2.5, 1640 / crop.w, 640 / crop.h).toFixed(3)
  return { crop, scale, edgeInk }
}
// Text pixels along a crop's four edges (0 = every edge sits on empty pixels or a border line).
function edgeInkOf(id: string, crop: Box) {
  const { m, W } = ink(id)
  const text = (n: number, len: number) => n > 3 && n < 0.8 * len ? n : 0
  const row = (y: number) => { let n = 0; for (let x = crop.x; x < crop.x + crop.w; x++) n += m[y * W + x]; return text(n, crop.w) }
  const col = (x: number) => { let n = 0; for (let y = crop.y; y < crop.y + crop.h; y++) n += m[y * W + x]; return text(n, crop.h) }
  return row(crop.y) + row(crop.y + crop.h - 1) + col(crop.x) + col(crop.x + crop.w - 1)
}
const boxOf = (id: string, b: string | number[]): Box => {
  if (Array.isArray(b)) return { x: b[0], y: b[1], w: b[2], h: b[3] }
  const box = shotMeta(id).boxes[b]
  if (!box) throw new Error(`${id}: no box ${b}`)
  return box
}
// When the footage changes: mpdecimate keeps a frame only if it differs from the last kept one.
const activityCache = new Map<string, number[]>()
function activity(clip: string) {
  if (!activityCache.has(clip)) {
    const log = spawnSync(FFMPEG, ['-nostdin', '-hide_banner', '-nostats', '-i', path.join(ROOT, 'capture/clips', clip), '-vf', 'mpdecimate,showinfo', '-f', 'null', '-'],
      { encoding: 'utf8', maxBuffer: 1 << 28 }).stderr
    activityCache.set(clip, [...String(log).matchAll(/pts_time:([\d.]+)/g)].map(m => Number(m[1])))
  }
  return activityCache.get(clip)!
}
// Time-lapse [c0, c1] of a clip into `out` frames: spans where the app changes play near 1×, idle waits are squeezed hard,
// so the lapse never shows a frozen app. Returns pieces (scene frames) with each span's own rate.
function lapse(clip: string, c0: number, c1: number, a0: number, out: number) {
  const kept = activity(clip).filter(t => t >= c0 && t <= c1)
  const spans: { s: number; e: number; active: boolean }[] = []
  let cur = c0
  for (const t of kept) {
    const s = Math.max(cur, t - 0.12), e = Math.min(c1, t + 0.25)
    if (s > cur + 1e-3) spans.push({ s: cur, e: s, active: false })
    if (e > s) { const last = spans.at(-1); if (last?.active && last.e >= s - 1e-3) last.e = e; else spans.push({ s, e, active: true }) }
    cur = Math.max(cur, e)
  }
  if (c1 > cur + 1e-3) spans.push({ s: cur, e: c1, active: false })
  // output seconds per span: active at 1×, idle at a fixed share; then scale everything to fit `out`
  const target = out / FPS
  let idleEach = 0.5
  const outLen = (sp: typeof spans[number]) => sp.active ? sp.e - sp.s : Math.min(sp.e - sp.s, idleEach)
  const activeTotal = spans.filter(s => s.active).reduce((n, s) => n + s.e - s.s, 0), idle = spans.filter(s => !s.active)
  if (idle.length) idleEach = Math.max(0.15, Math.min(0.5, (target - activeTotal) / idle.length)) // ≤ 0.5 s per idle wait
  const total = spans.reduce((n, s) => n + outLen(s), 0), k = target / total
  const pieces: { from: number; len: number; clip: number; rate: number }[] = []
  let a = a0
  spans.forEach((sp, i) => {
    const n = i === spans.length - 1 ? a0 + out - a : Math.max(1, Math.round(outLen(sp) * k * FPS))
    if (n > 0) pieces.push({ from: a, len: n, clip: sp.s, rate: (sp.e - sp.s) / (n / FPS) })
    a += n
  })
  return pieces
}

// Clip use → pieces on the scene timeline. Anchors pin a clip moment (seconds or a capture mark) to a spoken cue; between
// anchors the clip plays at 1× and holds briefly if the voice runs longer, or time-lapses (with a chip) if it runs shorter.
function clipPieces(use: { id: string; anchors: [number | string, number | string][]; until: number; stop?: number }, until: number, frames: number) {
  const meta = JSON.parse(fs.readFileSync(path.join(ROOT, 'capture', `${use.id}.marks.json`), 'utf8'))
  const at = (c: number | string) => typeof c === 'number' ? c : meta.marks.find((m: { id: string }) => m.id === c)?.t ?? (() => { throw new Error(`${use.id}: no mark ${c}`) })()
  const pts = use.anchors.map(([c, a]) => ({ c: at(c), a: typeof a === 'string' && a.startsWith('end-') ? frames - f(Number(a.slice(4))) : Number(a) }))
  const pieces: { from: number; len: number; clip: number; rate: number }[] = [], chips: { from: number; to: number; text: string }[] = []
  const lapses: { c0: number; c1: number; a0: number; a1: number }[] = []
  const stop = Math.min(use.stop ?? meta.duration, meta.duration) - 1 / FPS
  const add = (a: number, n: number, clip: number, rate: number) => { if (n > 0) pieces.push({ from: a, len: n, clip: Math.min(clip, stop), rate }) }
  for (let i = 0; i < pts.length; i++) {
    const { c, a } = pts[i], next = pts[i + 1]
    const A = (next ? next.a : until) - a
    if (A <= 0) continue
    if (!next) { const play = Math.max(0, Math.min(A, f(stop - c))); add(a, play, c, 1); add(a + play, A - play, c + play / FPS, 0); break }
    const C = f(next.c - c)
    if (C <= A * 1.05) { const n = Math.min(A, C); add(a, n, c, 1); add(a + n, A - n, next.c, 0) } // within 5% of 1×: play at 1×, trim the rest
    else { for (const p of lapse(meta.clip, c, next.c, a, A)) pieces.push(p); lapses.push({ c0: c, c1: next.c, a0: a, a1: a + A }) }
  }
  // one chip per time-lapse: every lapse in this clip use becomes one chip with one speed (clip time ÷ screen time)
  if (lapses.length) {
    const a0 = lapses[0].a0, a1 = lapses.at(-1)!.a1, r = (lapses.at(-1)!.c1 - lapses[0].c0) / ((a1 - a0) / FPS)
    chips.push({ from: a0, to: a1, text: `${r < 10 ? Math.round(r * 10) / 10 : Math.round(r)}×` })
  }
  link(meta.clip, path.join(ROOT, 'capture/clips', meta.clip))
  // the pointer, from the mouse positions logged during capture (the real cursor was hidden)
  const input = JSON.parse(fs.readFileSync(path.join(ROOT, 'capture', `${use.id}.input.json`), 'utf8'))
  const moves = input.events.filter((e: { type: string }) => e.type === 'move').map((e: { t: number; x: number; y: number }) => [+e.t.toFixed(3), +e.x.toFixed(1), +e.y.toFixed(1)])
  const downs = input.events.filter((e: { type: string }) => e.type === 'down').map((e: { t: number }) => +e.t.toFixed(3))
  return { id: use.id, clip: meta.clip, pieces, chips, marks: meta.marks, cursor: { moves, downs } }
}
/** The first scene frame at which a clip use shows clip time `t` or later. */
function clipFrame(pieces: { from: number; len: number; clip: number; rate: number }[], t: number) {
  for (const p of pieces) if (t <= p.clip + (p.len / FPS) * p.rate + 1e-6) return p.from + (p.rate && t > p.clip ? Math.ceil(((t - p.clip) / p.rate) * FPS) : 0)
  throw new Error(`clip time ${t} is past the clip use`)
}
const link = (file: string, src: string) => { fs.rmSync(path.join(STAGE, file), { force: true }); fs.linkSync(src, path.join(STAGE, file)) }

fs.mkdirSync(STAGE, { recursive: true })
const clipBox = (id: string, mark: string): Box => {
  const m = JSON.parse(fs.readFileSync(path.join(ROOT, 'capture', `${id}.marks.json`), 'utf8')).marks.find((x: { id: string }) => x.id === mark)
  if (!m?.box) throw new Error(`${id}: no box for mark ${mark}`)
  return { x: m.box.x * 1440, y: m.box.y * 900, w: m.box.w * 1440, h: m.box.h * 900 } // CSS px of the 1440×900 view
}
const union = (bs: Box[]): Box => {
  const x0 = Math.min(...bs.map(b => b.x)), y0 = Math.min(...bs.map(b => b.y))
  const x1 = Math.max(...bs.map(b => b.x + b.w)), y1 = Math.max(...bs.map(b => b.y + b.h))
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }
}
const scenes = []
const srt: string[] = []
const stamp = (s: number) => new Date(Math.round(s * 1000)).toISOString().slice(11, 23).replace('.', ',')
const clock = (fr: number) => `${Math.floor(fr / FPS / 60)}:${(fr / FPS % 60).toFixed(1).padStart(4, '0')}`
// whisper's spellings of the product names, put right in the captions
const fixNames = (t: string) => Object.entries(script.caption_fix as Record<string, string>).reduce((x, [re, name]) => x.replace(new RegExp(`\\b(${re})\\b`, 'gi'), name), t)
const lines: { scene: string; name: string; words: { w: string; at: number }[]; vo: string[] }[] = [] // the teleprompter, global frames
let start = 0
for (const raw of script.segments) {
  const tm = timing[raw.id]
  if (!tm) throw new Error(`${raw.id}: no timing; run script/vo.py`)
  const words: Word[] = tm.words
  const off = f(raw.vo_offset_s ?? 0) // the voiceover starts after a silent product lead-in
  const seg = resolve(raw, words, raw.id, off) as Record<string, any>
  const frames = off + f(tm.duration + (seg.pad_s ?? PAD_S))
  const end = (v: unknown) => v === 'end' ? frames + 100 : v
  const shots = new Set<string>([seg.shot, seg.page?.shot, ...(seg.steps ?? []).map((x: { shot: string }) => x.shot)].filter(Boolean))
  const checkCrop = (id: string, crop: Box, what: string) => { const n = edgeInkOf(id, crop); if (n) console.warn(`${seg.id}: ${what} ${id} crop edge touches ink (${n} px)`); return n }
  if (seg.page) { seg.page.crop = boxOf(seg.page.shot, seg.page.crop); seg.page.edgeInk = checkCrop(seg.page.shot, seg.page.crop, 'page') }
  if (seg.lead?.crop) seg.lead.crop = boxOf('', seg.lead.crop)
  for (const c of seg.crops ?? []) { shots.add(c.shot); c.crop = boxOf(c.shot, c.crop); c.edgeInk = checkCrop(c.shot, c.crop, 'matrix') }
  for (const pg of seg.pages ?? []) {
    if (pg.shot) { shots.add(pg.shot); pg.crop = boxOf(pg.shot, pg.crop); pg.edgeInk = checkCrop(pg.shot, pg.crop, 'memo') }
    else link(`${pg.doc}.png`, path.join(ROOT, 'shots/docs', `${pg.doc}.png`))
  }
  for (const ins of seg.insets ?? []) {
    shots.add(ins.shot)
    const name = String(ins.box), box = union(name.split('+').map((b) => boxOf(ins.shot, b)))
    Object.assign(ins, { box, out: end(ins.out), ...inset(ins.shot, box) })
    if (ins.edgeInk) console.warn(`${seg.id}: inset ${ins.shot}/${name} crop edge touches ink (${ins.edgeInk} px)`)
  }
  // a highlight on a clip mark stays inside the region that holds it (a table row can run past its scroll box)
  const clamp = (b: Box, r: Box): Box => { const x = Math.max(b.x, r.x), y = Math.max(b.y, r.y); return { x, y, w: Math.min(b.x + b.w, r.x + r.w) - x, h: Math.min(b.y + b.h, r.y + r.h) - y } }
  for (const h of seg.highlights ?? []) Object.assign(h, h.clip ? {
    box: h.box ? boxOf('', h.box) : h.within ? clamp(clipBox(h.clip, h.mark), clipBox(h.clip, h.within)) : clipBox(h.clip, h.mark) } : { out: end(h.out), box: boxOf(h.shot, h.box) })
  if (seg.zoom) seg.zoom.box = clipBox(seg.zoom.clip, seg.zoom.mark)
  if (seg.type === 'gate') { // the cited quote on the real PDF page (a 4x screenshot), tight enough to read at 1080p
    const m = boxOf(seg.shot, seg.box)
    seg.quote = m
    seg.crop = { x: Math.round(m.x - 64), y: Math.round(m.y - 36), w: Math.round(m.w + 128), h: Math.round(m.h + 52) }
    checkCrop(seg.shot, seg.crop, 'quote')
  }
  if (seg.type === 'trace') {
    const meta = shotMeta(seg.shot)
    // the call list is taller than the frame: show it at 2.1x in a window that pans down it
    const u = union([meta.boxes.line, meta.boxes.table])
    seg.inset = { shot: seg.shot, at: seg.cues.rows, crop: { x: u.x - 12, y: u.y - 12, w: u.w + 24, h: u.h + 24 }, scale: 2.1, window: 790 }
  }
  for (const id of shots) link(`${id}.png`, path.join(ROOT, 'shots', `${id}.png`))
  for (const u of seg.clips ?? []) Object.assign(u, clipPieces(u, u.until === 'end' ? frames : u.until, frames))
  if (seg.lead) Object.assign(seg.lead, clipPieces(seg.lead, seg.lead.until, frames))
  // a box on a clip lives in clip time: on from the moment its element is in place (`from`) until it moves or goes (`to`),
  // given as clip seconds or capture marks, mapped through the clip's pieces to scene frames
  for (const h of (seg.highlights ?? []).filter((x: { clip?: string }) => x.clip)) {
    const u = seg.lead, t = (v: number | string) => typeof v === 'number' ? v : u.marks.find((m: { id: string }) => m.id === v).t
    h.at = Math.max(clipFrame(u.pieces, t(h.from)), h.at ?? 0) // never before its spoken cue, if it has one
    // 'until': while the clip is up, and gone before the first inset covers the frame
    h.out = h.to === 'until' ? Math.min(u.until, ...(seg.insets ?? []).map((i: { at: number }) => i.at)) : clipFrame(u.pieces, t(h.to))
  }
  if (seg.type === 'context') for (const d of ['cps-07-84-00-p3', '3m-ic15wb-p1']) link(`${d}.png`, path.join(ROOT, 'shots/docs', `${d}.png`))
  const audio = tm.mode === 'vo' ? `seg${raw.id.slice(3)}.wav` : undefined // guide timing has no audio
  if (audio) link(audio, path.join(ROOT, 'audio', audio))
  scenes.push({ ...seg, frames, audio, audioAt: off, voEnd: off + f(tm.duration) })
  const at = words.map((w) => ({ w: w.w, at: start + off + f(w.start) }))
  if (lines.at(-1)?.scene === raw.scene) { lines.at(-1)!.words.push(...at); lines.at(-1)!.vo.push(raw.vo) }
  else lines.push({ scene: raw.scene, name: raw.name, words: at, vo: [raw.vo] })
  // YouTube captions from the words actually said (the script words in guide timing), on the global timeline
  const said: Word[] = tm.heard ?? words
  const phrases: Word[][] = [[]]
  for (const w of said) { phrases.at(-1)!.push(w); if (/[.,:;!?]$/.test(w.w) && phrases.at(-1)!.map(x => x.w).join(' ').length > 18) phrases.push([]) }
  for (const p of phrases.filter(p => p.length))
    srt.push(`${srt.length + 1}\n${stamp((start + off) / FPS + p[0].start)} --> ${stamp((start + off) / FPS + p.at(-1)!.end + 0.2)}\n${fixNames(p.map(w => w.w).join(' '))}\n`)
  start += frames - FADE
}
const total = start + FADE
const outcome = shotMeta('outcome-c07')
link('outcome-c07.png', path.join(ROOT, 'shots', 'outcome-c07.png'))
const voMode = Object.values(timing).some((t: any) => t.mode === 'vo')
if (voMode) link('roomtone.wav', path.join(ROOT, 'audio/roomtone.wav')) // a −60 dB bed sampled from the take, under every pause
// Thumbnail: the alert card from its title through the manufacturer's quote (the alternates box below stays out).
const { alert, quote } = outcome.boxes
const data = { fps: FPS, fade: FADE, frames: total, scenes, base_url: script.base_url, repo: script.repo, event: script.event, vo: voMode,
  prompter: lines.map((l) => ({ scene: l.scene, name: l.name, words: l.words })),
  thumb: { image: 'outcome-c07.png', box: { ...alert, h: quote.y + quote.h + 10 - alert.y }, view: outcome.view } }
fs.writeFileSync(path.join(STAGE, 'data.json'), JSON.stringify(data, null, 1))
fs.writeFileSync(path.join(ROOT, 'out/captions.srt'), srt.join('\n'))
if (!voMode) { // the recording script: one line per scene, where it starts in the cut, and its length at the script's pace
  const rows = lines.map((l) => {
    const n = l.vo.join(' ').split(/\s+/).length
    return `| ${l.scene} | ${l.name} | ${clock(l.words[0].at)} | ${(n * 60 / script.wpm + script.line_pad_s).toFixed(1)} s | ${l.vo.join(' ')} |`
  })
  const words = lines.reduce((n, l) => n + l.vo.join(' ').split(/\s+/).length, 0)
  const extra = total / FPS - (words * 60) / script.wpm // lead-ins, pads and fades, which stay at any pace
  const pace = Math.ceil((words * 60) / (150 - extra))
  fs.writeFileSync(path.join(ROOT, 'VO_SCRIPT.md'), `# SpecCheck voiceover script

Read one take while \`out/speccheck-guide.mp4\` plays; the teleprompter band shows each line and lights each word at
${script.wpm} wpm. The guide opens with a 3-second countdown; the start times below are positions in the cut (add 3 s on the
guide). Save the take as \`video/audio/vo.wav\` and run \`./render.sh\`; it finds each line in your take and fits the scenes
to your timing, so pace and small wording changes are fine. Keep the numbers and facts as written.

Target duration = words at ${script.wpm} wpm + ${script.line_pad_s} s. ${words} words; the cut is ${clock(total)} at this pace.
To land at or under 2:30, read at about ${pace} wpm (the ${extra.toFixed(0)} s of lead-ins and pauses between lines stay fixed).

| Scene | What's on screen | Starts at | Target | Line |
| --- | --- | --- | --- | --- |
${rows.join('\n')}
`)
}
console.log(`plan: ${(total / FPS).toFixed(2)} s at ${FPS} fps, ${scenes.length} scenes, ${voMode ? "Kyle's take" : 'guide timing (no audio)'}`)
for (const s of scenes) console.log(`${s.id} ${s.type} ${(s.frames / FPS).toFixed(1)} s${(s.insets ?? []).map((i: { crop: Box; scale: number }) => ` · inset ${i.crop.w}×${i.crop.h} at ${i.scale}x`).join('')}${(s.clips ?? []).concat(s.lead ? [s.lead] : []).flatMap((u: { chips: { text: string }[] }) => u.chips).map((c: { text: string }) => ` · lapse ${c.text}`).join('')}`)
