import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import crypto from 'node:crypto'
const fileId = '507f1f77bcf86cd799439011'
const pdf = fs.readFileSync(new URL('./fixtures/synthetic.pdf', import.meta.url))
const hash = crypto.createHash('sha256').update(pdf).digest('hex')
const source = { file_id: fileId, source_id: 'chunk-2', filename: 'Synthetic agreement.pdf', page_number: 2, chunk_index: 1, score: .9, processing_run_id: 'run-1', content_sha256: hash, excerpt: 'Payment USD 100 due December 1, 2026.' }

for (const width of [1440, 390]) {
  test(`PDF canvas, navigation, citation and preserved chat at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const failures = []
    page.on('pageerror', error => { failures.push(error.message); console.error('BROWSER ERROR:', error.message) })
    page.on('console', message => { if (message.type() === 'error') console.error('BROWSER CONSOLE:', message.text()) })
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname
      if (path.endsWith('/content')) return route.fulfill({ contentType: 'application/pdf', body: pdf })
      let body
      if (path === '/api/files') body = [{ _id: fileId, filename: source.filename, status: 'completed', total_pages: 2 }]
      else if (path.endsWith('/view')) body = { file_id: fileId, filename: source.filename, status: 'completed', version: 'version-1', total_pages: 2, processing_run_id: 'run-1', content_sha256: hash, original_available: true, provenance: 'verified' }
      else if (path.endsWith('/chat')) body = { answer: 'Payment is USD 100 due December 1, 2026.', sources: [source], retrieval_time_ms: 1, generation_time_ms: 1, total_time_ms: 2 }
      else if (path.endsWith('/search')) body = { results: [source], next_after: null, version: 'version-1' }
      else body = { status: 'completed' }
      return route.fulfill({ json: body })
    })
    await page.goto('/')
    await page.getByRole('button', { name: 'Documents', exact: true }).first().click()
    await page.getByText(source.filename, { exact: true }).first().click()
    await expect(page.locator('canvas').first()).toBeVisible()
    await page.getByRole('button', { name: 'Next page', exact: true }).click()
    await expect(page.getByRole('spinbutton', { name: 'Page number' })).toHaveValue('2')
    await page.getByRole('button', { name: 'Zoom in' }).click()
    await expect(page.getByText('125%', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Fit width', exact: true }).click()
    if (width < 1024) await page.getByRole('tab', { name: 'chat', exact: true }).click()
    await page.getByRole('textbox', { name: 'Ask a question' }).fill('What payment is due?')
    await page.getByRole('button', { name: 'Ask document' }).click()
    await page.getByRole('button', { name: `Open ${source.filename} page 2` }).click()
    await expect(page.getByRole('spinbutton', { name: 'Page number' })).toHaveValue('2')
    await expect(page.getByRole('region', { name: 'Selected evidence' })).toContainText(source.excerpt)
    if (width < 1024) await page.getByRole('button', { name: 'Back to answer' }).click()
    await expect(page.getByText('Payment is USD 100 due December 1, 2026.', { exact: true })).toBeVisible()
    if (width < 1024) await page.getByRole('tab', { name: 'document', exact: true }).click()
    await page.getByRole('textbox', { name: 'Search document' }).fill('100')
    await expect(page.getByRole('button', { name: /Page 2 Payment USD/ })).toBeVisible()
    await page.screenshot({ path: `test-results/evidence-${width}.png`, fullPage: true })
    expect(failures).toEqual([])
  })
}

test('collection chat opens the correct document and retains the answer', async ({ page }) => {
  const second = '507f1f77bcf86cd799439012'
  const otherSource = { ...source, file_id: second, filename: 'Second agreement.pdf' }
  const docs = [{ _id: fileId, filename: source.filename, status: 'completed' }, { _id: second, filename: otherSource.filename, status: 'completed' }]
  const collection = { id: 'project', name: 'Contracts', file_ids: [fileId, second], revision: 1 }
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/content')) return route.fulfill({ contentType: 'application/pdf', body: pdf })
    let body
    if (path === '/api/files') body = docs
    else if (path === '/api/collections') body = [collection]
    else if (path.endsWith('/chat')) {
      expect(route.request().postDataJSON().file_ids).toEqual([second])
      body = { answer: 'The second agreement requires USD 100.', sources: [otherSource] }
    } else if (path.endsWith('/view')) body = { file_id: second, filename: otherSource.filename, status: 'completed', version: 'version-1', total_pages: 2, processing_run_id: 'run-1', content_sha256: hash, original_available: true, provenance: 'verified' }
    else body = {}
    return route.fulfill({ json: body })
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Collections', exact: true }).first().click()
  await page.getByRole('combobox', { name: 'Active collection' }).selectOption('project')
  await page.getByRole('group', { name: 'Question context' }).getByLabel('Second agreement.pdf · completed').check()
  await page.getByRole('textbox', { name: 'Ask a question' }).fill('What does the second agreement require?')
  await page.getByRole('button', { name: 'Ask document' }).click()
  await page.getByRole('button', { name: 'Open Second agreement.pdf page 2' }).click()
  await expect(page.locator('canvas').first()).toBeVisible()
  await expect(page.getByRole('spinbutton', { name: 'Page number' })).toHaveValue('2')
  await page.getByRole('button', { name: 'Back to collection' }).click()
  await expect(page.getByText('The second agreement requires USD 100.', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/collection-chat.png', fullPage: true })
})

test('synthetic comparison exposes differences and opens original evidence', async ({ page }) => {
  const second = '507f1f77bcf86cd799439012'
  const docs = [{ _id: fileId, filename: 'A.pdf', status: 'completed' }, { _id: second, filename: 'B.pdf', status: 'completed' }]
  const evidence = { ...source, file_id: second, filename: 'B.pdf', evidence_id: 'e2' }
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/content')) return route.fulfill({ contentType: 'application/pdf', body: pdf })
    let body
    if (path === '/api/files') body = docs
    else if (path === '/api/collections') body = [{ id: 'project', name: 'Compare contracts', file_ids: [fileId, second], revision: 1 }]
    else if (path.endsWith('/compare')) {
      expect(route.request().postDataJSON().file_ids).toEqual([fileId, second])
      body = { schema_version: 1, summary: { supported_difference: 1 }, limitations: ['Retrieved evidence only; no full-document completeness claim.'], sources: [evidence], findings: [{ topic: 'Amount (USD)', classification: 'supported_difference', explanation: 'Explicit retrieved amounts differ; no contradiction established.', documents: [{ file_id: fileId, filename: 'A.pdf', facts: [] }, { file_id: second, filename: 'B.pdf', facts: [{ values: ['100'], evidence_id: 'e2' }] }] }] }
    } else if (path.endsWith('/view')) body = { file_id: second, filename: 'B.pdf', status: 'completed', version: 'version-1', total_pages: 2, processing_run_id: 'run-1', content_sha256: hash, original_available: true, provenance: 'verified' }
    else body = {}
    return route.fulfill({ json: body })
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Collections', exact: true }).first().click()
  await page.getByRole('combobox', { name: 'Active collection' }).selectOption('project')
  const panel = page.getByRole('region', { name: 'Document comparison' })
  await panel.getByLabel('A.pdf · completed').check()
  await panel.getByLabel('B.pdf · completed').check()
  await panel.getByRole('button', { name: 'Compare selected documents' }).click()
  await expect(panel.getByText('Supported difference', { exact: true })).toBeVisible()
  await page.screenshot({ path: 'test-results/comparison.png', fullPage: true })
  await panel.getByRole('button', { name: 'Open comparison B.pdf page 2' }).click()
  await expect(page.locator('canvas').first()).toBeVisible()
  await expect(page.getByRole('spinbutton', { name: 'Page number' })).toHaveValue('2')
  await expect(page.getByRole('region', { name: 'Selected evidence' })).toContainText(evidence.excerpt)
  await page.getByRole('button', { name: 'Back to collection' }).click()
  await expect(panel.getByText('Amount (USD)', { exact: true })).toBeVisible()
})
