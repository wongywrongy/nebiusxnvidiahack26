import { AbsoluteFill, Img, staticFile } from 'remotion'
import type { Data } from './Video'
import { C, sans } from './theme'

// The red discontinued card from the real Outcome screenshot (title, dates and quote), framed in 1280×720, with the name.
export function Thumbnail({ data }: { data: Data }) {
  const { image, box, view } = data.thumb
  const scale = Math.min(2.2, 1180 / box.w)
  return (
    <AbsoluteFill style={{ background: C.page, overflow: 'hidden' }}>
      <div style={{ position: 'absolute', left: 640 - (box.w * scale) / 2, top: 440 - (box.h * scale) / 2, width: box.w * scale, height: box.h * scale,
        overflow: 'hidden', borderRadius: 18, boxShadow: '0 30px 80px rgba(0,0,0,.6)' }}>
        <Img src={staticFile(image)} style={{ position: 'absolute', left: -box.x * scale, top: -box.y * scale, width: view.width * scale, height: view.height * scale }} />
      </div>
      <div style={{ position: 'absolute', left: 52, top: 40, display: 'flex', alignItems: 'center', gap: 20 }}>
        <div style={{ width: 44, height: 44, borderRadius: 11, background: C.flare }} />
        <span style={{ fontFamily: sans, fontWeight: 700, fontSize: 70, color: C.ink, letterSpacing: '-0.02em' }}>SpecCheck</span>
      </div>
    </AbsoluteFill>
  )
}
