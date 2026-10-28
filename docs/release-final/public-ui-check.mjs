// Public check of the grouped-package UI through the Vercel URL: fresh browser, no admin token.
// Tray scan of c01-c03 -> grouped package -> Review c02, c03 (page tag) -> Outcome -> Check approved now -> one upload -> memo -> Scoreboard.
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '../../web/node_modules/playwright/index.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const out = path.join(here, 'public')
const base = 'https://speccheck-wongywrongys-projects.vercel.app'
const shot = (p, name) => p.screenshot({ path: path.join(out, name), fullPage: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 })
const page = await context.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(e.message))
const log = (...a) => console.log(new Date().toISOString(), ...a)

await page.goto(base)
assert.equal((await (await page.request.get(`${base}/api/health`)).json()).mode, 'live')
for (const f of ['sti_specseal_lci_tds_2025.pdf', '3m_c-aj-2738.pdf', '3m_ic15wb_2005.pdf'])
  await page.getByRole('button', { name: `Add ${f} to the inbox`, exact: true }).click()
await page.getByRole('button', { name: 'Scan 3 submittals', exact: true }).click()
await page.getByRole('heading', { name: 'Scan complete', exact: true }).waitFor({ timeout: 600000 })
const band = page.getByRole('region', { name: '07 84 00 Firestopping' })
await band.waitFor()
assert.equal(await page.getByText('Unknown').count(), 0)
log('scan complete', await band.locator('header').innerText())
await page.waitForTimeout(500)
await shot(page, 'ui-scan-complete.png')
await band.screenshot({ path: path.join(out, 'ui-band-07-84-00.png') })

await page.getByRole('button', { name: 'Review 07 84 00-02' }).click()
await page.locator('#message').waitFor()
await page.waitForTimeout(1500)
await shot(page, 'ui-review-c02.png')
await page.getByRole('button', { name: /^2 Scan/ }).click()
await page.getByRole('button', { name: 'Review 07 84 00-03' }).click()
await page.locator('#message').waitFor()
await page.waitForTimeout(1500)
await shot(page, 'ui-review-c03.png')
const submitted = page.locator('aside section').filter({ hasText: /^Submitted · / })
await submitted.first().screenshot({ path: path.join(out, 'ui-review-c03-submitted.png') })
const tag = submitted.first().getByRole('button', { name: /^Show .* on page \d+$/ }).first()
const n = (await tag.innerText()).replace('p.', '')
await tag.click()
await page.waitForTimeout(1000)
assert.equal(await page.locator('nav[aria-label=Pages] [aria-current=page]').innerText(), n)
log('c03 page tag ->', n)
await shot(page, 'ui-review-c03-page-tag.png')

while (!(await page.getByRole('heading', { name: 'Outcome', exact: true }).isVisible())) {
  await page.getByRole('button', { name: /^Save (return|approval) decision$/ }).click()
  await page.waitForTimeout(500)
}
const recheck = page.waitForRequest((r) => r.url().endsWith('/api/scan') && r.postDataJSON().refresh_web === true)
await page.getByRole('button', { name: 'Check approved now', exact: true }).click()
await recheck
await page.getByRole('button', { name: 'Check approved now', exact: true }).waitFor({ state: 'visible' })
await page.waitForFunction(() => [...document.querySelectorAll('button')].some((b) => b.textContent === 'Check approved now' && !b.disabled), null, { timeout: 600000 })
log('check approved now done')
await shot(page, 'ui-outcome.png')

await page.getByRole('link', { name: 'Start over', exact: true }).click()
await page.locator('input[type=file]').first().setInputFiles(path.join(here, '../../tests/data/off-topic.pdf'))
await page.getByRole('button', { name: 'Scan 1 submittal', exact: true }).click()
await page.getByRole('heading', { name: 'Scan complete', exact: true }).waitFor({ timeout: 600000 })
await page.getByRole('region', { name: 'Your uploads' }).waitFor()
log('upload lands in Your uploads')
await shot(page, 'ui-upload.png')

const [memo] = await Promise.all([context.waitForEvent('page'), page.getByRole('link', { name: 'Package review memo' }).click()])
await memo.getByText(/^Reviewer:/).waitFor()
await memo.close()
const official = await context.newPage()
await official.goto(`${base}/memo/20261028-173729-554074`)
await official.getByRole('button', { name: 'Print or save as PDF', exact: true }).waitFor()
await official.close()
log('memo ok')

await page.goto(`${base}/#scoreboard`)
await page.getByText('6/8', { exact: false }).first().waitFor()
log('scoreboard ok')
assert.deepEqual(errors, [])
console.log(JSON.stringify({ passed: true }))
await browser.close()
