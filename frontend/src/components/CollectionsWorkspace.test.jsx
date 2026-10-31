import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, test, expect } from 'vitest'
import CollectionsWorkspace from './CollectionsWorkspace'
import * as collections from '../services/collectionService'
import * as documents from '../services/documentService'
vi.mock('../services/collectionService', () => ({ listCollections: vi.fn(), createCollection: vi.fn(), editCollection: vi.fn(), deleteCollection: vi.fn(), askCollection: vi.fn() }))
vi.mock('../services/documentService', () => ({ getDocuments: vi.fn(), getDocumentView: vi.fn(), uploadDocument: vi.fn() }))
vi.mock('./DocumentWorkspace', () => ({ default: () => <div>Reader</div> }))

test('creates collection and preserves independent upload failures', async () => {
  collections.listCollections.mockResolvedValue([])
  collections.createCollection.mockResolvedValue({ id: 'c1' })
  documents.getDocuments.mockResolvedValue([])
  documents.uploadDocument.mockResolvedValueOnce({ status: 'queued' }).mockRejectedValueOnce(new Error('failed'))
  const user = userEvent.setup()
  render(<CollectionsWorkspace />)
  await screen.findByText('No collections yet. Create one to start.')
  await user.type(screen.getByLabelText('New collection name'), 'Contracts')
  await user.click(screen.getByRole('button', { name: 'Create collection' }))
  await waitFor(() => expect(collections.createCollection).toHaveBeenCalledWith('Contracts'))
  const files = [new File(['pdf'], 'one.pdf', { type: 'application/pdf' }), new File(['pdf'], 'two.pdf', { type: 'application/pdf' })]
  await user.upload(screen.getByLabelText('Upload multiple PDFs'), files)
  await screen.findByText('one.pdf: queued')
  await screen.findByText(/two.pdf: failed/)
  expect(documents.uploadDocument).toHaveBeenCalledTimes(2)
})
