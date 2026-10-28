import { test, expect, type Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  // Browser regressions run only against a mock API, including on machines with a live .env.
  const health = await page.request.get('/api/health')
  expect((await health.json()).mode).toBe('mock')
  await page.route('**/api/scan', async (route) => {
    await route.continue({ postData: JSON.stringify({ ...route.request().postDataJSON(), delay_ms: 0 }) })
  })
})

async function inbox(page: Page) {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Sample submittals' })).toBeVisible()
  await page.getByRole('button', { name: /^Add .* to the inbox$/ }).first().click()
}

async function review(page: Page) {
  await inbox(page)
  await page.getByRole('button', { name: 'Scan 1 submittal', exact: true }).click()
  await page.getByRole('button', { name: 'Start review', exact: true }).click()
  await expect(page.locator('#message')).toBeVisible()
}

test('add all samples waits for every row and skips samples already in the inbox', async ({ page }) => {
  await inbox(page)
  await expect(page.getByRole('button', { name: 'Scan 1 submittal', exact: true })).toBeEnabled()
  const project = await (await page.request.get('/api/project')).json()
  const expected = project.tray.flatMap((g: { items: { ready: boolean }[] }) => g.items).filter((c: { ready: boolean }) => c.ready).length
  let release!: () => void
  const pending = new Promise<void>((resolve) => { release = resolve })
  await page.route('**/api/inbox', async route => { await pending; await route.continue() })
  await page.getByRole('button', { name: 'Add all samples', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Scan 1 submittal', exact: true })).toBeDisabled()
  release()
  await expect(page.getByRole('button', { name: `Scan ${expected} submittals`, exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Add all samples', exact: true })).toBeDisabled()
  await expect(page.getByRole('button', { name: /^Add .* to the inbox$/ })).toHaveCount(project.tray.flatMap((g: { items: unknown[] }) => g.items).length)
  for (const tile of await page.getByRole('button', { name: /^Add .* to the inbox$/ }).all()) await expect(tile).toBeDisabled()
})

test('tray review, edit decision, outcome, fresh re-check, reload and start over', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await inbox(page)
  await page.getByRole('button', { name: 'Scan 1 submittal', exact: true }).click()
  await page.getByRole('button', { name: 'Start review', exact: true }).click()
  await page.getByText('How this was checked', { exact: true }).click()
  await expect(page.locator('aside').getByText(/Sources: spec/)).toBeVisible()
  await page.locator('#message').fill('Reviewer edited this message after checking the evidence.')
  await page.getByRole('button', { name: /^Save approval( decision)?$/, exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Outcome', exact: true })).toBeVisible()
  await expect(page.getByText('No nightly re-check has reported yet', { exact: true })).toHaveCount(0)
  const refreshed = page.waitForRequest((r) => r.url().endsWith('/api/scan') && r.postDataJSON().refresh_web === true)
  await page.getByRole('button', { name: 'Check approved now', exact: true }).click()
  await refreshed
  await expect(page.getByRole('button', { name: 'Check approved now', exact: true })).toBeEnabled()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Outcome', exact: true })).toBeVisible()
  await page.getByRole('button', { name: /^3 Review/ }).click()
  await expect(page.locator('#message')).toHaveValue('Reviewer edited this message after checking the evidence.')
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('link', { name: 'Start over', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Inbox', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Scan', exact: true })).toBeDisabled()
  expect(errors).toEqual([])
})

for (const body of [null, {}, { mode: 'mock', name: 'Broken', specs: [null], tray: [], watched: [] }]) {
  test(`project HTTP/malformed response ${JSON.stringify(body)} stays recoverable`, async ({ page }) => {
    await page.route('**/api/project', (route) => route.fulfill({ status: body === null ? 500 : 200,
      json: body ?? { detail: 'Temporary failure' } }))
    await page.goto('/')
    await expect(page.getByText("Couldn't load the project. Check that the API is running, then reload.")).toBeVisible()
    await page.unroute('**/api/project')
    await page.reload()
    await expect(page.getByRole('heading', { name: 'Sample submittals' })).toBeVisible()
  })
}

test('budget denial shows its reason and leaves the inbox retryable', async ({ page }) => {
  await inbox(page)
  await page.route('**/api/scan', (route) => route.fulfill({ status: 429, json: { detail: 'Daily budget reached. Try tomorrow.' } }))
  await page.getByRole('button', { name: 'Scan 1 submittal', exact: true }).click()
  await expect(page.getByText('Daily budget reached. Try tomorrow.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Scan 1 submittal', exact: true })).toBeEnabled()
})

test('failed result retrieval offers Retry', async ({ page }) => {
  await page.route('**/api/runs/*/results/*', (route) => route.fulfill({ status: 500, json: { detail: 'Result temporarily unavailable' } }))
  await inbox(page)
  await page.getByRole('button', { name: 'Scan 1 submittal', exact: true }).click()
  await expect(page.getByText('Result temporarily unavailable')).toBeVisible()
  await expect(page.getByRole('button', { name: /^Retry / })).toBeVisible()
})

test('missing PDF uses the text view', async ({ page }) => {
  await page.route('**/api/docs/**/pages', (route) => route.fulfill({ status: 404, json: { detail: 'PDF missing' } }))
  await review(page)
  await expect(page.locator('#message')).toBeVisible()
  await expect(page.locator('img')).toHaveCount(0)
})

test('lost scan stream offers Retry instead of spinning', async ({ page }) => {
  await page.route('**/api/runs/*/events', (route) => route.abort('failed'))
  await inbox(page)
  await page.getByRole('button', { name: 'Scan 1 submittal', exact: true }).click()
  await expect(page.getByText('Lost the scan connection. Retry this item.')).toBeVisible()
  await expect(page.getByRole('button', { name: /^Retry / })).toBeVisible()
})

test('replacement proposal is labelled in review, draft and outcome', async ({ page }, testInfo) => {
  await page.route('**/api/runs/*/results/*', async route => {
    const response = await route.fetch()
    const result = await response.json()
    result.decision = 'send_back'
    result.summary = result.note_to_subcontractor = 'Revise and resubmit to address the findings below.'
    result.findings = [{ id: 'synthetic-status', check: 'status', verdict: 'fail', severity: 'major',
      title: 'Synthetic retired product', detail: 'Synthetic browser scenario, not live evidence.',
      claim_ids: [], highlights: [], evidence: [], decided_by: 'code', fix: {
        head: 'Checked proposal', query: '', suggest: 'SpecCheck proposal: ZX-12-D1. Confirm configuration before ordering.',
        candidates: [{ name: 'Synthetic catalog', source_url: 'https://maker.test/catalog', passes: true,
          selection: { model: 'ZX-12-D1', origin: 'agent_proposal', page: 1, quote: '**Catalog** number: __ZX-12-D1__' },
          checks: [{ label: 'Synthetic quoted check', ok: true, note: '',
            evidence: [{url: 'https://maker.test/catalog', excerpt: '**Synthetic** quoted __evidence__.'}] }] }],
        alternates: [{ name: 'Synthetic catalog', source_url: 'https://maker.test/catalog', rank: 'meets_spec',
          confirm: [], failed: [], better: [], origin: 'search' }] } }]
    await route.fulfill({ response, json: result })
  })
  await review(page)
  await expect(page.getByText('Proposed by SpecCheck: ZX-12-D1. Confirm configuration before ordering.')).toBeVisible()
  await page.getByText('Evidence', {exact:true}).click()
  await expect(page.getByText('“Catalog number: ZX-12-D1”')).toBeVisible()
  await expect(page.getByText('“Synthetic quoted evidence.”')).toBeVisible()
  await expect.poll(() => page.evaluate(() => {
    const saved = JSON.parse(localStorage.getItem('speccheck.session.v2')!)
    return Object.values(saved.loaded).map((item: any) => item.result.findings[0].fix.candidates[0].selection.quote)[0]
  })).toBe('**Catalog** number: __ZX-12-D1__')
  await page.screenshot({path: testInfo.outputPath('proposal-desktop.png'),fullPage:true})
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({path:testInfo.outputPath('proposal-mobile.png'),fullPage:true})
})

test('scan complete shows the package matrix and opens Review at a row', async ({ page }) => {
  const cell = (spec: string, sheet: string, made: string, id: string) => ({ case_id: id, title: `Item ${id}`, number: id,
    sender: 'Sub', decision: 'approve_with_note', stamp: 'Exceptions noted', spec, current_sheet: sheet, still_made: made,
    meets: 1, doesnt_meet: 0, couldnt_confirm: 0, what_to_send: [`Line ${id}`, 'Second'], best_alternate: null,
    manual_review_suggested: id === 'r1', return_note: '', approval_note: '' })
  const synthetic = [cell('meets', 'current', 'active', 'r1'), cell('fails', 'outdated', 'discontinued', 'r2'),
    cell('configure', 'newer', 'unknown', 'r3'), cell('unconfirmed', 'unknown', 'unknown', 'r4'), cell('not_checked', 'unknown', 'unknown', 'r5')]
  await page.route('**/api/runs/*/package', async (route) => {
    const response = await route.fetch()
    const real = await response.json()
    await route.fulfill({ response, json: { ...real, rows: [...real.rows, ...synthetic] } })
  })
  await inbox(page)
  await page.getByRole('button', { name: 'Scan 1 submittal', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Scan complete', exact: true })).toBeVisible()
  const matrix = page.getByRole('button', { name: /^Review / })
  await expect(matrix).toHaveCount(1)  // only rows for items in this scan are shown
  await matrix.click()
  await expect(page.locator('#message')).toBeVisible()
})

test('the package shows one status line only when there is news, and never Unknown', async ({ page }) => {
  // Each sheet / still-made pair through a real scan whose one row is rewritten; null: no status line.
  const values: [string, string, string | null][] = [['current', 'active', null], ['outdated', 'active', 'Sheet out of date'],
    ['newer', 'unknown', 'Newer sheet online'], ['current', 'discontinued', 'Discontinued'], ['outdated', 'discontinued', 'Discontinued'],
    ['unknown', 'not_checked', null]]
  let n = 0
  await page.route('**/api/runs/*/package', async (route) => {
    const response = await route.fetch()
    const real = await response.json()
    const [current_sheet, still_made] = values[n++ % values.length]
    await route.fulfill({ response, json: { ...real, rows: real.rows.map((r: object) => ({ ...r, current_sheet, still_made })) } })
  })
  for (const [, , status] of values) {
    await page.evaluate(() => localStorage.clear()).catch(() => {})
    await inbox(page)
    await page.getByRole('button', { name: 'Scan 1 submittal', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Scan complete', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: /^Review / })).toBeVisible()
    await expect(page.locator('[data-status]')).toHaveText(status ? [new RegExp(`${status}$`)] : [])
    await expect(page.getByRole('img', { name: /meets?|doesn't meet|not confirmed|with an option/ })).toHaveCount(1)
    await expect(page.getByText('Unknown')).toHaveCount(0)
    await expect(page.getByText('Worth a manual look')).toHaveCount(0)
  }
})

test('flag for manual review lands in its own Outcome bucket and survives reload', async ({ page }) => {
  await review(page)
  await expect(page.getByText('What to send', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Flag for manual review', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Outcome', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Manual review', exact: true })).toBeVisible()
  await expect(page.getByText(/· 1 for manual review$/)).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Manual review', exact: true })).toBeVisible()
  await page.getByRole('button', { name: /^3 Review/ }).click()
  await expect(page.getByText('· Saved: flagged for manual review')).toBeVisible()
})

test('the package memo opens from Scan complete with the matrix, labels and a reviewer line', async ({ page, context }) => {
  await inbox(page)
  await page.getByRole('button', { name: 'Scan 1 submittal', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Scan complete', exact: true })).toBeVisible()
  const [memo] = await Promise.all([context.waitForEvent('page'), page.getByRole('link', { name: 'Package review memo' }).click()])
  await expect(memo.getByText(/^Reviewer:/)).toBeVisible()
  await expect(memo.getByText(/mock \(fixture answers\)/)).toBeVisible()
  await expect(memo.locator('[data-cell]').first()).toBeVisible()
  await expect(memo.getByText(/^Checked by /)).toHaveCount(1)
})
