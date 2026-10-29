// Screenshots of the real app on BASE_URL (1440×900 at 2× → 2880×1800 PNG), each with the boxes of the elements the
// video zooms to or highlights. A shot is only taken once the page is settled: network idle, fonts ready, every image
// decoded with a real size, no busy text. Decisions come from the replay of the official run (state "replay", saved by
// clips k2), the c07 alert from the live re-check (state "outcome", k4), the Schlage review from k5 (state "schlage").
// usage: npx tsx capture/shots.ts [inbox|replay|outcome|memo|schlage …]   (no provider calls: replay, saved states and read-only pages)
import { chromium, type Locator, type Page } from 'playwright'
import fs from 'node:fs'
import path from 'node:path'
import { BASE_URL, replayRun, ROOT } from './lib.ts'

const VIEW = { width: 1440, height: 900 }
const OUT = path.join(ROOT, 'shots')
fs.mkdirSync(OUT, { recursive: true })
type Box = { x: number; y: number; w: number; h: number } // CSS px in the 1440×900 viewport

async function settled(page: Page) {
  await page.waitForLoadState('networkidle')
  await page.evaluate('document.fonts.ready')
  await page.waitForFunction(`[...document.images].every(i => i.complete && i.naturalWidth > 0)`, null, { timeout: 30000 })
  await page.waitForFunction(`!/Scanning…|Checking…|Drafting checklist…|Saving checklist…|Adding samples…|Loading/.test(document.body.innerText)`, null, { timeout: 60000 })
  await page.waitForTimeout(500)
}

// Put an element's centre at a fraction of the viewport height (instant window scroll).
async function place(target: Locator, at = 0.4) {
  await target.first().evaluate((el, at) => {
    const r = el.getBoundingClientRect()
    window.scrollTo({ top: Math.max(0, window.scrollY + r.top + r.height / 2 - innerHeight * at), behavior: 'instant' as ScrollBehavior })
  }, at)
}

async function boxOf(target: Locator): Promise<Box> {
  const r = await target.first().evaluate(e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom] })
  return { x: r[0], y: r[1], w: r[2] - r[0], h: r[3] - r[1] }
}

async function shot(page: Page, id: string, boxes: Record<string, Locator> = {}) {
  await page.mouse.move(VIEW.width - 4, VIEW.height - 4) // no hover state on anything we show
  await settled(page)
  const meta: { id: string; view: typeof VIEW; scale: number; boxes: Record<string, Box> } = { id, view: VIEW, scale: await page.evaluate('devicePixelRatio') as number, boxes: {} }
  for (const [name, loc] of Object.entries(boxes)) {
    const b = await boxOf(loc)
    if (b.y < 0 || b.y + b.h > VIEW.height || b.x < 0 || b.x + b.w > VIEW.width) throw new Error(`${id}: ${name} is cut at the viewport edge (${JSON.stringify(b)})`)
    meta.boxes[name] = b
  }
  await page.screenshot({ path: path.join(OUT, `${id}.png`), animations: 'disabled', caret: 'hide' })
  fs.writeFileSync(path.join(OUT, `${id}.json`), JSON.stringify(meta, null, 1) + '\n')
  console.log('shot', id, Object.keys(meta.boxes).join(', '))
}

const browser = await chromium.launch({ headless: true })
const want = (block: string) => process.argv.length < 3 || process.argv.slice(2).includes(block)
async function open(state?: string, scale = 2) {
  const context = await browser.newContext({ viewport: VIEW, deviceScaleFactor: scale,
    storageState: state ? path.join(ROOT, 'capture/state', `${state}.json`) : undefined })
  const page = await context.newPage()
  page.setDefaultTimeout(30000)
  page.on('pageerror', e => console.error('pageerror', e.message))
  return page
}
const aside = (page: Page) => page.locator('aside')
const card = (page: Page, caps: string) => aside(page).locator('span', { hasText: new RegExp(`^${caps}$`) }).first().locator('xpath=..')
const ruleRow = (page: Page, text: string) => aside(page).locator('li.grid').filter({ hasText: text }).first()
const group = (page: Page, text: string) => aside(page).locator('section').filter({ hasText: text }).last()
async function review(page: Page, number: string) {
  await page.getByRole('button', { name: number, exact: true }).click()
  await page.getByRole('img', { name: /^Page \d+$/ }).first().waitFor()
  await settled(page)
}

// Inbox, as a first-time visitor sees it.
if (want('inbox')) {
  const page = await open()
  await page.goto(BASE_URL)
  await page.getByRole('button', { name: 'Add all samples', exact: true }).waitFor()
  await shot(page, 'inbox')
  await page.context().close()
}
// The official run's package matrix and its Review screens (replay).
if (want('replay')) {
  const page = await open('replay')
  await page.goto(BASE_URL)
  const band = page.locator('section[aria-label="07 84 00 Firestopping"]')
  await band.waitFor()
  await page.evaluate('window.scrollTo(0, 0)')
  const row = (n: string) => page.getByRole('button', { name: `Review ${n}`, exact: true }).locator('xpath=..')
  await shot(page, 'matrix', { band, c02: row('07 84 00-02'), c03: row('07 84 00-03'),
    replayed: page.locator('p').filter({ hasText: 'replayed items show their original usage' }), count: page.getByText('3 to send back · 4 to approve') })

  await page.getByRole('button', { name: 'Start review', exact: true }).click()
  await review(page, '07 84 00-02')
  const c02 = ruleRow(page, 'Does not meet: Temperature rating')
  await place(c02, 0.62)
  await shot(page, 'review-c02', { finding: c02, group: group(page, 'Does not meet: Temperature rating'), send: card(page, 'What to send'), instead: card(page, 'What to send instead'),
    mark: page.locator('[title="Problem: Does not meet: Temperature rating (T)"]') })

  // s4: its trace has no investigation block, and all 11 calls fit on screen
  await review(page, '07 84 00-05')
  const how = aside(page).locator('details > summary').filter({ hasText: 'How this was checked' })
  await how.click()
  const calls = how.locator('xpath=..').locator('details > summary').filter({ hasText: 'Checked by' })
  await calls.click()
  const table = calls.locator('xpath=..').locator('div.overflow-hidden')
  await table.waitFor()
  // the summary line at the very top, so the long source URL above it is off screen
  await calls.evaluate(el => window.scrollBy({ top: el.getBoundingClientRect().top - 4, behavior: 'instant' as ScrollBehavior }))
  await shot(page, 'trace', { table, line: calls })

  await review(page, '07 84 00-03')
  await place(card(page, 'What to send'), 0.42)
  await shot(page, 'review-c03-send', { send: card(page, 'What to send'), instead: card(page, 'What to send instead') })
  await page.getByRole('button', { name: 'Show Highest service temperature on page 1' }).click()
  await page.waitForTimeout(800)
  const temp = ruleRow(page, 'Highest service temperature')
  await place(temp, 0.62)
  await shot(page, 'review-c03', { finding: temp, group: group(page, 'Highest service temperature'), mark: page.locator('[title="Problem: Data sheet is out of date"]') })
  await page.context().close()
}
// c07 after the live "Check approved now".
if (want('outcome')) {
  const page = await open('outcome')
  await page.goto(BASE_URL)
  const alert = page.locator('section[aria-label$=" discontinued"]')
  await alert.waitFor({ timeout: 90000 })
  await place(alert, 0.5)
  await shot(page, 'outcome-c07', { alert, dates: alert.locator('ol'), quote: alert.locator('blockquote'),
    send: alert.locator('span', { hasText: /^What to send instead$/ }).locator('xpath=..') })
  await page.context().close()
}
// Package memo of the replayed run, at one point-by-point alternate table; c07's "What to send" line exactly as the
// app writes it (the live alert lists alternates instead); and the print view.
if (want('memo')) {
  const page = await open()
  await page.goto(`${BASE_URL}/memo/${replayRun()}`)
  const alts = page.getByText('Alternates, ranked in code').first().locator('xpath=..')
  await alts.waitFor()
  await place(alts, 0.5)
  await shot(page, 'memo', { alts, table: alts.locator('table').first() })
  await page.evaluate('window.scrollTo(0, 0)')
  const c07 = page.locator('section.memo-item').filter({ hasText: '26 51 00-03' })
  const send = c07.locator('span', { hasText: /^What to send$/ }).locator('xpath=..')
  await place(send, 0.5)
  await shot(page, 'memo-c07', { label: send.locator('span').first(), line: send.locator('li').first() })
  await page.emulateMedia({ media: 'print' })
  await place(alts, 0.5)
  await shot(page, 'memo-print', { alts })
  // the app's own print output, at the 70 % scale a browser's print dialog offers (at 100 % Letter squeezes the matrix columns together)
  await page.pdf({ path: path.join(OUT, 'memo.pdf'), format: 'Letter', scale: 0.7, margin: { top: '0.5in', bottom: '0.5in', left: '0.5in', right: '0.5in' }, printBackground: true })
  await page.context().close()
}
// c02's quoted line at 4x pixel density, so the quote-gate close-up reads at 1080p.
if (want('gatehi')) {
  const page = await open('replay', 4)
  await page.goto(BASE_URL)
  await page.getByRole('button', { name: 'Start review', exact: true }).click()
  await review(page, '07 84 00-02')
  await place(ruleRow(page, 'Does not meet: Temperature rating'), 0.62)
  await shot(page, 'review-c02-hi', { mark: page.locator('[title="Problem: Does not meet: Temperature rating (T)"]') })
  await page.context().close()
}
// Bring your own spec: the Schlage ND review against the edited UBC draft (k5).
if (want('schlage')) {
  const page = await open('schlage')
  await page.goto(BASE_URL)
  const other = page.locator('aside details summary').filter({ hasText: 'rules for other product types' })
  await other.waitFor()
  await page.getByRole('img', { name: /^Page \d+$/ }).first().waitFor()
  await page.evaluate('window.scrollTo(0, 0)')
  await shot(page, 'schlage-top', { draft: aside(page).locator('p').filter({ hasText: 'Checked against your draft checklist' }) })
  await place(other, 0.6)
  // the strengths, each in its own box; the PDF's first page for the page crop
  await shot(page, 'schlage', { other, pdf: page.getByRole('img', { name: 'Page 1', exact: true }),
    model: ruleRow(page, 'ND Series'), datasheet: group(page, 'Data sheet version') })
  await page.context().close()
}
await browser.close()
