import { AbsoluteFill, Audio, Sequence, interpolate, staticFile, useCurrentFrame } from 'remotion'
import { TransitionSeries, linearTiming } from '@remotion/transitions'
import { fade } from '@remotion/transitions/fade'
import { C, mono, sans } from './theme'
import type { Box } from './anim'
import { Arch, Catch, Close, Context, Gate, Live, Matrix, Memo, Prompter, Results, Title, Trace, type Line, type Scene } from './scenes'

export type Data = { fps: number; fade: number; frames: number; scenes: Scene[]; base_url: string; repo: string; event: string; vo: boolean
  prompter: Line[]; thumb: { image: string; box: Box; view: { width: number; height: number } } }

const view = (s: Scene, data: Data) => {
  switch (s.type) {
    case 'title': return <Title s={s} />
    case 'context': return <Context s={s} />
    case 'live': return <Live s={s} />
    case 'matrix': return <Matrix s={s} />
    case 'catch': return <Catch s={s} />
    case 'gate': return <Gate s={s} />
    case 'trace': return <Trace s={s} />
    case 'arch': return <Arch s={s} />
    case 'memo': return <Memo s={s} />
    case 'results': return <Results s={s} />
    default: return <Close s={s} url={data.base_url} repo={data.repo} event={data.event} />
  }
}

/** A slow push (1.00 → 1.04) across the whole scene, so a held card or end frame is never fully static. */
function Camera({ frames, children }: { frames: number; children: React.ReactNode }) {
  const frame = useCurrentFrame()
  const k = interpolate(frame, [0, frames], [1, 1.04], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
  return <AbsoluteFill style={{ scale: `${k}` }}>{children}</AbsoluteFill>
}

// Scenes joined by one transition: a 10-frame crossfade. Kyle's voice plays per scene once his take is aligned, over a
// −60 dB room-tone bed from the same take, so no pause drops to digital silence.
export const Video = ({ data, silent = false }: { data: Data; silent?: boolean }) => (
  <AbsoluteFill style={{ background: C.page }}>
    <TransitionSeries>
      {data.scenes.flatMap((s, i) => [
        ...(i ? [<TransitionSeries.Transition key={`t${i}`} presentation={fade()} timing={linearTiming({ durationInFrames: data.fade })} />] : []),
        <TransitionSeries.Sequence key={s.id} name={s.id} durationInFrames={s.frames}>
          {s.audio && !silent && <Sequence from={s.audioAt} layout="none"><Audio src={staticFile(s.audio)} /></Sequence>}
          <Camera frames={s.frames}>{view(s, data)}</Camera>
        </TransitionSeries.Sequence>,
      ])}
    </TransitionSeries>
    {data.vo && !silent && <Audio src={staticFile('roomtone.wav')} loop />}
  </AbsoluteFill>
)

export const COUNTDOWN = 180
/** The recording guide: a 3-second countdown, then the silent cut with the teleprompter band on top. */
export const Guide = ({ data }: { data: Data }) => {
  const frame = useCurrentFrame()
  return (
    <AbsoluteFill style={{ background: C.page }}>
      <Sequence durationInFrames={COUNTDOWN}>
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', gap: 30, fontFamily: sans, color: C.ink }}>
          <div style={{ fontSize: 44, color: C.soft }}>Recording guide · read the band at the top</div>
          <div style={{ fontSize: 220, fontWeight: 700, color: C.flare, fontFamily: mono }}>{3 - Math.floor(frame / 60)}</div>
          <div style={{ fontSize: 40, color: C.soft, maxWidth: 1500, textAlign: 'center' }}>First line: {data.prompter[0].words.map((w) => w.w).join(' ')}</div>
        </AbsoluteFill>
      </Sequence>
      <Sequence from={COUNTDOWN}>
        <Video data={data} silent />
        <Prompter lines={data.prompter} />
      </Sequence>
    </AbsoluteFill>
  )
}
