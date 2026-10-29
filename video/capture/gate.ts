// Capture gate: 10 s of smooth scrolling on a long page, then mpdecimate counts the frames that actually differ.
// Real takes need ≥ 55 unique fps. Run: npx tsx capture/gate.ts
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { BASE_URL, DSF, FFMPEG, ROOT, Take } from './lib.ts'

const t = new Take('gate')
const page = await t.open()
await page.goto(`${BASE_URL}/#specs`)
await page.getByRole('heading', { name: 'Draft a checklist from a spec PDF' }).waitFor()
await page.waitForLoadState('networkidle')
await t.start()
await t.hold(500)
await t.mark('scroll_start')
// Continuous motion for the whole window: scroll a few pixels every animation frame, bouncing at the ends.
// A string, not a function: tsx would inject a __name helper the page doesn't have.
const raf: number = await page.evaluate(`new Promise(done => {
  let dir = 1, n = 0
  const t0 = performance.now()
  function step() {
    n++
    window.scrollBy(0, 7 * dir)
    if (scrollY + innerHeight >= document.body.scrollHeight - 2 || (dir < 0 && scrollY <= 0)) dir = -dir
    if (performance.now() - t0 < 10000) requestAnimationFrame(step); else done(n / 10)
  }
  requestAnimationFrame(step)
})`)
console.log('page rAF rate', raf.toFixed(1), '/s')
await t.mark('scroll_end')
await t.stop()
const out = execFileSync(FFMPEG, ['-hide_banner', '-nostats', '-ss', '1.0', '-t', '10', '-i', path.join(ROOT, 'capture/clips/gate.mp4'),
  '-vf', 'mpdecimate', '-f', 'null', '-'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).toString()
console.log(out)
