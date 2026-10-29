// Shared motion, driven only by useCurrentFrame(): text and overlays fade in with an 8 px rise and are fully readable
// 12 frames after their cue; they leave with an 8-frame fade.
import type { CSSProperties, ReactNode } from 'react'
import { Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion'
import { C, mono, sans } from './theme'

export const SPRING = { damping: 200, mass: 0.8 }
export type Box = { x: number; y: number; w: number; h: number }

/** 0 → 1 on the shared spring, starting at frame `at`. */
export function useIn(at: number) {
  const frame = useCurrentFrame(), { fps } = useVideoConfig()
  return frame < at ? 0 : spring({ frame: frame - at, fps, config: SPRING })
}
export const lin = (frame: number, a: number, b: number, from = 0, to = 1) =>
  interpolate(frame, [a, b], [from, to], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
/** 0 → 1 over 12 frames from `at`, eased out: an element is fully in 12 frames after its cue. */
export const ramp = (frame: number, at: number, len = 12) =>
  interpolate(frame, [at, at + len], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) })
export function useRamp(at: number, len = 12) {
  return ramp(useCurrentFrame(), at, len)
}

/** Fades in with an 8 px rise, fully in 12 frames after `at`; with `out`, fades out over the 8 frames before it. */
export function Rise({ at, out, children, style }: { at: number; out?: number; children: ReactNode; style?: CSSProperties }) {
  const frame = useCurrentFrame()
  const k = ramp(frame, at), o = out === undefined ? 1 : 1 - lin(frame, out - 8, out)
  return <div style={{ ...style, opacity: k * o, translate: `0px ${(1 - k) * 8}px` }}>{children}</div>
}

/** One line of text, shown whole on its first cue (never word by word). */
export function Words({ words, size, color = C.ink, weight = 600, style }: { words: [string, number][]; size: number; color?: string
  weight?: number; style?: CSSProperties }) {
  return (
    <Rise at={Math.min(...words.map((w) => w[1]))} style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', columnGap: size * 0.28, fontFamily: sans, fontSize: size,
      fontWeight: weight, color, letterSpacing: '-0.015em', lineHeight: 1.15, ...style }}>
      {words.map(([w], i) => <span key={i}>{w}</span>)}
    </Rise>
  )
}

/** A stamp that lands: scales down from 1.6x and settles at a slight angle. */
export function Stamp({ at, text, color = C.bad, size = 44, style }: { at: number; text: string; color?: string; size?: number; style?: CSSProperties }) {
  const k = useRamp(at)
  if (k <= 0) return null
  return (
    <div style={{ position: 'absolute', ...style, opacity: Math.min(1, k * 1.6), scale: `${1.6 - 0.6 * k}`, rotate: '-7deg',
      border: `5px solid ${color}`, borderRadius: 14, padding: '8px 22px', color, fontFamily: sans, fontWeight: 800, fontSize: size,
      letterSpacing: '0.06em', background: 'rgba(11,12,15,.82)', whiteSpace: 'nowrap', boxShadow: '0 10px 30px rgba(0,0,0,.45)' }}>
      {text}
    </div>
  )
}

/** The app's screenshot (1440×900 CSS, 2880×1800 PNG) in a simple browser frame; `crop` shows a CSS-px region of it.
 * Children (highlights) sit above the dim, in the same CSS-px space; `drift` is a slow push-in so the frame never freezes. */
export function Shot({ id, width, crop = { x: 0, y: 0, w: 1440, h: 900 }, dim = 0, drift = 1, children, style }: { id: string; width: number
  crop?: Box; dim?: number; drift?: number; children?: ReactNode; style?: CSSProperties }) {
  const s = width / crop.w
  return (
    <div style={{ width, borderRadius: 16, overflow: 'hidden', border: '1px solid rgba(255,255,255,.10)', background: C.panel,
      boxShadow: '0 30px 80px rgba(0,0,0,.55), 0 4px 16px rgba(0,0,0,.35)', ...style }}>
      <div style={{ height: 22, display: 'flex', alignItems: 'center', gap: 8, paddingLeft: 14, background: '#15171c', borderBottom: '1px solid rgba(255,255,255,.06)' }}>
        {[0, 1, 2].map((i) => <span key={i} style={{ width: 10, height: 10, borderRadius: 5, background: '#2c3038' }} />)}
      </div>
      <div style={{ position: 'relative', width, height: crop.h * s, overflow: 'hidden' }}>
        <div style={{ position: 'absolute', inset: 0, scale: `${drift}` }}>
          <Img src={staticFile(`${id}.png`)} style={{ position: 'absolute', left: -crop.x * s, top: -crop.y * s, width: 1440 * s, height: 900 * s }} />
          <div style={{ position: 'absolute', inset: 0, background: C.page, opacity: dim }} />
          <div style={{ position: 'absolute', left: -crop.x * s, top: -crop.y * s }}>{children}</div>
        </div>
      </div>
    </div>
  )
}

export function Logo({ at, size = 96, letters = true }: { at: number; size?: number; letters?: boolean }) {
  const frame = useCurrentFrame()
  const sq = size * 0.62
  const draw = lin(frame, at, at + 12)
  const fill = ramp(frame, at + 6)
  const per = 4 * sq
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: size * 0.3 }}>
      <svg width={sq + 4} height={sq + 4} viewBox={`-2 -2 ${sq + 4} ${sq + 4}`}>
        <rect x={0} y={0} width={sq} height={sq} rx={sq * 0.26} fill={C.flare} fillOpacity={fill} stroke={C.flare} strokeWidth={3}
          pathLength={per} strokeDasharray={per} strokeDashoffset={per * (1 - draw)} />
      </svg>
      {letters && <Rise at={at} style={{ fontFamily: sans, fontWeight: 700, fontSize: size, color: C.ink, letterSpacing: '-0.02em' }}>SpecCheck</Rise>}
    </div>
  )
}
