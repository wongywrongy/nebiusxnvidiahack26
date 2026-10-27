// Actual browser gate. No intercepted API replies or fabricated results.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '../../web/node_modules/playwright/index.mjs'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const name = process.argv[2]
assert(['a', 'b', 'c', 'd', 'e'].includes(name), 'Choose exactly one gate case: a–e')
const base = process.env.SPECCHECK_BROWSER_URL || 'http://127.0.0.1:8009'
const out = process.env.SPECCHECK_EVIDENCE_DIR || path.join(root, 'docs/playground/local')
fs.mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: process.env.SPECCHECK_CHROMIUM_PATH })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage()
page.setDefaultTimeout(20000)
const errors = []
page.on('pageerror', error => errors.push(error.message))
const evidence = { case: name, url: base, captured_at: new Date().toISOString(), runs: [] }
const save = () => fs.writeFileSync(path.join(out, `${name}-trace.json`), JSON.stringify(evidence, null, 2) + '\n')
const get = async route => {
  const response = await context.request.get(base + route)
  assert(response.ok(), `${route}: ${response.status()}`)
  return response.json()
}
const health = () => get('/api/health')
const file = (index, filename) => ({ name: filename, mimeType: 'application/pdf',
  buffer: fs.readFileSync(index === 'off-topic' ? path.join(root, 'tests/data/off-topic.pdf') : `/tmp/speccheck-gate1-input-${index}.pdf`) })
async function upload(index, filename, spec) {
  await page.getByRole('heading', { name: 'Inbox', exact: true }).waitFor()
  const added = page.waitForResponse(r => new URL(r.url()).pathname === '/api/inbox' && r.request().method() === 'POST')
  await page.locator('input[type=file][multiple]').first().setInputFiles(file(index, filename))
  const response = await added
  assert(response.ok(), await response.text())
  const item = await response.json()
  evidence.inputs ??= []
  evidence.inputs.push({ id: item.id, filename, spec, input: index })
  if (spec) {
    const patched = page.waitForResponse(r => new URL(r.url()).pathname === `/api/inbox/${item.id}` && r.request().method() === 'PATCH')
    await page.getByLabel(`Spec for ${filename}`).selectOption(spec)
    const response = await patched
    assert(response.ok(), await response.text())
  }
  return item
}
async function screenshot(label) {
  if (label.includes('review')) await page.getByRole('img', { name: /^Page \d+$/ }).first().waitFor()
  await page.locator('img').evaluateAll(images => Promise.all(images.map(async img => {
    await img.decode(); if (!img.naturalWidth) throw new Error('PDF page did not render')
  })))
  await page.screenshot({ path: path.join(out, `${name}-${label}.png`), fullPage: true, animations: 'disabled' })
}
async function scan() {
  const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/scan' && r.request().method() === 'POST')
  await page.getByRole('button', { name: /^Scan \d+ submittals?$/ }).click()
  const started = await response
  assert(started.ok(), await started.text())
  const run = await started.json()
  evidence.runs.push({ ...run })
  save()
  await page.getByRole('button', { name: 'Start review', exact: true }).waitFor({ timeout: 900000 })
  const results = await get(`/api/runs/${run.run_id}/results`)
  const events = await context.request.get(base + `/api/runs/${run.run_id}/events`)
  Object.assign(evidence.runs.at(-1), { results: results.results, events: (await events.text()).split('\n')
    .filter(line => line.startsWith('data: ')).map(line => JSON.parse(line.slice(6))) })
  save()
  assert(results.done && results.results.length, 'Run must complete with results')
  for (const result of results.results) {
    assert.equal(result.mode, 'live')
    assert(!result.replayed_from, 'A replay cannot prove a live gate')
    assert.equal(result.validity, 'valid', JSON.stringify(result.diagnostics))
  }
  await screenshot('scan')
  await page.getByRole('button', { name: 'Start review', exact: true }).click()
  return results.results
}
async function decide() {
  for (const label of ['Mark as not checked', 'Save return decision', 'Save approval decision']) {
    const button = page.getByRole('button', { name: label, exact: true })
    if (await button.count()) { await button.click(); return }
  }
  throw new Error('Missing review action')
}
try {
  evidence.before = await health()
  assert.equal(evidence.before.mode, 'live')
  assert(!evidence.before.today.blocked)
  await page.goto(base)
  await page.getByRole('heading', { name: 'Sample submittals' }).waitFor()
  if (name === 'a') {
    await upload('off-topic', 'off-topic.pdf', '07 84 00')
    const [result] = await scan()
    assert.equal(result.decision, 'not_applicable')
    assert.equal(result.web_credits, 0)
    assert.equal(result.spec_match_count, 0)
    assert(!evidence.runs[0].events.some(e => ['verify', 'fix', 'investigate'].includes(e.stage)))
    await screenshot('review'); await decide(); await screenshot('outcome')
  } else if (name === 'b') {
    await upload(0, 'rectorseal-metacaulk.pdf', '07 84 00')
    const [result] = await scan()
    assert(result.spec_match_count > 0 && result.claims.some(c => c.quote), 'Product must yield a quoted checklist value')
    await screenshot('review'); await decide(); await screenshot('outcome')
  } else if (name === 'c') {
    await page.getByRole('link', { name: /^Specs/ }).click()
    const section = page.getByLabel(/^Spec section/)
    await section.fill('08 71 00')
    await page.getByLabel('Section title', { exact: true }).fill('UBC Door Hardware')
    const drafting = page.waitForResponse(r => new URL(r.url()).pathname === '/api/specs/draft', { timeout: 600000 })
    await page.getByLabel('Draft a checklist from a spec PDF').setInputFiles(file(3, 'ubc-door-hardware.pdf'))
    const drafted = await drafting
    assert(drafted.ok(), await drafted.text())
    evidence.draft = await drafted.json(); save()
    await page.getByRole('button', { name: /^Delete requirement / }).first().waitFor()
    const before = evidence.draft.draft.requirements.length
    assert(before > 1, 'Need at least two drafted rows to demonstrate deletion')
    await page.getByRole('button', { name: /^Delete requirement / }).last().click()
    while (await page.getByRole('button', { name: /^Delete requirement / }).count() > 30)
      await page.getByRole('button', { name: /^Delete requirement / }).last().click()
    await screenshot('draft-edited')
    const saving = page.waitForResponse(r => new URL(r.url()).pathname === '/api/checklists' && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Use this checklist for my uploads' }).click()
    const response = await saving
    assert(response.ok(), await response.text())
    evidence.checklist = await response.json()
    evidence.edited_checklist = response.request().postDataJSON()
    assert(evidence.checklist.n < before)
    save()
    await page.getByRole('link', { name: /Back to Inbox/ }).click()
    await upload(4, 'schlage-nd.pdf', evidence.checklist.id)
    const [result] = await scan()
    assert.equal(result.checklist_id, evidence.checklist.id)
    assert(result.spec_match_count > 0 && result.claims.some(c => c.quote), 'Paired sheet must match at least one draft rule')
    assert(/cylindrical.*lock/i.test(result.product_type), 'Schlage sheet must be scoped to cylindrical locksets')
    const otherTypes = result.findings.filter(f => f.verdict === 'not_applicable' && f.product_type)
    assert(otherTypes.length > 0, 'Other product types must be excluded')
    assert(result.findings.filter(f => f.requirement_id && f.verdict !== 'not_applicable')
      .every(f => !f.product_type || f.product_type === result.product_type), 'Only shared and lockset rules may apply')
    const hardware = evidence.edited_checklist.requirements.filter(r => /hinge|pivot|door_stop|flush_bolt|door_closer|exit_device/.test(r.property))
    assert(hardware.every(r => result.findings.some(f => f.requirement_id === r.id && f.verdict === 'not_applicable')),
      'Rules for other physical hardware must not remain in the visible lockset list')
    const ndRules = evidence.edited_checklist.requirements.filter(r => r.operator === 'any_of' &&
      /\bND\b/i.test(JSON.stringify(r.value)))
    assert(ndRules.some(r => result.findings.some(f => f.requirement_id === r.id && f.verdict === 'pass')),
      'The ND series must pass its allowed-series rule')
    const disclosure = page.locator('aside details').filter({ hasText: `${otherTypes.length} rules for other product types` })
    assert.equal(await disclosure.count(), 1)
    assert.equal(await disclosure.getAttribute('open'), null)
    await screenshot('review')
    await disclosure.locator('summary').click(); await screenshot('other-product-types')
    await disclosure.locator('summary').click(); await decide(); await screenshot('outcome')
  } else if (name === 'd') {
    const project = await get('/api/project')
    const expected = project.tray.flatMap(s => s.items).length
    const add = page.getByRole('button', { name: /^Add .* to the inbox$/ })
    for (let i = 0; i < expected; i++) await add.nth(i).click()
    const results = await scan()
    assert.equal(results.length, expected)
    assert(results.every(r => r.decision !== 'not_applicable'), 'Tray items must reach manufacturer checks')
    await screenshot('review')
    for (let i = 0; i < expected; i++) await decide()
    await page.getByRole('heading', { name: 'Outcome', exact: true }).waitFor()
    await screenshot('outcome')
  } else {
    const first = await upload(0, 'same-product-firestop.pdf', '07 84 00')
    const second = await upload(0, 'same-product-lighting.pdf', '26 51 00')
    const results = await scan()
    assert.notEqual(first.id, second.id)
    assert(results.find(r => r.case_id === first.id).spec_match_count > 0)
    const offTopic = results.find(r => r.case_id === second.id)
    assert.equal(offTopic.decision, 'not_applicable')
    assert.equal(offTopic.web_credits, 0)
    await screenshot('firestop-review'); await decide()
    await screenshot('lighting-review'); await decide(); await screenshot('outcome')
  }
  assert.deepEqual(errors, [])
  evidence.passed = true
} catch (error) {
  evidence.passed = false
  evidence.error = String(error)
  await screenshot('failure').catch(() => {})
  process.exitCode = 1
} finally {
  evidence.after = await health().catch(() => null)
  if (evidence.after) evidence.cost = {
    usd: +(evidence.after.today.total_usd - evidence.before.today.total_usd).toFixed(9),
    credits: evidence.after.today.total_credits - evidence.before.today.total_credits,
  }
  if (evidence.passed && (evidence.after.today.blocked || evidence.after.today.held_usd || evidence.after.today.held_credits)) {
    evidence.passed = false; evidence.error = 'Unresolved provider usage after the browser run'; process.exitCode = 1
  }
  save()
  console.log(JSON.stringify({ case: name, passed: evidence.passed, cost: evidence.cost, error: evidence.error,
    run_ids: evidence.runs.map(r => r.run_id) }))
  await browser.close()
}
