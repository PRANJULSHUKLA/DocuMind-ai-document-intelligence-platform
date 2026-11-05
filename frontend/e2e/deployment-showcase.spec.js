import { test, expect } from '@playwright/test'
import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../../deploy/showcase/', import.meta.url))
let server, origin

test.beforeAll(async () => {
  server = createServer(async (request, response) => {
    const name = new URL(request.url, 'http://localhost').pathname
    const file = path.resolve(root, '.' + (name === '/' ? '/index.html' : name))
    if (!file.startsWith(root)) { response.writeHead(403).end(); return }
    try {
      const body = await readFile(file)
      response.writeHead(200, { 'Content-Type': file.endsWith('.html') ? 'text/html' : file.endsWith('.css') ? 'text/css' : 'image/png' })
      response.end(body)
    } catch { response.writeHead(404).end() }
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  origin = `http://127.0.0.1:${server.address().port}`
})
test.afterAll(async () => { await new Promise(resolve => server.close(resolve)) })

for (const width of [360, 768, 1440]) test(`static fallback is honest, isolated and readable at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 })
  const failures = [], unexpected = []
  page.on('pageerror', error => failures.push(error.message))
  page.on('request', request => { if (!request.url().startsWith(origin)) unexpected.push(request.url()) })
  await page.goto(origin)
  await expect(page.getByText('Static demonstration', { exact: true })).toBeVisible()
  await expect(page.getByText(/Sign-in, uploads, AI questions and exports are not interactive here/)).toBeVisible()
  await expect(page.locator('form, input, script')).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
  await page.getByRole('link', { name: 'Explore the evidence viewer', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'The original stays in view.' })).toBeVisible()
  await expect(page.getByText(/intercepted test answers/)).toBeVisible()
  const image = page.getByAltText('Stable DocuMind Evidence Viewer showing synthetic PDF page two, a payment answer and its exact source passage.')
  await expect(image).toBeVisible()
  expect(await image.evaluate(el => el.complete && el.naturalWidth > 0)).toBe(true)
  await page.evaluate(() => window.scrollTo(0,0))
  await page.screenshot({ path: `test-results/showcase-${width}.png`, fullPage: true })
  expect(failures).toEqual([])
  expect(unexpected).toEqual([])
})
