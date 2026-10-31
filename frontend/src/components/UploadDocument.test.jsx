import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import UploadDocument from './UploadDocument'
import { uploadDocument, getDocumentStatus, retryDocumentProcessing } from '../services/documentService'

vi.mock('../services/documentService', () => ({
  uploadDocument: vi.fn(), getDocumentStatus: vi.fn(), retryDocumentProcessing: vi.fn(),
}))

beforeEach(() => {
  uploadDocument.mockReset()
  getDocumentStatus.mockReset()
  retryDocumentProcessing.mockReset()
})

test('a failed dispatch retries the saved document without a second upload', async () => {
  const user = userEvent.setup()
  const onUploaded = vi.fn()
  uploadDocument.mockRejectedValue({ response: { data: { file_id: 'saved-document', message: 'Document saved, but processing is not queued.' } } })
  retryDocumentProcessing.mockResolvedValue({ file_id: 'saved-document' })
  getDocumentStatus.mockResolvedValue({ status: 'completed' })
  const { container } = render(<UploadDocument onUploaded={onUploaded} />)
  await user.upload(container.querySelector('input[type=file]'), new File(['%PDF-1.7'], 'contract.pdf', { type: 'application/pdf' }))
  await user.click(screen.getByRole('button', { name: 'Start analysis' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Document saved')
  await user.click(screen.getByRole('button', { name: 'Retry processing saved PDF' }))
  await waitFor(() => expect(onUploaded).toHaveBeenCalled())
  expect(uploadDocument).toHaveBeenCalledTimes(1)
  expect(retryDocumentProcessing).toHaveBeenCalledWith('saved-document')
  expect(onUploaded.mock.calls[0][0].file_id).toBe('saved-document')
})

test('an ambiguous accepted upload polls its existing ID without reuploading', async () => {
  uploadDocument.mockResolvedValue({ file_id: 'pending-document', enqueue_state: 'uncertain' })
  getDocumentStatus.mockResolvedValue({ status: 'completed' })
  const onUploaded = vi.fn()
  const user = userEvent.setup()
  const { container } = render(<UploadDocument onUploaded={onUploaded} />)
  await user.upload(container.querySelector('input[type=file]'), new File(['%PDF-1.7'], 'contract.pdf', { type: 'application/pdf' }))
  await user.click(screen.getByRole('button', { name: 'Start analysis' }))
  await waitFor(() => expect(onUploaded).toHaveBeenCalled())
  expect(getDocumentStatus).toHaveBeenCalledWith('pending-document')
  expect(uploadDocument).toHaveBeenCalledTimes(1)
})

test('unconfirmed polling performs bounded recovery on the saved ID', async () => {
  vi.useFakeTimers()
  try {
    uploadDocument.mockResolvedValue({ file_id: 'pending-document', enqueue_state: 'uncertain' })
    getDocumentStatus.mockResolvedValue({ status: 'queued', enqueue_state: 'uncertain' })
    retryDocumentProcessing.mockImplementation(async () => {
      getDocumentStatus.mockResolvedValue({ status: 'completed' })
      return { file_id: 'pending-document' }
    })
    const onUploaded = vi.fn()
    const { container } = render(<UploadDocument onUploaded={onUploaded} />)
    fireEvent.change(container.querySelector('input[type=file]'), { target: { files: [new File(['%PDF-1.7'], 'contract.pdf', { type: 'application/pdf' })] } })
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Start analysis' })) })
    await act(async () => { await vi.advanceTimersByTimeAsync(20000) })
    expect(retryDocumentProcessing).toHaveBeenCalledExactlyOnceWith('pending-document')
    expect(uploadDocument).toHaveBeenCalledTimes(1)
    expect(onUploaded).toHaveBeenCalledTimes(1)
  } finally {
    vi.useRealTimers()
  }
})
