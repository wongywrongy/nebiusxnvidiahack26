// Shared capture harness: headed Chromium in kiosk mode on a private Xvfb screen, recorded at 60 fps with ffmpeg x11grab
// (real cursor hidden). Writes clips/<seg>.mp4 (constant 60 fps), <seg>.marks.json (element boxes for the camera and callouts)
// and <seg>.input.json (every logged mouse position, click and scroll, for the cursor Remotion draws).
import { chromium, type Browser, type BrowserContext, type Locator, type Page } from 'playwright'
import { execFileSync, spawn, type ChildProcess } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
export const BASE_URL = process.env.BASE_URL || 'https://speccheck-wongywrongys-projects.vercel.app'
/** The official recorded live run: every decision and number on screen comes from it. */
export const OFFICIAL = '20261028-173729-554074'
export const VIEW = { width: Number(process.env.VIEW_W || 1440), height: Number(process.env.VIEW_H || 900) } // CSS px, same layout as the screenshots
export const DSF = Number(process.env.DSF || 1.2) // 1440×900 CSS at 1.2 → a 1728×1080 screen: the clip's on-screen width at 90%, 59.7 unique fps in the gate
const SCREEN = { width: Math.round(VIEW.width * DSF), height: Math.round(VIEW.height * DSF) }
// Ubuntu's own xvfb and ffmpeg (x11grab, NVENC) unpacked without root; see capture/README.md.
const XVFB = process.env.XVFB || path.join(os.homedir(), '.local/opt/xvfb-deb/root/usr/bin/Xvfb')
export const FFMPEG = process.env.FFMPEG_X11 || path.join(os.homedir(), '.local/opt/ffmpeg-deb/ffmpeg')
const STATE = path.join(ROOT, 'capture/state')
const CLIPS = path.join(ROOT, 'capture/clips')

type Box = { x: number; y: number; w: number; h: number } // fractions of the viewport
type Mark = { id: string; t: number; box?: Box }
type Input = { t: number; type: 'move' | 'down' | 'up' | 'scroll'; x?: number; y?: number; box?: Box }
const ease = (k: number) => (k < 0.5 ? 4 * k ** 3 : 1 - (-2 * k + 2) ** 3 / 2) // easeInOutCubic

export class Take {
  page!: Page
  context!: BrowserContext
  browser!: Browser
  xvfb?: ChildProcess
  rec?: ChildProcess
  private display = `:${90 + Math.floor(Math.random() * 9)}`
  private marks: Mark[] = []
  private input: Input[] = []
  private t0 = 0 // wall clock of the first captured frame (x11grab stamps frames with wall-clock time)
  private mouse = { x: VIEW.width * 0.62, y: VIEW.height * 0.55 }
  constructor(readonly seg: string) {}

  async open(opts: { state?: string } = {}) {
    // One pixel larger than the capture: Chromium's fullscreen window comes out 1 px short of the screen.
    this.xvfb = spawn(XVFB, [this.display, '-screen', '0', `${SCREEN.width + 1}x${SCREEN.height + 1}x24`, '-nolisten', 'tcp', '-nocursor'], { stdio: 'ignore' })
    const socket = `/tmp/.X11-unix/X${this.display.slice(1)}`
    for (let i = 0; !fs.existsSync(socket); i++) { if (i > 100) throw new Error('Xvfb did not start'); await new Promise(r => setTimeout(r, 50)) }
    this.browser = await chromium.launch({ headless: false, env: { ...process.env, DISPLAY: this.display },
      args: ['--kiosk', `--window-size=${VIEW.width},${VIEW.height}`, '--window-position=0,0', `--force-device-scale-factor=${DSF}`,
        '--hide-scrollbars', '--force-color-profile=srgb', '--disable-infobars', '--no-first-run', '--noerrdialogs',
        ...(process.env.CHROME_GPU ? [] : ['--disable-gpu'])] })
    const storageState = opts.state ? path.join(STATE, `${opts.state}.json`) : undefined
    this.context = await this.browser.newContext({ viewport: null, storageState, acceptDownloads: false })
    this.page = await this.context.newPage()
    this.page.setDefaultTimeout(30000)
    this.page.on('pageerror', e => console.error('pageerror', e.message))
    // Playwright's launch keeps the toolbar despite --kiosk; browser fullscreen hides it so the page fills the screen.
    const cdp = await this.context.newCDPSession(this.page)
    const { windowId } = await cdp.send('Browser.getWindowForTarget')
    await cdp.send('Browser.setWindowBounds', { windowId, bounds: { windowState: 'fullscreen' } })
    await this.page.waitForFunction(([w, h]) => innerWidth === w && innerHeight === h, [VIEW.width, VIEW.height], { timeout: 5000 }).catch(() => {})
    const size = await this.page.evaluate(() => [innerWidth, innerHeight, devicePixelRatio])
    if (Math.abs(size[0] - VIEW.width) > 1 || Math.abs(size[1] - VIEW.height) > 1) throw new Error(`viewport is ${size}, expected ${VIEW.width}×${VIEW.height}`)
    return this.page
  }

  async start() {
    fs.mkdirSync(CLIPS, { recursive: true })
    const raw = path.join(CLIPS, `${this.seg}.raw.mkv`)
    this.rec = spawn(FFMPEG, ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'x11grab', '-framerate', '60', '-video_size',
      `${SCREEN.width}x${SCREEN.height}`, '-draw_mouse', '0', '-i', `${this.display}.0+0,0`, '-copyts', '-pix_fmt', 'bgr0',
      '-c:v', 'h264_nvenc', '-preset', 'p5', '-rc', 'constqp', '-qp', '14', '-g', '30', '-bf', '0', raw], { stdio: ['pipe', 'ignore', 'inherit'] })
    this.t0 = Date.now() / 1000 // refined from the first frame's timestamp in stop()
    await this.page.waitForTimeout(600)
    await this.page.mouse.move(this.mouse.x, this.mouse.y)
    this.log({ type: 'move', ...this.mouse })
  }

  /** Seconds since recording started (wall clock; corrected to the first frame in stop()). */
  now() { return Date.now() / 1000 - this.t0 }

  private log(e: Omit<Input, 't'>) { this.input.push({ t: +this.now().toFixed(4), ...e }) }

  private async boxOf(target: Locator, pad: number): Promise<Box> {
    // Union of every matching element, clipped to the viewport.
    const r = await target.evaluateAll(els => {
      const rs = els.map(e => e.getBoundingClientRect()).filter(r => r.width && r.height)
      return rs.length ? [Math.min(...rs.map(r => r.left)), Math.min(...rs.map(r => r.top)),
        Math.max(...rs.map(r => r.right)), Math.max(...rs.map(r => r.bottom))] : null
    })
    if (!r) throw new Error('element has no box')
    const [x0, y0] = [Math.max(0, r[0] - pad), Math.max(0, r[1] - pad)]
    const [x1, y1] = [Math.min(VIEW.width, r[2] + pad), Math.min(VIEW.height, r[3] + pad)]
    return { x: x0 / VIEW.width, y: y0 / VIEW.height, w: (x1 - x0) / VIEW.width, h: (y1 - y0) / VIEW.height }
  }

  /** A moment (and optionally an element box) the edit can anchor the camera, a callout or a phrase to. */
  async mark(id: string, target?: Locator, pad = 6, { replace = false } = {}) {
    const box = target ? await this.boxOf(target, pad).catch(e => { throw new Error(`mark ${id}: ${e.message}`) }) : undefined
    if (replace) this.marks = this.marks.filter(m => m.id !== id)
    this.marks.push({ id, t: +this.now().toFixed(4), ...(box && { box }) })
    console.log(`mark ${id} @ ${this.now().toFixed(2)}s`)
  }

  /** Glide to an element, rest 650 ms so a viewer can follow, click, then let it land for 400 ms. */
  async click(target: Locator, opts: { markAs?: string } = {}) {
    await this.scrollTo(target)
    await this.glide(target)
    await this.page.waitForTimeout(650)
    if (opts.markAs) await this.mark(opts.markAs, target)
    await this.page.mouse.down(); this.log({ type: 'down', ...this.mouse })
    await this.page.waitForTimeout(70)
    await this.page.mouse.up(); this.log({ type: 'up', ...this.mouse })
    await this.page.waitForTimeout(400)
  }

  /** Move the mouse along an eased path (30–60 steps, easeInOutCubic), logging every position. */
  async glide(target: Locator | { x: number; y: number }) {
    let to: { x: number; y: number }
    if ('boundingBox' in target) {
      const b = await target.first().boundingBox()
      if (!b) throw new Error('glide: element has no box')
      to = { x: b.x + Math.min(b.width / 2, 60), y: b.y + b.height / 2 }
    } else to = target
    const from = { ...this.mouse }
    const dist = Math.hypot(to.x - from.x, to.y - from.y)
    if (dist < 2) return
    const steps = Math.round(Math.min(60, Math.max(30, dist / 12)))
    const ms = Math.min(900, 380 + dist * 0.45)
    const t = Date.now()
    for (let i = 1; i <= steps; i++) {
      const e = ease(i / steps)
      this.mouse = { x: from.x + (to.x - from.x) * e, y: from.y + (to.y - from.y) * e }
      await this.page.mouse.move(this.mouse.x, this.mouse.y)
      this.log({ type: 'move', ...this.mouse })
      const wait = t + (ms * i) / steps - Date.now()
      if (wait > 0) await this.page.waitForTimeout(wait)
    }
  }

  /** Smooth-scroll an element to the middle of the viewport (unless it is comfortably visible) and wait until it settles. */
  async scrollTo(target: Locator, block: 'center' | 'start' | 'end' = 'center') {
    const visible = await target.first().evaluate(el => { const r = el.getBoundingClientRect(); return r.top >= 80 && r.bottom <= innerHeight - 160 })
    if (visible && block === 'center') return
    this.log({ type: 'scroll' })
    await target.first().evaluate((el, block) => el.scrollIntoView({ behavior: 'smooth', block }), block)
    await this.settle()
    this.log({ type: 'scroll', box: await this.boxOf(target.first(), 0).catch(() => undefined) })
  }

  async scrollBy(dy: number) {
    this.log({ type: 'scroll' })
    await this.page.evaluate(dy => window.scrollBy({ top: dy, behavior: 'smooth' }), dy)
    await this.settle()
    this.log({ type: 'scroll' })
  }

  async settle() {
    let last = -1
    for (;;) {
      await this.page.waitForTimeout(120)
      const y = await this.page.evaluate(() => [document.scrollingElement, ...document.querySelectorAll('*')]
        .filter(e => e && e.scrollTop).reduce((s, e) => s + e!.scrollTop, 0))
      if (y === last) return
      last = y
    }
  }

  async hold(ms: number) { await this.page.waitForTimeout(ms) }

  async saveState(name: string) {
    fs.mkdirSync(STATE, { recursive: true })
    await this.context.storageState({ path: path.join(STATE, `${name}.json`) })
  }

  async stop() {
    const end = this.now()
    await this.page.waitForTimeout(300)
    await new Promise<void>(resolve => { this.rec!.once('exit', () => resolve()); this.rec!.stdin!.write('q') })
    await this.close()
    const raw = path.join(CLIPS, `${this.seg}.raw.mkv`), clip = path.join(CLIPS, `${this.seg}.mp4`)
    const pts = execFileSync(FFMPEG.replace(/ffmpeg$/, 'ffprobe'), ['-v', 'error', '-select_streams', 'v', '-show_entries', 'packet=pts_time',
      '-of', 'csv=p=0', raw], { encoding: 'utf8', maxBuffer: 64 << 20 }).trim().split('\n').map(Number).sort((a, b) => a - b)
    const shift = pts[0] - this.t0 // align every logged time to the first frame
    for (const m of [...this.marks, ...this.input]) m.t = +(m.t - shift).toFixed(4)
    // Wall-clock frames → constant 60 fps from the first frame: duplicates fill any dropped frame, nothing is sped up.
    execFileSync(FFMPEG, ['-hide_banner', '-loglevel', 'error', '-y', '-i', raw, '-vf', 'setpts=PTS-STARTPTS', '-fps_mode', 'cfr', '-r', '60',
      '-c:v', 'h264_nvenc', '-preset', 'p5', '-rc', 'constqp', '-qp', '16', '-g', '30', '-bf', '0', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', clip])
    const gaps = pts.slice(1).map((p, i) => p - pts[i])
    const meta = { seg: this.seg, clip: `${this.seg}.mp4`, base_url: BASE_URL, captured_at: new Date().toISOString(), fps: 60,
      view: [VIEW.width, VIEW.height], size: [SCREEN.width, SCREEN.height], duration: +(end - shift).toFixed(3), frames: pts.length,
      capture_fps: +((pts.length - 1) / (pts.at(-1)! - pts[0])).toFixed(1), max_frame_gap_s: +Math.max(0, ...gaps).toFixed(3), marks: this.marks }
    fs.writeFileSync(path.join(ROOT, 'capture', `${this.seg}.marks.json`), JSON.stringify(meta, null, 1) + '\n')
    fs.writeFileSync(path.join(ROOT, 'capture', `${this.seg}.input.json`), JSON.stringify({ seg: this.seg, view: meta.view, events: this.input }) + '\n')
    fs.rmSync(raw)
    console.log(`${clip}: ${meta.duration}s, ${meta.frames} frames captured at ${meta.capture_fps} fps, ${this.marks.length} marks`)
  }

  async close() {
    await this.browser?.close().catch(() => {})
    this.xvfb?.kill()
  }
}

/** Route the app's Scan to the server's own replay of the official run (no provider calls); the results carry
 * replayed_from, so the app labels them "replayed". Only for the matrix and Review captures. */
export async function replayScans(page: Page, speed = 30) {
  await page.route('**/api/scan', async (route) => {
    const r = await fetch(`${BASE_URL}/api/runs/replay`, { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ source_run_id: OFFICIAL, speed }) })
    if (!r.ok) throw new Error(`replay failed: ${r.status}`)
    const { run_id } = await r.json()
    await route.fulfill({ json: { run_id, mode: 'live', mock: [], note: null } })
  })
}

/** The run id the app saved for the replayed package (from the browser state k2 saved). */
export function replayRun() {
  const state = JSON.parse(fs.readFileSync(path.join(ROOT, 'capture/state/replay.json'), 'utf8'))
  const ls = state.origins.flatMap((o: { localStorage: { name: string; value: string }[] }) => o.localStorage)
  const session = JSON.parse(ls.find((x: { name: string }) => x.name === 'speccheck.session.v2').value)
  return (Object.values(session.loaded)[0] as { run: string }).run
}

/** Ledger reading from the public health endpoint (no secrets: totals and caps only). */
export async function spend() {
  const r = await fetch(`${BASE_URL}/api/health`)
  const h = await r.json()
  return { usd: h.today.total_usd as number, credits: h.today.total_credits as number, mode: h.mode as string }
}

/** Run a take, retrying at most twice, and log its ledger delta to capture/spend.jsonl. */
export async function run(seg: string, body: (t: Take) => Promise<void>, { attempts = 3 } = {}) {
  for (let attempt = 1; attempt <= attempts; attempt++) {
    const before = await spend()
    if (before.mode !== 'live') throw new Error(`BASE_URL is in ${before.mode} mode`)
    const take = new Take(seg)
    try {
      await body(take)
      await take.stop()
      log(seg, attempt, before, await spend(), 'ok')
      return
    } catch (e) {
      console.error(`${seg} attempt ${attempt} failed:`, e)
      await take.page?.screenshot({ path: path.join(ROOT, `capture/${seg}-failure-${attempt}.png`) }).catch(() => {})
      take.rec?.kill('SIGINT')
      await take.close()
      log(seg, attempt, before, await spend(), String(e).slice(0, 300))
    }
  }
  process.exit(1)
}

function log(seg: string, attempt: number, before: { usd: number; credits: number }, after: { usd: number; credits: number }, result: string) {
  const row = { seg, attempt, at: new Date().toISOString(), usd: +(after.usd - before.usd).toFixed(6), credits: after.credits - before.credits, result }
  fs.appendFileSync(path.join(ROOT, 'capture/spend.jsonl'), JSON.stringify(row) + '\n')
  console.log('spend', row)
}
