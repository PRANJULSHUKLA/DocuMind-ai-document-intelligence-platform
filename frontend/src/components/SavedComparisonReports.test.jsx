import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, test, expect } from 'vitest'
import SavedComparisonReports from './SavedComparisonReports'
import * as reports from '../services/reportService'
vi.mock('../services/reportService', () => ({ listReports: vi.fn(), readReport: vi.fn(), deleteReport: vi.fn(), downloadReport: vi.fn() }))

test('saved snapshot shows stale state, linked evidence and export actions', async () => {
  const user = userEvent.setup(), open = vi.fn()
  const source = { evidence_id: 'f1', filename: 'A.pdf', page_number: 1, excerpt: 'Exact sentence.' }
  reports.listReports.mockResolvedValue([{ id: 'r1', title: 'Reviewed payment' }])
  reports.readReport.mockResolvedValue({ id: 'r1', title: 'Reviewed payment', created_at: '2026-11-01', stale: true, snapshot: { method: 'bounded', limitations: ['No completeness claim.'], findings: [], sources: [source] } })
  render(<SavedComparisonReports onSourceSelect={open} />)
  await user.click(await screen.findByRole('button', { name: 'Open report: Reviewed payment' }))
  await screen.findByText(/STALE: source revisions changed/)
  await user.click(screen.getByRole('button', { name: 'Export JSON' }))
  expect(reports.downloadReport).toHaveBeenCalledWith('r1', 'json')
  await user.click(screen.getByText('Saved evidence passages'))
  await user.click(screen.getByRole('button', { name: /A.pdf/ }))
  expect(open).toHaveBeenCalledWith(source)
})

test('failed export shows the safe server explanation', async () => {
  const user = userEvent.setup()
  reports.listReports.mockResolvedValue([{ id: 'r2', title: 'Report' }])
  reports.readReport.mockResolvedValue({ id: 'r2', title: 'Report', stale: false, snapshot: { method: 'bounded', limitations: [], findings: [], sources: [] } })
  reports.downloadReport.mockRejectedValue({ response: { data: { detail: 'Source access lost.' } } })
  render(<SavedComparisonReports onSourceSelect={vi.fn()} />)
  await user.click(await screen.findByRole('button', { name: 'Open report: Report' }))
  await user.click(await screen.findByRole('button', { name: 'Export PDF' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Source access lost.')
})
