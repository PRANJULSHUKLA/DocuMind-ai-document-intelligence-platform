import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import App from './App'
import { getDocuments } from './services/documentService'

vi.mock('./components/DocumentWorkspace', () => ({ default: ({ document }) => <div>{document.filename}</div> }))

vi.mock('./services/documentService', () => ({
  getDocuments: vi.fn(),
  getDocumentStatus: vi.fn(),
  analyzeDocument: vi.fn(),
  generateWorkflow: vi.fn(),
}))

vi.mock('./components/UploadDocument', () => ({
  default: ({ onUploaded }) => (
    <button onClick={() => onUploaded({ file_id: '507f1f77bcf86cd799439011', filename: 'new-contract.pdf', status: 'completed' })}>
      Complete test upload
    </button>
  ),
}))

beforeEach(() => {
  getDocuments.mockReset().mockResolvedValue([])
})

test('completed upload selects the document and refreshes the document library', async () => {
  const user = userEvent.setup()
  render(<App />)
  await waitFor(() => expect(getDocuments).toHaveBeenCalledTimes(1))
  await user.click(screen.getAllByRole('button', { name: 'Documents' })[0])
  await user.click(screen.getByRole('button', { name: 'Complete test upload' }))
  await waitFor(() => expect(getDocuments).toHaveBeenCalledTimes(2))
  expect(screen.getAllByText('new-contract.pdf').length).toBeGreaterThan(0)
})

test('document-list failures give the user a visible error', async () => {
  getDocuments.mockRejectedValue(new Error('Backend unavailable'))
  render(<App />)
  expect(await screen.findByText('Backend unavailable')).toBeInTheDocument()
})
