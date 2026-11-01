import { test, expect } from '@playwright/test'
import fs from 'node:fs'
import { Buffer } from 'node:buffer'
import crypto from 'node:crypto'
const fileId = '507f1f77bcf86cd799439011'
const pdf = fs.readFileSync(new URL('./fixtures/synthetic.pdf', import.meta.url))
const hash = crypto.createHash('sha256').update(pdf).digest('hex')
const source = { file_id: fileId, source_id: 'chunk-2', filename: 'Synthetic agreement.pdf', page_number: 2, chunk_index: 1, score: .9, processing_run_id: 'run-1', content_sha256: hash, excerpt: 'Payment USD 100 due December 1, 2026.' }

test('explicit bounded semantic mode displays evidence facts and uncertainty', async ({ page }) => {
  const second = '507f1f77bcf86cd799439012'
  let calls = 0
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/files') return route.fulfill({ json: [{ _id: fileId, filename: 'A.pdf', status: 'completed' }, { _id: second, filename: 'B.pdf', status: 'completed' }] })
    if (path === '/api/collections') return route.fulfill({ json: [{ id: 'project', name: 'Semantic examples', file_ids: [fileId, second], revision: 1 }] })
    if (path.endsWith('/compare-semantic')) {
      calls++
      return route.fulfill({ json: { summary: { insufficient_evidence: 1 }, limitations: ['Qualified clauses require review.'], findings: [{ topic: 'Normalized obligation', classification: 'insufficient_evidence', explanation: 'Conditions require human review.', documents: [] }], sources: [], extracted_facts: [{ fact_id: 'f1', kind: 'obligation', value: { party: 'buyer', action: 'pay unless approved' }, uncertainty: 'qualified_clause', quotation: 'Buyer must pay unless approved.', source: { filename: 'A.pdf', page_number: 1 } }] } })
    }
    return route.fulfill({ json: {} })
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Collections', exact: true }).first().click()
  await page.getByRole('combobox', { name: 'Active collection' }).selectOption('project')
  const panel = page.getByRole('region', { name: 'Document comparison' })
  await panel.getByLabel('Use validated obligation comparison (bounded)').check()
  await panel.getByLabel('A.pdf · completed').check()
  await panel.getByLabel('B.pdf · completed').check()
  await panel.getByRole('button', { name: 'Compare selected documents' }).click()
  await expect(panel.getByText('Insufficient evidence', { exact: true })).toBeVisible()
  await panel.getByText('Review structured evidence facts (1)').click()
  await expect(panel.getByText(/qualified_clause/)).toBeVisible()
  expect(calls).toBe(1)
})

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
    await page.evaluate(() => window.scrollTo(0, 0))
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
  const pdf200 = Buffer.from(pdf.toString('binary').replaceAll('USD 100', 'USD 200'), 'binary')
  const hash200 = crypto.createHash('sha256').update(pdf200).digest('hex')
  const evidenceA = { ...source, filename: 'A.pdf', evidence_id: 'e1', content_sha256: hash200, excerpt: source.excerpt.replace('100', '200') }
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/content')) return route.fulfill({ contentType: 'application/pdf', body: path.includes(fileId) ? pdf200 : pdf })
    let body
    if (path === '/api/files') body = docs
    else if (path === '/api/collections') body = [{ id: 'project', name: 'Compare contracts', file_ids: [fileId, second], revision: 1 }]
    else if (path.endsWith('/compare')) {
      expect(route.request().postDataJSON().file_ids).toEqual([fileId, second])
      body = { schema_version: 1, summary: { supported_difference: 1 }, limitations: ['Retrieved evidence only; no full-document completeness claim.'], sources: [evidenceA, evidence], findings: [{ topic: 'Amount (USD)', classification: 'supported_difference', explanation: 'Explicit retrieved amounts differ; no contradiction established.', documents: [{ file_id: fileId, filename: 'A.pdf', facts: [{ values: ['200'], evidence_id: 'e1' }] }, { file_id: second, filename: 'B.pdf', facts: [{ values: ['100'], evidence_id: 'e2' }] }] }] }
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
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: 'test-results/comparison.png', fullPage: true })
  await panel.getByRole('button', { name: 'Open comparison B.pdf page 2' }).click()
  await expect(page.locator('canvas').first()).toBeVisible()
  await expect(page.getByRole('spinbutton', { name: 'Page number' })).toHaveValue('2')
  await expect(page.getByRole('region', { name: 'Selected evidence' })).toContainText(evidence.excerpt)
  await page.getByRole('button', { name: 'Back to collection' }).click()
  await expect(panel.getByText('Amount (USD)', { exact: true })).toBeVisible()
})

test('reviewed comparison can be saved, reopened stale, exported and deleted', async ({ page }) => {
  const second = '507f1f77bcf86cd799439012'
  const reportId = '507f1f77bcf86cd799439099'
  let saved = false
  const snapshot = { review_digest: 'a'.repeat(64), summary: {}, limitations: ['Bounded evidence only.'], findings: [], sources: [], method: 'literal_plus_verified_normalization_v1' }
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/files') return route.fulfill({ json: [{ _id: fileId, filename: 'A.pdf', status: 'completed' }, { _id: second, filename: 'B.pdf', status: 'completed' }] })
    if (path === '/api/collections') return route.fulfill({ json: [{ id: 'project', name: 'Reports', file_ids: [fileId, second], revision: 1 }] })
    if (path.endsWith('/compare-semantic')) return route.fulfill({ json: snapshot })
    if (path === '/api/comparison-reports/collection/project') {
      expect(route.request().postDataJSON()).toMatchObject({ reviewed: true, expected_digest: snapshot.review_digest, title: 'Reviewed payment' })
      saved = true
      return route.fulfill({ status: 201, json: { id: reportId, title: 'Reviewed payment' } })
    }
    if (path === '/api/comparison-reports') return route.fulfill({ json: saved ? [{ id: reportId, title: 'Reviewed payment' }] : [] })
    if (path.endsWith('/export')) {
      const format = new URL(route.request().url()).searchParams.get('format')
      return route.fulfill({ contentType: format === 'pdf' ? 'application/pdf' : 'application/json', body: format === 'pdf' ? pdf : JSON.stringify(snapshot) })
    }
    if (path === `/api/comparison-reports/${reportId}`) {
      if (route.request().method() === 'DELETE') { saved = false; return route.fulfill({ status: 204 }) }
      return route.fulfill({ json: { id: reportId, title: 'Reviewed payment', created_at: '2026-11-01', stale: true, snapshot } })
    }
    return route.fulfill({ json: {} })
  })
  await page.goto('/')
  await page.getByRole('button', { name: 'Collections', exact: true }).first().click()
  await page.getByRole('combobox', { name: 'Active collection' }).selectOption('project')
  const panel = page.getByRole('region', { name: 'Document comparison' })
  await panel.getByLabel('Use validated obligation comparison (bounded)').check()
  await panel.getByLabel('A.pdf · completed').check()
  await panel.getByLabel('B.pdf · completed').check()
  await panel.getByRole('button', { name: 'Compare selected documents' }).click()
  await panel.getByRole('textbox', { name: 'Report title' }).fill('Reviewed payment')
  await panel.getByLabel('I reviewed these findings and their limitations').check()
  await panel.getByRole('button', { name: 'Save reviewed comparison' }).click()
  await expect(panel.getByText(/Saved report: Reviewed payment/)).toBeVisible()
  const reports = page.getByRole('region', { name: 'Saved comparison reports' })
  await reports.getByRole('button', { name: 'Refresh saved reports' }).click()
  await reports.getByRole('button', { name: 'Open report: Reviewed payment' }).click()
  await expect(reports.getByText(/STALE: source revisions changed/)).toBeVisible()
  for (const format of ['JSON', 'PDF']) {
    const download = page.waitForEvent('download')
    await reports.getByRole('button', { name: `Export ${format}` }).click()
    expect((await download).suggestedFilename()).toBe(`documind-report-${reportId}.${format.toLowerCase()}`)
  }
  page.once('dialog', dialog => dialog.accept())
  await reports.getByRole('button', { name: 'Delete report: Reviewed payment' }).click()
  await expect(reports.getByRole('button', { name: 'Open report: Reviewed payment' })).toHaveCount(0)
})
