// Scenes. Product moments are real 60 fps clips of the app; findings are real 2x screenshots with insets. Remotion only
// draws titles, overlays, insets, highlights, diagrams and number cards; the one score comes from the official run's scores.json.
import { evolvePath, getLength, getPointAtLength } from '@remotion/paths'
import { AbsoluteFill, Freeze, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig } from 'remotion'
import { lin, Logo, ramp, Rise, Shot, Stamp, useIn, useRamp, Words, type Box } from './anim'
import { C, mono, sans } from './theme'

type Cues = Record<string, number>
type Piece = { from: number; len: number; clip: number; rate: number }
type ClipUse = { id: string; clip: string; label?: string; crop?: Box; pieces: Piece[]; chips: { from: number; to: number; text: string }[]
  marks: { id: string; t: number; box?: Box }[]; cursor?: { moves: [number, number, number][]; downs: number[] } }
type Mark = { at: number; out: number; box: Box; shot?: string; clip?: string }
type InsetSpec = { shot: string; box: Box; crop: Box; scale: number; at: number; out: number; slot?: number; caption?: string }
export type Scene = Record<string, any> & { id: string; type: string; frames: number; voEnd: number; audioAt: number; cues?: Cues }

const sec = (fps: number, s: number) => Math.round(s * fps)
const W = 1440, H = 900 // CSS px of every capture

// ---------- clips ----------
/** A clip's pieces on the scene timeline: 1× play, short holds (frozen frame) and labelled time-lapses. */
function ClipVideo({ use, width }: { use: ClipUse; width: number }) {
  const { fps } = useVideoConfig()
  const style = { position: 'absolute' as const, width, height: (width * H) / W }
  return <>{use.pieces.map((p, i) => (
    <Sequence key={i} from={p.from} durationInFrames={p.len} layout="none">
      {p.rate
        ? <OffthreadVideo src={staticFile(use.clip)} trimBefore={Math.round(p.clip * fps)} playbackRate={p.rate} muted style={style} />
        : <Freeze frame={0}><OffthreadVideo src={staticFile(use.clip)} trimBefore={Math.round(p.clip * fps)} muted style={style} /></Freeze>}
    </Sequence>
  ))}</>
}
const Bar = () => (
  <div style={{ height: 22, display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 14, background: '#15171c', borderBottom: '1px solid rgba(255,255,255,.06)' }}>
    {[0, 1, 2].map((i) => <span key={i} style={{ width: 10, height: 10, borderRadius: 5, background: '#2c3038' }} />)}
  </div>
)
const onAt = (u: ClipUse, frame: number) => u.pieces.some((p) => frame >= p.from && frame < p.from + p.len)
/** Clips in the browser frame, one after another, optionally cropped to a CSS-px region of the capture; one push-in at
 * most (≤ 1.35×); the time-lapse chip sits above the frame's top-right corner, outside the footage. */
function ClipFrame({ uses, width, zoom, marks = [], crop = { x: 0, y: 0, w: W, h: H } }: { uses: ClipUse[]; width: number; zoom?: { at: number; box: Box }
  marks?: Mark[]; crop?: Box }) {
  const frame = useCurrentFrame()
  const k = width / crop.w, h = crop.h * k
  const z = useIn(zoom?.at ?? 1e9)
  const s = 1 + 0.35 * z
  const ox = zoom ? (zoom.box.x + zoom.box.w / 2 - crop.x) * k : width / 2, oy = zoom ? (zoom.box.y + zoom.box.h / 2 - crop.y) * k : h / 2
  const chip = uses.flatMap((u) => u.chips).find((c) => frame >= c.from && frame < c.to)
  return (
    <div style={{ position: 'relative', width }}>
      {chip && <Chip {...chip} />}
      <div style={{ width, borderRadius: 16, overflow: 'hidden', border: '1px solid rgba(255,255,255,.10)', background: C.page, boxShadow: '0 30px 80px rgba(0,0,0,.55)' }}>
        <Bar />
        <div style={{ position: 'relative', width, height: h, overflow: 'hidden' }}>
          <div style={{ position: 'absolute', inset: 0, scale: `${s}`, transformOrigin: `${ox}px ${oy}px` }}>
            <div style={{ position: 'absolute', left: -crop.x * k, top: -crop.y * k, width: W * k, height: H * k }}>
              {uses.map((u) => <ClipVideo key={u.id + u.pieces[0]?.from} use={u} width={W * k} />)}
              {uses.map((u) => <Pointer key={`p${u.id}${u.pieces[0]?.from}`} use={u} k={k} />)}
              {marks.map((m, i) => <Highlight key={i} {...m} k={k} bounds={crop} />)}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
/** The pointer at the logged mouse position for the clip moment on screen (the real cursor was hidden in capture). */
function Pointer({ use, k }: { use: ClipUse; k: number }) {
  const frame = useCurrentFrame(), { fps } = useVideoConfig()
  const p = use.pieces.find((q) => frame >= q.from && frame < q.from + q.len)
  const m = use.cursor?.moves ?? []
  if (!p || !m.length) return null
  const t = p.clip + ((frame - p.from) / fps) * p.rate
  let i = m.findIndex((x) => x[0] > t)
  if (i === -1) i = m.length
  const [x, y] = i === 0 ? [m[0][1], m[0][2]] : i === m.length ? [m.at(-1)![1], m.at(-1)![2]] : (() => {
    const [t0, x0, y0] = m[i - 1], [t1, x1, y1] = m[i], f = (t - t0) / Math.max(1e-6, t1 - t0)
    return [x0 + (x1 - x0) * f, y0 + (y1 - y0) * f]
  })()
  const click = (use.cursor?.downs ?? []).map((d) => t - d).find((d) => d >= 0 && d < 0.45)
  return (
    <>
      {click !== undefined && <div style={{ position: 'absolute', left: x * k - (10 + click * 80), top: y * k - (10 + click * 80), width: 2 * (10 + click * 80), height: 2 * (10 + click * 80),
        borderRadius: '50%', border: `3px solid ${C.flare}`, opacity: 0.8 * (1 - click / 0.45) }} />}
      <svg style={{ position: 'absolute', left: x * k - 3, top: y * k - 2, filter: 'drop-shadow(0 2px 4px rgba(0,0,0,.5))' }} width={30} height={38} viewBox="0 0 28 36">
        <path d="M2 1 L2 27 L8.5 21 L12.6 31 L17 29.2 L12.9 19.4 L21.5 19.4 Z" fill="#111" stroke="#fff" strokeWidth={2} strokeLinejoin="round" />
      </svg>
    </>
  )
}
function Chip({ from, to, text }: { from: number; to: number; text: string }) {
  const frame = useCurrentFrame()
  const o = lin(frame, from, from + 8) * (1 - lin(frame, to - 8, to))
  return (
    <div style={{ position: 'absolute', right: 0, top: -58, opacity: o, display: 'flex', alignItems: 'center', gap: 10, fontFamily: mono, fontSize: 30, color: C.ink,
      background: 'rgba(17,19,23,.9)', border: `1px solid ${C.edge}`, borderRadius: 999, padding: '8px 22px', boxShadow: '0 8px 22px rgba(0,0,0,.45)' }}>
      <svg width={26} height={18} viewBox="0 0 22 16"><path d="M1 1 L10 8 L1 15 Z M11 1 L20 8 L11 15 Z" fill={C.flare} /></svg>{text}
    </div>
  )
}
/** Where the footage came from: the live app, or the app's replay of the official recorded run. */
function Source({ text, style }: { text: string; style?: React.CSSProperties }) {
  const live = /^live/i.test(text)
  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 12, fontFamily: sans, fontSize: 28, fontWeight: 500, color: C.soft, background: C.panel,
      border: `1px solid ${C.edge}`, borderRadius: 999, padding: '6px 20px', whiteSpace: 'nowrap', ...style }}>
      <span style={{ width: 12, height: 12, borderRadius: 6, background: live ? C.bad : C.muted, boxShadow: live ? `0 0 10px ${C.bad}` : 'none' }} />{text}
    </div>
  )
}
/** The label of whichever clip is on screen, crossfading when it changes. */
function ClipSource({ uses, style }: { uses: ClipUse[]; style?: React.CSSProperties }) {
  const frame = useCurrentFrame()
  return <>{uses.map((u, i) => {
    const a = u.pieces[0].from, b = u.pieces.at(-1)!.from + u.pieces.at(-1)!.len
    const o = lin(frame, a, a + 8) * (i < uses.length - 1 ? 1 - lin(frame, b - 8, b) : 1)
    return u.label ? <div key={i} style={{ position: 'absolute', opacity: o, ...style }}><Source text={u.label} /></div> : null
  })}</>
}

/** HIGHLIGHT: an orange 3 px rounded box 8 px outside the target's box (CSS px of the capture, scaled by k), kept inside the
 * visible region `bounds`; fades in over 8 frames from `at` and is gone by `out`. */
function Highlight({ at, out, box, k, bounds }: Mark & { k: number; bounds: Box }) {
  const frame = useCurrentFrame()
  const o = lin(frame, at, at + 8) * (1 - lin(frame, out - 8, out))
  if (o <= 0) return null
  const pad = 8, x0 = Math.max(box.x * k - pad, bounds.x * k + 2), y0 = Math.max(box.y * k - pad, bounds.y * k + 2)
  const x1 = Math.min((box.x + box.w) * k + pad, (bounds.x + bounds.w) * k - 2), y1 = Math.min((box.y + box.h) * k + pad, (bounds.y + bounds.h) * k - 2)
  return <div style={{ position: 'absolute', left: x0, top: y0, width: x1 - x0, height: y1 - y0, boxSizing: 'border-box',
    border: `3px solid ${C.flare}`, borderRadius: 10, opacity: o, boxShadow: '0 0 18px rgba(245,121,26,.45)' }} />
}

/** INSET: a crop of a 2x screenshot springing in at its own scale, over the dimmed screenshot. */
function Inset({ s, left, top }: { s: InsetSpec; left: number; top: number }) {
  const frame = useCurrentFrame()
  const k = ramp(frame, s.at), o = k * (1 - lin(frame, s.out - 8, s.out))
  if (o <= 0) return null
  const w = s.crop.w * s.scale, h = s.crop.h * s.scale
  return (
    <div style={{ position: 'absolute', left, top, opacity: o, translate: `0px ${(1 - k) * 8}px` }}>
      {s.caption && <div style={{ position: 'absolute', top: -46, fontFamily: sans, fontSize: 28, color: C.soft, whiteSpace: 'nowrap' }}>{s.caption}</div>}
      <div style={{ position: 'relative', width: w, height: h, borderRadius: 18, overflow: 'hidden', border: '1px solid rgba(255,255,255,.16)', background: C.panel,
        boxShadow: '0 40px 100px rgba(0,0,0,.7), 0 0 0 1px rgba(0,0,0,.4)' }}>
        <Img src={staticFile(`${s.shot}.png`)} style={{ position: 'absolute', left: -s.crop.x * s.scale, top: -s.crop.y * s.scale, width: W * s.scale, height: H * s.scale }} />
      </div>
    </div>
  )
}

// ---------- 1 · Title over the real Inbox ----------
export function Title({ s }: { s: Scene }) {
  const frame = useCurrentFrame()
  const drift = 1.02 + 0.03 * lin(frame, 0, s.frames)
  return (
    <AbsoluteFill style={{ background: C.page }}>
      <div style={{ position: 'absolute', left: 240, top: 79, scale: `${drift}` }}><Shot id={s.shot} width={1440} /></div>
      <AbsoluteFill style={{ background: C.page, opacity: 0.78 }} />
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', gap: 40 }}>
        <Logo at={2} size={132} />
        <Words size={46} weight={500} color={C.soft} words={s.tag} />
        <Rise at={s.send} style={{ fontFamily: sans, fontSize: 46, fontWeight: 600, color: C.flare }}>…and says what to send instead.</Rise>
      </AbsoluteFill>
    </AbsoluteFill>
  )
}

// ---------- 2 · What a submittal is: the spec, the data sheet, the round trip ----------
// One centered block per phase, inside 96 px side and 80 px top/bottom margins after the 1.04 camera push.
const PAGE = { w: 500, h: 647, top: 173, gap: 360 }
const BOX = { w: 440, h: 140, gap: 160, y: 659 } // the three roles, centered
const ROLES = [{ t: 'Subcontractor', cue: 'roles' }, { t: 'General contractor', cue: 'role1' }, { t: 'Architect', cue: 'role2' }]
  .map((r, i) => ({ ...r, x: 960 + (i - 1) * (BOX.w + BOX.gap) }))
const ICON = { w: 100, h: 128, top: 511 } // the submittal travels in a lane above the boxes, its label above it
const DOC = { x: ROLES[0].x, y: ICON.top + ICON.h / 2 }
const BACK = `M ${ROLES[2].x} ${BOX.y + BOX.h + 14} C ${ROLES[2].x} ${BOX.y + BOX.h + 134}, ${ROLES[0].x} ${BOX.y + BOX.h + 134}, ${ROLES[0].x} ${BOX.y + BOX.h + 14}`

function DrawPath({ d, at, len, color = C.edge, width = 5, head = true }: { d: string; at: number; len: number; color?: string; width?: number; head?: boolean }) {
  const frame = useCurrentFrame()
  const p = lin(frame, at, at + len)
  if (p <= 0) return null
  const ev = evolvePath(p, d)
  const L = getLength(d), end = getPointAtLength(d, L * p), before = getPointAtLength(d, Math.max(0, L * p - 1))
  const ang = (Math.atan2(end.y - before.y, end.x - before.x) * 180) / Math.PI
  return (
    <g>
      <path d={d} stroke={color} strokeWidth={width} fill="none" strokeLinecap="round" strokeDasharray={ev.strokeDasharray} strokeDashoffset={ev.strokeDashoffset} />
      {head && <path d="M -18 -12 L 0 0 L -18 12" stroke={color} strokeWidth={width} fill="none" strokeLinecap="round" strokeLinejoin="round" transform={`translate(${end.x} ${end.y}) rotate(${ang})`} />}
    </g>
  )
}
function Page({ src, x, at, label, labelAt, shrink, out }: { src: string; x: number; at: number; label: string; labelAt: number; shrink: number; out: number }) {
  const frame = useCurrentFrame()
  const k = useRamp(at)
  const cx = x + PAGE.w / 2, cy = PAGE.top + PAGE.h / 2
  const tx = (DOC.x - cx) * shrink, ty = (DOC.y - cy) * shrink, sc = (1 - 0.8 * shrink) * (1 + 0.02 * lin(frame, at, at + 600))
  return (
    <>
      <div style={{ position: 'absolute', left: x, top: PAGE.top, width: PAGE.w, height: PAGE.h, opacity: k * (1 - lin(shrink, 0.6, 1)), translate: `${tx}px ${ty + (1 - k) * 8}px`,
        scale: `${sc}`, borderRadius: 10, overflow: 'hidden', background: '#fff', boxShadow: '0 30px 80px rgba(0,0,0,.6)' }}>
        <Img src={staticFile(`${src}.png`)} style={{ width: PAGE.w, height: PAGE.h }} />
      </div>
      <div style={{ opacity: out }}>
        <Rise at={labelAt} style={{ position: 'absolute', left: x - 60, width: PAGE.w + 120, top: PAGE.top + PAGE.h + 26, textAlign: 'center', fontFamily: sans, fontSize: 48,
          fontWeight: 650, color: C.ink }}>{label}</Rise>
      </div>
    </>
  )
}
export function Context({ s }: { s: Scene }) {
  const frame = useCurrentFrame(), { fps } = useVideoConfig()
  const c = s.cues!
  const shrink = useIn(c.shrink)
  // the submittal goes out above the boxes, then comes back along the same lane while the red arrow draws below them
  const travel = lin(frame, c.travel, c.travel + (c.role2 - c.travel) + 20), back = lin(frame, c.back + 8, c.back + 8 + sec(fps, 0.9))
  const docX = frame < c.back + 8 ? ROLES[0].x + (ROLES[2].x - ROLES[0].x) * travel : ROLES[2].x + (ROLES[0].x - ROLES[2].x) * back
  const docK = useRamp(c.doc + 10)
  const arrowOut = 1 - lin(frame, c.shrink, c.shrink + 8) // labels and arrows leave with an 8-frame fade as the pages shrink
  const mid = PAGE.top + PAGE.h / 2
  return (
    <AbsoluteFill style={{ background: C.page }}>
      <Page src="cps-07-84-00-p3" x={960 - PAGE.gap / 2 - PAGE.w} at={c.spec} label="The spec" labelAt={c.specLabel} shrink={shrink} out={arrowOut} />
      <Page src="3m-ic15wb-p1" x={960 + PAGE.gap / 2} at={c.product} label="The submittal" labelAt={c.productLabel} shrink={shrink} out={arrowOut} />
      <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0, opacity: arrowOut }}>
        <DrawPath d={`M ${960 - 150} ${mid - 22} L ${960 + 150} ${mid - 22}`} at={c.arrow} len={sec(fps, 0.5)} color={C.flare} width={6} />
        <DrawPath d={`M ${960 + 150} ${mid + 28} L ${960 - 150} ${mid + 28}`} at={c.arrow + 10} len={sec(fps, 0.5)} color={C.flare} width={6} />
      </svg>
      <div style={{ opacity: arrowOut }}>
        <Rise at={c.match} style={{ position: 'absolute', left: 960 - PAGE.gap / 2, width: PAGE.gap, top: mid - 100, textAlign: 'center', fontFamily: sans, fontSize: 44, fontWeight: 700, color: C.flare }}>Must match</Rise>
      </div>
      {ROLES.map((r) => (
        <Rise key={r.t} at={c[r.cue]} style={{ position: 'absolute', left: r.x - BOX.w / 2, top: BOX.y, width: BOX.w, height: BOX.h }}>
          <div style={{ width: BOX.w, height: BOX.h, boxSizing: 'border-box', borderRadius: 20, background: C.panel, border: `2px solid ${C.edge}`, display: 'flex', alignItems: 'center',
            justifyContent: 'center', fontFamily: sans, fontSize: 40, fontWeight: 600, color: C.ink }}>{r.t}</div>
        </Rise>
      ))}
      <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
        <DrawPath d={`M ${ROLES[0].x + BOX.w / 2 + 14} ${BOX.y + BOX.h / 2} L ${ROLES[1].x - BOX.w / 2 - 14} ${BOX.y + BOX.h / 2}`} at={c.role1 - 12} len={sec(fps, 0.5)} />
        <DrawPath d={`M ${ROLES[1].x + BOX.w / 2 + 14} ${BOX.y + BOX.h / 2} L ${ROLES[2].x - BOX.w / 2 - 14} ${BOX.y + BOX.h / 2}`} at={c.role2 - 12} len={sec(fps, 0.5)} />
        <DrawPath d={BACK} at={c.back} len={sec(fps, 0.9)} color={C.bad} width={6} />
      </svg>
      {docK > 0 && <div style={{ position: 'absolute', left: docX - ICON.w / 2, top: ICON.top, width: ICON.w, height: ICON.h, opacity: docK }}>
        <div style={{ width: ICON.w, height: ICON.h, borderRadius: 10, background: '#e9e7e2', boxShadow: '0 12px 30px rgba(0,0,0,.5)' }}>
          {[0, 1, 2, 3, 4].map((i) => <div key={i} style={{ position: 'absolute', left: 14, top: 19 + i * 19, width: [72, 58, 69, 50, 65][i], height: 7, borderRadius: 4, background: '#b7b3aa' }} />)}
        </div>
        <div style={{ position: 'absolute', left: -80, width: 260, top: -50, textAlign: 'center', fontFamily: sans, fontSize: 34, fontWeight: 600, color: C.ink }}>Submittal</div>
      </div>}
      <div style={{ position: 'absolute', left: 0, right: 0, top: 216, display: 'flex', justifyContent: 'center' }}>
        <Stamp at={c.stamp} text="REVISE AND RESUBMIT" size={60} style={{ position: 'relative' }} />
      </div>
      <Rise at={c.weeks} style={{ position: 'absolute', left: 0, right: 0, top: 368, textAlign: 'center', fontFamily: sans, fontSize: 84, fontWeight: 800, color: C.bad }}>+ weeks</Rise>
    </AbsoluteFill>
  )
}

// ---------- 3 · The product: pipeline rail + the real scan ----------
const RAIL = { x: 76, w: 300, h: 176, gap: 38, y0: 150 }
const railY = (i: number) => RAIL.y0 + i * (RAIL.h + RAIL.gap)
const LIVE_W = 1392, LIVE_X = 448
export function Live({ s }: { s: Scene }) {
  const frame = useCurrentFrame(), { fps } = useVideoConfig()
  const nodes = s.nodes as { title: string; note?: string; at: number }[]
  const cx = RAIL.x + RAIL.w / 2
  const br = lin(frame, s.cues!.bracket, s.cues!.bracket + sec(fps, 0.6))
  const bx = RAIL.x + RAIL.w + 14
  const bracket = `M ${bx} ${railY(0) + 10} L ${bx + 18} ${railY(0) + 10} L ${bx + 18} ${railY(1) + RAIL.h - 10} L ${bx} ${railY(1) + RAIL.h - 10}`
  const ev = evolvePath(br, bracket)
  return (
    <AbsoluteFill style={{ background: C.page }}>
      <svg width={1920} height={1080} style={{ position: 'absolute', inset: 0 }}>
        {nodes.slice(1).map((n, i) => {
          const d = `M ${cx} ${railY(i) + RAIL.h + 3} L ${cx} ${railY(i + 1) - 3}`, e = evolvePath(lin(frame, nodes[i].at, nodes[i].at + 14), d)
          return <path key={n.title} d={d} stroke={C.edge} strokeWidth={3} strokeDasharray={e.strokeDasharray} strokeDashoffset={e.strokeDashoffset} />
        })}
        {br > 0 && <path d={bracket} stroke={C.flare} strokeWidth={4} fill="none" strokeDasharray={ev.strokeDasharray} strokeDashoffset={ev.strokeDashoffset} />}
      </svg>
      {nodes.map((n, i) => <RailNode key={n.title} i={i} n={n} />)}
      <Rise at={s.cues!.label} style={{ position: 'absolute', left: RAIL.x, width: RAIL.w + 40, top: 60, fontFamily: sans, fontSize: 32, fontWeight: 650, color: C.flare }}>Nebius Token Factory</Rise>
      <ClipSource uses={s.clips} style={{ left: LIVE_X, top: 50 }} />
      <div style={{ position: 'absolute', left: LIVE_X, top: 112 }}>
        <ClipFrame uses={s.clips} width={LIVE_W} />
      </div>
    </AbsoluteFill>
  )
}
function RailNode({ i, n }: { i: number; n: { title: string; note?: string; at: number } }) {
  const frame = useCurrentFrame(), { fps } = useVideoConfig()
  const lit = lin(frame, n.at, n.at + 8)
  const pulse = interpolate(frame, [n.at, n.at + 8, n.at + sec(fps, 0.7)], [0, 0.3, 0.08], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  return (
    <div style={{ position: 'absolute', left: RAIL.x, top: railY(i), width: RAIL.w, height: RAIL.h, borderRadius: 18, boxSizing: 'border-box',
      border: `2px solid ${lit > 0.5 ? C.flare : C.edge}`, background: `rgba(245,121,26,${pulse})`, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '0 22px', gap: 8 }}>
      <span style={{ fontFamily: sans, fontSize: 34, fontWeight: 650, color: lit < 0.5 ? C.muted : n.title === 'Code' ? C.flare : C.ink, lineHeight: 1.1 }}>{n.title}</span>
      {n.note && <span style={{ fontFamily: sans, fontSize: 28, color: C.soft, opacity: lit, lineHeight: 1.15 }}>{n.note}</span>}
    </div>
  )
}

// ---------- 4 · Catches: lead clip → screenshot → insets → What to send ----------
const FRAME = { x: 360, y: 236, w: 1200 } // 772 px tall: clear of the bottom edge through the camera push
function Header({ n, headline, detail }: { n?: number; headline: { text: string; at: number }; detail?: { text: string; at: number } }) {
  return <>
    {n && <Rise at={0} style={{ position: 'absolute', left: 64, top: 40 }}>
      <div style={{ fontFamily: sans, fontSize: 32, fontWeight: 600, color: C.flare, border: `3px solid ${C.flare}`, borderRadius: 999, padding: '8px 24px' }}>Catch {n} of 3</div>
    </Rise>}
    <div style={{ position: 'absolute', top: 24, width: '100%' }}>
      <Words size={76} weight={700} words={headline.text.split(' ').map((w, i) => [w, headline.at + 4 * i] as [string, number])} />
    </div>
    {detail && <div style={{ position: 'absolute', top: 128, left: 360, right: 360 }}>
      <Words size={40} weight={500} color={C.soft} words={detail.text.split(' ').map((w, i) => [w, detail.at + 4 * i] as [string, number])} />
    </div>}
  </>
}
// Normal pages (a PDF in the Review screen) sit left with the insets stacked right; a wide crop (the c07 alert) sits on
// top with its inset below. Pages are crops of the real screenshot that leave out anything the scene doesn't show.
const PAGE_AT = { x: 100, y: 244, w: 580 }, WIDE_AT = { x: 210, y: 244, w: 1500 }
const COL = { x: 760, w: 1100, top: 290, gap: 50, bottom: 1040 }
export function Catch({ s }: { s: Scene }) {
  const frame = useCurrentFrame()
  const insets = s.insets as InsetSpec[]
  const page = s.page as { shot: string; crop: Box; wide?: boolean }
  const at = page.wide ? WIDE_AT : PAGE_AT
  const k = at.w / page.crop.w
  const pageH = page.crop.h * k + 22
  const show = s.lead ? lin(frame, s.lead.until, s.lead.until + 10) : 1 // the lead clip hands over to the page
  const leadAt = s.lead?.crop ? at : { x: FRAME.x, y: FRAME.y, w: FRAME.w } // a cropped lead sits where the page will
  const firstInset = Math.min(...insets.map((i) => i.at))
  const dim = lin(frame, firstInset - 6, firstInset + 12, 0, 0.22)
  // insets: the right column stacks top-down at one shared scale that fits them all; slot 2 sits under a wide page
  const col = insets.filter((x) => x.slot !== 2)
  const colScale = Math.min(...col.map((x) => Math.min(x.scale, COL.w / x.crop.w)),
    (COL.bottom - COL.top - COL.gap * (col.length - 1)) / col.reduce((h, x) => h + x.crop.h, 0))
  const place = (i: InsetSpec, n: number) => {
    if (i.slot === 2) { const sc = Math.min(i.scale, at.w / i.crop.w); return { s: { ...i, scale: sc }, left: 960 - (i.crop.w * sc) / 2, top: at.y + pageH + 90 } }
    const before = col.slice(0, col.indexOf(i)).reduce((y, x) => y + x.crop.h * colScale + COL.gap, COL.top)
    return { s: { ...i, scale: colScale }, left: COL.x + (COL.w - i.crop.w * colScale) / 2, top: before }
  }
  return (
    <AbsoluteFill style={{ background: C.page }}>
      {s.lead && show < 1 && <div style={{ position: 'absolute', left: leadAt.x, top: leadAt.y, opacity: 1 - show }}>
        <ClipFrame uses={[s.lead]} width={leadAt.w} crop={s.lead.crop} marks={((s.highlights ?? []) as Mark[]).filter((h) => h.clip)} />
      </div>}
      {show > 0 && <div style={{ position: 'absolute', left: at.x, top: at.y, opacity: show }}>
        <Shot id={page.shot} width={at.w} crop={page.crop} dim={dim}>
          {((s.highlights ?? []) as Mark[]).filter((h) => !h.clip).map((h, j) => <Highlight key={j} {...h} k={k} bounds={page.crop} />)}
        </Shot>
      </div>}
      <Header n={s.n} headline={s.headline} detail={s.detail} />
      <div style={{ position: 'absolute', left: s.lead && show < 1 ? leadAt.x : at.x, top: 182 }}><Source text={s.label} /></div>
      {insets.map((i, n) => { const p = place(i, n); return <Inset key={n} s={p.s} left={p.left} top={p.top} /> })}
    </AbsoluteFill>
  )
}

// ---------- 4a · The package matrix: two crops of the same rows (Submittal · Documents | What to send · Decision) ----------
export function Matrix({ s }: { s: Scene }) {
  const crops = s.crops as { shot: string; crop: Box }[]
  const GAP = 36, k = (1760 - GAP) / crops.reduce((n, c) => n + c.crop.w, 0)
  let x = 80
  return (
    <AbsoluteFill style={{ background: C.page }}>
      <div style={{ position: 'absolute', top: 40, width: '100%' }}>
        <Words size={80} weight={700} words={s.headline.text.split(' ').map((w: string, i: number) => [w, s.headline.at + 4 * i] as [string, number])} />
      </div>
      <Source text={s.label} style={{ position: 'absolute', left: 80, top: 182 }} />
      {crops.map((c, i) => {
        const left = x
        x += c.crop.w * k + GAP
        const inside = (h: Mark) => h.box.x >= c.crop.x && h.box.x < c.crop.x + c.crop.w
        return <div key={i} style={{ position: 'absolute', left, top: 244 }}>
          <Shot id={c.shot} width={c.crop.w * k} crop={c.crop}>
            {(s.highlights as Mark[]).filter(inside).map((h, j) => <Highlight key={j} {...h} k={k} bounds={c.crop} />)}
          </Shot>
        </div>
      })}
    </AbsoluteFill>
  )
}

// ---------- 6a · The quote gate, on one real claim from the official run ----------
const CHECKS = [
  { cue: 'page', text: 'Quote is on the cited page' },
  { cue: 'value', text: 'Value, unit and metric are in the quote' },
]
export function Gate({ s }: { s: Scene }) {
  const c = s.cues!
  const crop = s.crop as Box, scale = 860 / crop.w
  return (
    <AbsoluteFill style={{ background: C.page }}>
      <div style={{ position: 'absolute', top: 40, width: '100%' }}>
        <Words size={80} weight={700} words={[['Models', c.head], ['read', c.head + 4], ['and', c.head + 8], ['quote.', c.head + 12]]} />
        <Words size={80} weight={700} color={C.flare} words={[['Code', c.head + 4], ['decides.', c.head + 4]]} style={{ marginTop: 6 }} />
      </div>
      <div>
        {/* the real page: 3M C-AJ-2738, page 1, with the app's own boxes around the quoted lines */}
        <Rise at={c.claim} style={{ position: 'absolute', left: 90, top: 300 }}>
          <div style={{ fontFamily: sans, fontSize: 30, color: C.soft, marginBottom: 14 }}>Submitted sheet · page 1</div>
          <div style={{ width: 860, height: crop.h * scale, borderRadius: 14, overflow: 'hidden', position: 'relative', background: '#fff', boxShadow: '0 30px 80px rgba(0,0,0,.6)' }}>
            <Img src={staticFile(`${s.shot}.png`)} style={{ position: 'absolute', left: -crop.x * scale, top: -crop.y * scale, width: W * scale, height: H * scale }} />
          </div>
        </Rise>
        <Rise at={c.claim + 6} style={{ position: 'absolute', left: 1010, top: 300, width: 820 }}>
          <div style={{ fontFamily: sans, fontSize: 30, color: C.soft, marginBottom: 14 }}>Claim from Nemotron 3 Super</div>
          <div style={{ background: C.panel, border: `1px solid ${C.edge}`, borderRadius: 16, padding: '22px 28px', fontFamily: mono, fontSize: 32, color: C.ink, lineHeight: 1.6 }}>
            <div><span style={{ color: C.muted }}>quote </span>“T Rating — 0 Hr”</div>
            <div><span style={{ color: C.muted }}>page  </span>1 · <span style={{ color: C.muted }}>metric </span>T rating · <span style={{ color: C.muted }}>value </span>0 Hr</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 26 }}>
            {CHECKS.map((x) => (
              <Rise key={x.cue} at={c[x.cue]} style={{ display: 'flex', alignItems: 'center', gap: 18, fontFamily: sans, fontSize: 36, color: C.ink }}>
                <span style={{ width: 40, height: 40, borderRadius: 8, background: C.good, color: '#06130c', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800 }}>✓</span>{x.text}
              </Rise>
            ))}
            <Rise at={c.compare} style={{ display: 'flex', alignItems: 'center', gap: 18, fontFamily: sans, fontSize: 36, color: C.ink }}>
              <span style={{ width: 40, height: 40, borderRadius: 8, border: `2px solid ${C.edge}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: mono, fontSize: 24 }}>{'{}'}</span>
              Code: T 0 hr vs spec T = F (2 hr)
            </Rise>
            <Rise at={c.verdict} style={{ marginLeft: 58 }}>
              <span style={{ display: 'inline-block', fontFamily: sans, fontSize: 36, fontWeight: 700, color: C.bad, border: `3px solid ${C.bad}`, borderRadius: 999, padding: '6px 24px' }}>Doesn't meet</span>
            </Rise>
          </div>
        </Rise>
      </div>
      <Rise at={c.unproven} style={{ position: 'absolute', top: 870, width: '100%', textAlign: 'center', fontFamily: sans, fontSize: 48, fontWeight: 650, color: C.ink }}>
        Unproven values go to a person, <span style={{ color: C.flare }}>never faked</span>
      </Rise>
    </AbsoluteFill>
  )
}
// ---------- 6b · How this was checked: the per-call list, panning ----------
export function Trace({ s }: { s: Scene }) {
  const frame = useCurrentFrame()
  const i = s.inset as { shot: string; crop: Box; scale: number; window: number; at: number }
  const w = i.crop.w * i.scale, full = i.crop.h * i.scale
  const pan = interpolate(frame, [i.at + 30, s.frames - 20], [0, full - i.window], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  return (
    <AbsoluteFill style={{ background: C.page }}>
      <Header headline={{ text: 'How this was checked', at: 0 }} />
      <Source text={s.label} style={{ position: 'absolute', left: 960 - w / 2, top: 182 }} />
      <div style={{ position: 'absolute', left: 960 - w / 2, top: 244, width: w, height: i.window, borderRadius: 18,
        overflow: 'hidden', border: '1px solid rgba(255,255,255,.16)', background: C.panel, boxShadow: '0 40px 100px rgba(0,0,0,.7)' }}>
        <Img src={staticFile(`${i.shot}.png`)} style={{ position: 'absolute', left: -i.crop.x * i.scale, top: -i.crop.y * i.scale - pan, width: W * i.scale, height: H * i.scale }} />
      </div>
    </AbsoluteFill>
  )
}

// ---------- 6c · How it runs: one row of services, each with its one-line role ----------
// five equal tiles, centered: 1656 px wide, so ≥ 96 px side margins even at the camera's 1.04 push; they enter 3 frames apart
const TILE = { w: 312, h: 300, gap: 24, y: 400 }
export function Arch({ s }: { s: Scene }) {
  const boxes = s.boxes as { title: string; note: string; at: number }[]
  const x0 = 960 - (boxes.length * TILE.w + (boxes.length - 1) * TILE.gap) / 2
  return (
    <AbsoluteFill style={{ background: C.page }}>
      <div style={{ position: 'absolute', top: 40, width: '100%' }}><Words size={76} weight={700} words={[['How', 0], ['it', 4], ['runs', 8]]} /></div>
      {boxes.map((b, i) => (
        <Rise key={b.title} at={boxes[0].at + 3 * i} style={{ position: 'absolute', left: x0 + i * (TILE.w + TILE.gap), top: TILE.y, width: TILE.w, height: TILE.h }}>
          <div style={{ width: TILE.w, height: TILE.h, boxSizing: 'border-box', borderRadius: 20, background: C.panel, border: `2px solid ${C.flare}`, padding: '0 22px',
            display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: 18, textAlign: 'center' }}>
            <span style={{ fontFamily: sans, fontSize: 40, fontWeight: 650, color: C.ink, lineHeight: 1.15 }}>{b.title}</span>
            <span style={{ fontFamily: sans, fontSize: 30, color: C.soft, lineHeight: 1.25 }}>{b.note}</span>
          </div>
        </Rise>
      ))}
    </AbsoluteFill>
  )
}

// ---------- 7 · Package memo: its first page on screen, then the print preview beside it (both whole, in frame) ----------
export function Memo({ s }: { s: Scene }) {
  const [screen, print] = s.pages as [{ shot: string; crop: Box; at: number }, { doc: string; at: number }]
  const H1 = 800, kScreen = H1 / screen.crop.h, wScreen = screen.crop.w * kScreen, wPrint = (H1 * 1700) / 2200
  const k = useRamp(print.at)
  const left = 960 - (wScreen + 70 + wPrint) / 2
  return (
    <AbsoluteFill style={{ background: C.page }}>
      <div style={{ position: 'absolute', top: 24, width: '100%' }}><Words size={76} weight={700} words={[['One', 0], ['memo', 4], ['for', 8], ['the', 12], ['package', 16]]} /></div>
      <Source text={s.label} style={{ position: 'absolute', left, top: 140 }} />
      <div style={{ position: 'absolute', left, top: 200 }}><Shot id={screen.shot} width={wScreen} crop={screen.crop} /></div>
      <div style={{ position: 'absolute', left: left + wScreen + 70, top: 140, opacity: k, translate: `0px ${(1 - k) * 8}px` }}>
        <Source text={s.chip.text} />
        <div style={{ marginTop: 24, width: wPrint, height: H1, borderRadius: 6, overflow: 'hidden', background: '#fff', boxShadow: '0 30px 80px rgba(0,0,0,.6)' }}>
          <Img src={staticFile(`${print.doc}.png`)} style={{ width: wPrint, height: H1 }} />
        </div>
      </div>
    </AbsoluteFill>
  )
}

// ---------- 7b · Result: one number from the official run ----------
export function Results({ s }: { s: Scene }) {
  const frame = useCurrentFrame(), { fps } = useVideoConfig()
  const { n, of, at } = s.number as { n: string; of: string; at: number }
  // the card is up from the scene's first frame; the count starts at a visible 0 as the crossfade ends and lands on n 0.6 s later
  const v = Math.min(Number(n), Math.floor(lin(frame, 8, 8 + sec(fps, 0.6)) * Number(n)))
  const d = 'M 0 4 L 900 4', ev = evolvePath(lin(frame, at + sec(fps, 0.5), at + sec(fps, 1.1)), d)
  return (
    <AbsoluteFill style={{ background: C.page, justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', background: C.panel,
        border: `1px solid ${C.edge}`, borderRadius: 28, padding: '64px 110px', boxShadow: '0 40px 100px rgba(0,0,0,.6)' }}>
        <div style={{ fontFamily: sans, fontWeight: 700, color: C.ink, display: 'flex', alignItems: 'baseline', gap: 28, fontSize: 80, letterSpacing: '-0.015em' }}>
          <span>Caught</span>
          <span style={{ fontSize: 210, lineHeight: 1, color: C.flare, fontVariantNumeric: 'tabular-nums' }}>{v}</span>
          <span>of {of}</span>
        </div>
        <div style={{ fontFamily: sans, fontWeight: 700, fontSize: 80, color: C.ink, marginTop: 8, letterSpacing: '-0.015em' }}>planted problems</div>
        <svg width={900} height={8} style={{ marginTop: 28 }}><path d={d} stroke={C.flare} strokeWidth={3} strokeDasharray={ev.strokeDasharray} strokeDashoffset={ev.strokeDashoffset} /></svg>
        <Rise at={at + sec(fps, 0.6)} style={{ fontFamily: sans, fontSize: 44, color: C.soft, marginTop: 26 }}>on real manufacturer documents</Rise>
      </div>
    </AbsoluteFill>
  )
}

// ---------- 8 · Close: the URL is the largest thing on the end card ----------
export function Close({ s, url, repo, event }: { s: Scene; url: string; repo: string; event: string }) {
  const frame = useCurrentFrame()
  const end = s.cues!.end
  const out = lin(frame, end - 8, end) // the two lines leave with an 8-frame fade; the end card rises in on the same cue
  const u = url.replace(/^https:\/\//, '')
  return (
    <AbsoluteFill style={{ background: C.page }}>
      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', gap: 26, opacity: 1 - out }}>
        <Words size={96} weight={700} words={s.words} />
        <Words size={96} weight={700} color={C.flare} words={s.words2} />
      </AbsoluteFill>
      {frame >= end && <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', gap: 44 }}>
        <Logo at={end} size={76} />
        <Rise at={end + 4} style={{ fontFamily: mono, color: C.ink, fontSize: 66, fontWeight: 500 }}>{u}</Rise>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
          <Rise at={end + 8} style={{ fontFamily: mono, color: C.soft, fontSize: 36 }}>{repo}</Rise>
          <Rise at={end + 12} style={{ fontFamily: sans, fontSize: 32, color: C.muted }}>{event}</Rise>
        </div>
      </AbsoluteFill>}
    </AbsoluteFill>
  )
}

// ---------- Guide only: the teleprompter band (global frames) ----------
export type Line = { scene: string; name: string; words: { w: string; at: number }[] }
export function Prompter({ lines }: { lines: Line[] }) {
  const frame = useCurrentFrame()
  const LEAD = 45 // a line shows 0.75 s before its first word
  let i = 0
  while (i + 1 < lines.length && frame >= lines[i + 1].words[0].at - LEAD) i++
  const l = lines[i], next = lines[i + 1]
  const first = l.words[0].at, last = l.words.at(-1)!.at
  const wait = Math.max(0, first - frame)
  return (
    <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 316, background: 'rgba(6,7,9,.95)', borderBottom: `3px solid ${C.flare}`,
      padding: '18px 48px', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: mono, fontSize: 28, color: C.flare }}>
        <span>{l.scene} · {l.name}</span>
        <span style={{ color: C.soft }}>{wait > 0 ? `read in ${(wait / 60).toFixed(1)} s` : next ? `next: ${next.scene}` : 'last line'}</span>
      </div>
      <div style={{ fontFamily: sans, fontSize: 44, lineHeight: 1.28, fontWeight: 500, color: '#5d626c' }}>
        {l.words.map((w, j) => {
          const nextAt = l.words[j + 1]?.at ?? last + 30
          const now = frame >= w.at && frame < nextAt
          return <span key={j} style={{ color: now ? C.flare : frame >= w.at ? C.ink : undefined }}>{w.w} </span>
        })}
      </div>
    </div>
  )
}
