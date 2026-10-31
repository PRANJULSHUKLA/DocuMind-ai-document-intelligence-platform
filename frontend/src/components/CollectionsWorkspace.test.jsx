import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi, test, expect } from 'vitest'
import CollectionsWorkspace from './CollectionsWorkspace'
import * as collections from '../services/collectionService'
import * as documents from '../services/documentService'
vi.mock('../services/collectionService', () => ({ listCollections: vi.fn(), createCollection: vi.fn(), editCollection: vi.fn(), deleteCollection: vi.fn(), askCollection: vi.fn() }))
vi.mock('../services/documentService', () => ({ getDocuments: vi.fn(), getDocumentView: vi.fn(), uploadDocument: vi.fn() }))
vi.mock('./DocumentWorkspace', () => ({ default: () => <div>Reader</div> }))
vi.mock('../services/reportService', () => ({ listReports: vi.fn().mockResolvedValue([]) }))

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


test('collection forms and comparison panels have distinct sibling keys', async () => {
  const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
  collections.listCollections.mockResolvedValue([{ id: 'project', name: 'Contracts', file_ids: [], revision: 2 }])
  documents.getDocuments.mockResolvedValue([])
  const user = userEvent.setup()
  try {
    render(<CollectionsWorkspace />)
    await screen.findByRole('option', { name: 'Contracts' })
    await user.selectOptions(screen.getByRole('combobox', { name: 'Active collection' }), 'project')
    await screen.findByRole('region', { name: 'Document comparison' })
    expect(screen.getAllByRole('button', { name: 'Rename', exact: true })).toHaveLength(1)
    expect(errors.mock.calls.filter(call => String(call[0]).includes('same key'))).toEqual([])
  } finally { errors.mockRestore() }
})
