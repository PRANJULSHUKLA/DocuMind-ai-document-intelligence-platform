import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, test, expect } from 'vitest'
import ComparisonPanel from './ComparisonPanel'
import { compareCollection } from '../services/collectionService'
vi.mock('../services/collectionService', () => ({ compareCollection: vi.fn() }))
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
