// Short 60 fps clips of the real app on BASE_URL (Xvfb + headed Chromium + x11grab, real cursor hidden, eased mouse).
// usage: npx tsx capture/clips.ts k1|k2|k3|k4|k5|k6|k7
//   k1 live: add samples, press Scan, rows start streaming (live calls)
//   k2 replay: Scan → the official run's package matrix → open c02 (saves state "replay")
//   k3 replay: c03, click the page tag, the PDF jumps to the quote
//   k4 live: decide every item, Outcome → Check approved now → c07 discontinued (saves state "outcome")
//   k5 live: Specs → draft UBC 08 71 00 → delete the last rule → use it → Schlage ND upload, cursor on Scan (one draft call)
//   k6 replay: package memo → point-by-point alternate table → print view
//   k7 Scoreboard
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import type { Page } from 'playwright'
import { BASE_URL, ROOT, replayRun, replayScans, run, type Take } from './lib.ts'

// Settled: no requests in flight, fonts and every image decoded (no white PDF placeholders on camera).
async function settled(page: Page) {
  await page.waitForLoadState('networkidle')
  await page.evaluate('document.fonts.ready')
  await page.waitForFunction('[...document.images].every(i => i.complete && i.naturalWidth > 0)', null, { timeout: 30000 })
}
const scanReady = `[...document.querySelectorAll('button')].some(b => /^Scan \\d+ submittals?$/.test(b.textContent.trim()) && !b.disabled)`
const scanButton = (page: Page) => page.getByRole('button', { name: /^Scan \d+ submittals?$/ })
const isScan = (u: string, m: string) => new URL(u).pathname === '/api/scan' && m === 'POST'

async function addSamples(page: Page) {
  await page.goto(BASE_URL)
  await page.getByRole('button', { name: 'Add all samples', exact: true }).click()
  await page.waitForFunction(scanReady)
  await page.evaluate('window.scrollTo(0, 0)')
  await settled(page)
}

/** Every item decided as SpecCheck recommends, landing on Outcome (off camera). */
async function decideAll(page: Page) {
  await page.getByRole('button', { name: 'Start review', exact: true }).click()
  const outcome = page.getByRole('heading', { name: 'Outcome', exact: true })
  for (let i = 0; i < 20 && !(await outcome.isVisible()); i++) {
    for (const label of ['Mark as not checked', 'Save return decision', 'Save approval decision']) {
      const b = page.getByRole('button', { name: label, exact: true })
      if (await b.count()) { await b.click(); break }
    }
    await page.waitForTimeout(400)
  }
  await outcome.waitFor()
}

async function download(re: RegExp, dir: string) {
  const tries: { title: string; url: string }[] = JSON.parse(fs.readFileSync(path.join(ROOT, '../data/cases/try.json'), 'utf8'))
  const { url } = tries.find(d => re.test(d.title))!
  const file = path.join(dir, path.basename(new URL(url).pathname))
  fs.writeFileSync(file, Buffer.from(await (await fetch(url)).arrayBuffer()))
  return file
}

const clips: Record<string, [(t: Take) => Promise<void>, number?]> = {
  k1: [async (t) => {
    const page = await t.open()
    await page.goto(BASE_URL)
    await page.getByRole('button', { name: 'Add all samples', exact: true }).waitFor()
    await settled(page)
    await t.start()
    await t.hold(500)
    await t.click(page.getByRole('button', { name: 'Add all samples', exact: true }), { markAs: 'add_click' })
    await page.waitForFunction(scanReady)
    await t.mark('rows_ready', page.locator('div.arrive'))
    await page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })"); await t.settle()
    const started = page.waitForResponse(r => isScan(r.url(), r.request().method()))
    await t.click(scanButton(page), { markAs: 'scan_click' })
    if (!(await started).ok()) throw new Error('scan failed')
    await page.getByRole('heading', { name: 'Scanning' }).waitFor()
    await t.mark('scanning')
    // The live decisions must never reach the cut (they are not the official run): mark the first one so the edit ends before it.
    await page.waitForFunction(`/Reading pages|Checking the spec|Checking manufacturer|Investigating/.test(document.querySelector('main').innerText)`, null, { timeout: 120000 })
    await t.mark('streaming')
    await page.waitForFunction(`/Send back|Approve/.test(document.querySelector('main').innerText)`, null, { timeout: 120000 }).catch(() => {})
    await t.mark('first_decision')
    await t.hold(300)
  }, 1],

  k2: [async (t) => {
    const page = await t.open()
    await replayScans(page, 30)
    await addSamples(page)
    await t.start()
    await t.hold(400)
    await t.click(scanButton(page), { markAs: 'scan_click' })
    await page.getByRole('heading', { name: 'Scanning' }).waitFor()
    await t.mark('scanning')
    await page.getByRole('button', { name: 'Start review', exact: true }).waitFor({ timeout: 120000 })
    await settled(page)
    const band = page.locator('section[aria-label="07 84 00 Firestopping"]')
    await band.waitFor({ timeout: 60000 }) // the grouped matrix replaces the plain table once the package loads
    await settled(page)
    await t.mark('complete', band)
    await t.mark('replayed', page.locator('p').filter({ hasText: 'replayed items show their original usage' }))
    await t.glide(band.locator('header'))
    await t.hold(1600)
    const c02 = page.getByRole('button', { name: 'Review 07 84 00-02', exact: true })
    await t.mark('row_c02', c02.locator('xpath=..'))
    await t.saveState('replay')
    await t.click(c02, { markAs: 'open_c02' })
    await page.getByRole('img', { name: /^Page \d+$/ }).first().waitFor()
    await settled(page)
    await t.mark('review')
    await t.hold(1500)
  }, 2],

  k3: [async (t) => {
    const page = await t.open({ state: 'replay' })
    await page.goto(BASE_URL)
    await page.getByRole('button', { name: 'Start review', exact: true }).click()
    await page.getByRole('button', { name: '07 84 00-03', exact: true }).click()
    await settled(page)
    await page.getByRole('button', { name: 'Page 3', exact: true }).click() // the PDF starts away from the quote
    await page.waitForTimeout(800)
    await page.evaluate('window.scrollTo(0, 0)')
    await settled(page)
    await t.start()
    await t.hold(500)
    const tag = page.getByRole('button', { name: 'Show Highest service temperature on page 1' })
    await t.click(tag, { markAs: 'tag' })
    await t.settle()
    await page.waitForTimeout(600)
    await t.mark('quote', page.locator('[title="Problem: Data sheet is out of date"]').first())
    await t.glide(page.locator('[title="Problem: Data sheet is out of date"]').first())
    await t.hold(1800)
  }],

  k4: [async (t) => {
    const page = await t.open({ state: 'replay' })
    await page.goto(BASE_URL)
    await decideAll(page)
    const approved = page.getByRole('heading', { name: 'Approved for forwarding to the architect' })
    await approved.evaluate(el => el.scrollIntoView({ block: 'start' }))
    await page.evaluate('window.scrollBy(0, -120)')
    await settled(page)
    await t.start()
    await t.hold(400)
    const started = page.waitForResponse(r => isScan(r.url(), r.request().method()))
    await t.click(page.getByRole('button', { name: 'Check approved now', exact: true }), { markAs: 'check_click' })
    if (!(await started).ok()) throw new Error('re-check failed')
    await t.mark('checking')
    const alert = page.locator('section[aria-label$=" discontinued"]')
    await alert.waitFor({ timeout: 10 * 60000 })
    await t.mark('alert_seen')
    await page.getByRole('button', { name: 'Check approved now', exact: true }).waitFor({ timeout: 10 * 60000 })
    await t.mark('all_checked')
    await t.scrollTo(alert, 'start')
    await t.scrollBy(-40)
    await t.mark('alert', alert)
    await t.glide(alert.locator('blockquote'))
    await t.mark('quote', alert.locator('blockquote'))
    await t.hold(1500)
    const send = alert.getByText('What to send instead')
    await t.scrollTo(send)
    await t.mark('send', send.locator('xpath=..'))
    await t.glide(send)
    await t.hold(1500)
    await t.saveState('outcome')
  }, 1],

  k5: [async (t) => {
    // Ends on the cursor at "Scan 1 submittal" (no scan): the cut shows the Schlage Review from shots.ts (state "schlage",
    // saved by an earlier k5 take with this same edit), so this take makes one draft call and nothing else.
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'speccheck-clip-'))
    const spec = await download(/^UBC Door Hardware/, dir), sheet = await download(/^Schlage ND/, dir)
    const page = await t.open()
    const flat = () => page.evaluate(() => { for (const el of document.querySelectorAll('*')) if (el.scrollLeft) el.scrollLeft = 0 }) // tables at x = 0
    await page.goto(`${BASE_URL}/#specs`)
    const heading = page.getByRole('heading', { name: 'Draft a checklist from a spec PDF' })
    await heading.waitFor()
    await page.getByLabel(/^Spec section/).fill('08 71 00')
    await page.getByLabel('Section title', { exact: true }).fill('UBC Door Hardware')
    await settled(page)
    // The draft section ends the page, so the browser can't scroll it to the top: give it empty room below (page background
    // only), so the first frame is the UBC draft, not the lighting checklist above it.
    await page.evaluate("document.body.style.paddingBottom = '900px'")
    for (let i = 0; i < 3; i++) { // re-frame after late layout shifts
      await heading.evaluate(el => el.scrollIntoView({ block: 'start' }))
      await page.evaluate('window.scrollBy(0, -40)')
      await page.waitForTimeout(400)
    }
    await flat()
    await t.start()
    await t.hold(500)
    const chooser = page.waitForEvent('filechooser')
    await t.click(page.locator('label').filter({ hasText: 'Drop a spec PDF here or browse' }), { markAs: 'upload' })
    await (await chooser).setFiles(spec)
    const deletes = page.getByRole('button', { name: /^Delete requirement / })
    await deletes.first().waitFor({ timeout: 10 * 60000 })
    await flat()
    await settled(page)
    await t.mark('drafted')
    const provenance = page.getByText('Drafted by Nemotron 3 Super · edited by you · unreviewed · this browser only')
    await t.scrollTo(provenance, 'start')
    await t.scrollBy(-60)
    await flat()
    const row = (b: ReturnType<typeof deletes.first>) => b.locator('xpath=ancestor::tr[1]')
    const table = page.getByRole('region', { name: 'Checklist requirements' }).last()
    await t.mark('first_row', row(deletes.first()))
    await t.mark('table', table)
    await t.glide(provenance)
    await t.hold(1400)
    // Same edit as the release-final journey: delete the last drafted rule (the Review screenshot was checked against it).
    const last = deletes.last()
    await last.evaluate(el => el.closest('tr')!.scrollIntoView({ block: 'center', inline: 'nearest' }))
    await flat()
    await t.settle()
    await t.mark('delete_row', row(last))
    await t.mark('table_at_delete', table)
    await t.glide(row(last))
    await t.hold(700)
    await t.mark('delete')
    await last.evaluate(el => (el as HTMLElement).click()) // a script click: Playwright's own would scroll the table sideways to it
    await t.hold(800)
    while (await deletes.count() > 30) await deletes.last().evaluate(el => (el as HTMLElement).click()) // the app saves 1–30 rules
    await flat()
    await t.click(page.getByRole('button', { name: 'Use this checklist for my uploads' }), { markAs: 'use_click' })
    const ready = page.getByText(/is ready in this browser’s upload spec menu/)
    await ready.waitFor()
    await t.mark('saved', ready)
    await t.hold(600)
    await t.click(page.getByRole('link', { name: /^Return to / }), { markAs: 'return' })
    await page.getByRole('heading', { name: 'Inbox', exact: true }).waitFor()
    await settled(page)
    await page.locator('input[type=file][multiple]').first().setInputFiles({ name: 'schlage-nd.pdf', mimeType: 'application/pdf', buffer: fs.readFileSync(sheet) })
    const select = page.getByLabel('Spec for schlage-nd.pdf')
    await select.waitFor()
    await t.mark('uploaded', select)
    await t.glide(select)
    await t.hold(400)
    await select.selectOption((await select.locator('option').filter({ hasText: 'unreviewed draft' }).getAttribute('value'))!)
    await page.waitForLoadState('networkidle')
    await t.mark('spec_picked', select)
    const scan = page.getByRole('button', { name: 'Scan 1 submittal', exact: true })
    await t.glide(scan)
    await t.mark('scan_ready', scan)
    await t.hold(1500)
    fs.rmSync(dir, { recursive: true, force: true })
  }, 1],

  k6: [async (t) => {
    const page = await t.open()
    await page.goto(`${BASE_URL}/memo/${replayRun()}`)
    await page.getByText('Alternates, ranked in code').first().waitFor()
    await settled(page)
    await t.start()
    await t.hold(800)
    await t.mark('header', page.locator('header'))
    const table = page.getByText('Alternates, ranked in code').first().locator('xpath=..')
    await t.scrollTo(table, 'start')
    await t.scrollBy(-80)
    await t.mark('alternates', table)
    await t.glide(table.locator('table').first())
    await t.hold(1600)
    await page.emulateMedia({ media: 'print' })
    await page.evaluate('window.scrollTo(0, 0)')
    await settled(page)
    await t.mark('print')
    await t.hold(1400)
    await t.scrollBy(500)
    await t.hold(800)
  }],

  k7: [async (t) => {
    const page = await t.open()
    await page.goto(`${BASE_URL}/#scoreboard`)
    await page.locator('dl').waitFor()
    await settled(page)
    await t.start()
    await t.hold(500)
    await t.mark('panel', page.locator('dl'))
    await t.glide(page.locator('dl'))
    await t.hold(1200)
    const rows = page.locator('tbody tr')
    await t.scrollTo(rows.nth(3))
    await t.glide(rows.nth(2).locator('td').nth(1))
    await t.mark('rows', rows)
    await t.hold(1200)
  }],
}

const which = process.argv[2]
if (!clips[which]) throw new Error(`usage: clips.ts ${Object.keys(clips).join('|')}`)
await run(which, clips[which][0], { attempts: clips[which][1] ?? 3 })
