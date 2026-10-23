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

test('upload, review source, edit decision, outcome, fresh re-check, reload and start over', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.goto('/')
  await page.locator('input[type=file]').first().setInputFiles('../tests/data/smoke.pdf')
  await page.getByRole('button', { name: 'Scan 1 submittal', exact: true }).click()
  await page.getByRole('button', { name: 'Start review', exact: true }).click()
  await expect(page.locator('aside').getByText(/Sources: spec/)).toBeVisible()
  await page.locator('#message').fill('Reviewer edited this message after checking the evidence.')
  await page.getByRole('button', { name: /^Save approval( decision)?$/, exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Outcome', exact: true })).toBeVisible()
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
