import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, test, expect } from 'vitest'
import ComparisonPanel from './ComparisonPanel'
import { compareCollection } from '../services/collectionService'
import { saveReport } from '../services/reportService'
vi.mock('../services/collectionService', () => ({ compareCollection: vi.fn() }))
vi.mock('../services/reportService', () => ({ saveReport: vi.fn() }))
test('requires two documents and renders evidence-backed conservative findings', async () => {
  const user = userEvent.setup(), open = vi.fn()
  const source = { evidence_id: 'e1', file_id: 'a', filename: 'A.pdf', page_number: 1, excerpt: 'USD 100.' }
  compareCollection.mockResolvedValue({ summary: { supported_difference: 1 }, limitations: ['Bounded evidence only.'], sources: [source], findings: [{ topic: 'Amount (USD)', classification: 'supported_difference', explanation: 'Explicit values differ.', documents: [{ file_id: 'a', filename: 'A.pdf', facts: [{ values: ['100'], evidence_id: 'e1' }] }, { file_id: 'b', filename: 'B.pdf', facts: [] }] }] })
  render(<ComparisonPanel collectionId="project" documents={[{ _id: 'a', filename: 'A.pdf', status: 'completed' }, { _id: 'b', filename: 'B.pdf', status: 'completed' }]} onSourceSelect={open} />)
  expect(screen.getByRole('button', { name: 'Compare selected documents' })).toBeDisabled()
  await user.click(screen.getByLabelText('A.pdf · completed'))
  await user.click(screen.getByLabelText('B.pdf · completed'))
  await user.click(screen.getByRole('button', { name: 'Compare selected documents' }))
  await screen.findByText('Supported difference', { exact: true })
  await user.click(screen.getByRole('button', { name: 'Open comparison A.pdf page 1' }))
  expect(open).toHaveBeenCalledWith(source)
  expect(screen.getByText(/Full-document absence is unverified/)).toBeVisible()
})

test('bounded semantic mode is explicit and shows structured evidence and limits', async () => {
  const user = userEvent.setup()
  compareCollection.mockResolvedValue({ summary: {}, limitations: [], sources: [], findings: [], extraction_limitations: [{ file_id: 'a', reason: 'chunk_limit_reached' }], extracted_facts: [{ fact_id: 'f1', kind: 'amount', value: { amount: '100', currency: 'USD' }, uncertainty: 'literal_only', quotation: 'USD 100.', source: { filename: 'A.pdf', page_number: 1 } }] })
  render(<ComparisonPanel collectionId="project" documents={[{ _id: 'a', filename: 'A.pdf', status: 'completed' }, { _id: 'b', filename: 'B.pdf', status: 'completed' }]} onSourceSelect={vi.fn()} />)
  await user.click(screen.getByLabelText('Use validated obligation comparison (bounded)'))
  await user.click(screen.getByLabelText('A.pdf · completed'))
  await user.click(screen.getByLabelText('B.pdf · completed'))
  await user.click(screen.getByRole('button', { name: 'Compare selected documents' }))
  await screen.findByText(/Some evidence was skipped/)
  expect(compareCollection.mock.lastCall[4]).toBe(true)
  await user.click(screen.getByText('Review structured evidence facts (1)'))
  expect(screen.getByText(/literal_only/)).toBeVisible()
})

test('saving uses the reviewed server digest and requires a title and confirmation', async () => {
  const user = userEvent.setup()
  compareCollection.mockResolvedValue({ review_digest: 'a'.repeat(64), summary: {}, limitations: [], sources: [], findings: [] })
  saveReport.mockResolvedValue({ title: 'Reviewed payment' })
  render(<ComparisonPanel collectionId="project" documents={[{ _id: 'a', filename: 'A.pdf', status: 'completed' }, { _id: 'b', filename: 'B.pdf', status: 'completed' }]} onSourceSelect={vi.fn()} />)
  await user.click(screen.getByLabelText('Use validated obligation comparison (bounded)'))
  await user.click(screen.getByLabelText('A.pdf · completed'))
  await user.click(screen.getByLabelText('B.pdf · completed'))
  await user.click(screen.getByRole('button', { name: 'Compare selected documents' }))
  await user.type(await screen.findByRole('textbox', { name: 'Report title' }), 'Reviewed payment')
  await user.click(screen.getByLabelText('I reviewed these findings and their limitations'))
  await user.click(screen.getByRole('button', { name: 'Save reviewed comparison' }))
  await screen.findByText(/Saved report: Reviewed payment/)
  expect(saveReport).toHaveBeenCalledWith('project', expect.objectContaining({ reviewed: true, expected_digest: 'a'.repeat(64), file_ids: ['a', 'b'] }))
})
