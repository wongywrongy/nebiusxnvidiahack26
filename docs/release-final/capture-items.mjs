// Screenshots of c02, c03, c05 and c07 from the official run's package memo, through the public URL. No scan, $0.
import assert from 'node:assert/strict'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '../../web/node_modules/playwright/index.mjs'

const out = path.join(path.dirname(fileURLToPath(import.meta.url)), 'public')
const base = 'https://speccheck-wongywrongys-projects.vercel.app'
const run = '20261028-173729-554074'
const items = { c02: 'Firestop system, floor penetration', c03: 'Firestop sealant, cable penetrations',
  c05: 'LED troffer, classrooms', c07: 'LED troffer, offices' }
const browser = await chromium.launch({ headless: true })
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1000 } })).newPage()
const errors = []
page.on('pageerror', e => errors.push(e.message))
await page.goto(`${base}/memo/${run}`)
await page.getByRole('button', { name: 'Print or save as PDF', exact: true }).waitFor()
for (const [id, title] of Object.entries(items)) {
  const section = page.locator('section.memo-item').filter({ hasText: title })
  assert.equal(await section.count(), 1, id)
  await section.screenshot({ path: path.join(out, `memo-${id}.png`) })
}
assert.deepEqual(errors, [])
console.log(JSON.stringify({ run, captured: Object.keys(items), passed: true }))
await browser.close()
