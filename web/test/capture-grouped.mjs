// Mock-mode screenshots of the grouped package and two reviews: node test/capture-grouped.mjs <out dir> [base url] [scale]
import { chromium } from '@playwright/test'
const [out = '.', base = 'http://127.0.0.1:8007', scale = '1'] = process.argv.slice(2)
const browser = await chromium.launch(process.env.SPECCHECK_CHROMIUM_PATH ? { executablePath: process.env.SPECCHECK_CHROMIUM_PATH } : {})
for (const width of [1440, 390]) {
  const page = await browser.newPage({ viewport: { width, height: width > 500 ? 1000 : 844 }, deviceScaleFactor: Number(scale) })
  await page.route('**/api/scan', (route) => route.continue({ postData: JSON.stringify({ ...route.request().postDataJSON(), delay_ms: 0 }) }))
  await page.goto(base)
  await page.evaluate(() => localStorage.clear())
  await page.reload()
  await page.getByRole('button', { name: 'Add all samples', exact: true }).click()
  await page.getByRole('button', { name: /^Scan \d+ submittals$/ }).click()
  await page.getByRole('heading', { name: 'Scan complete', exact: true }).waitFor({ timeout: 60000 })
  await page.getByRole('button', { name: /^Review / }).first().waitFor()
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${out}/scan-complete-${width}.png`, fullPage: true })
  console.log(width, 'page overflow', await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
  for (const n of ['02', '03']) {
    if (n === '02') await page.getByRole('button', { name: `Review 07 84 00-${n}` }).click()
    else await page.getByRole('button', { name: new RegExp(`^07 84 00-${n}`) }).click()
    await page.locator('#message').waitFor()
    await page.waitForTimeout(800)
    await page.screenshot({ path: `${out}/review-c${n}-${width}.png`, fullPage: true })
  }
  await page.close()
}
await browser.close()
