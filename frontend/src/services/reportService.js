import api from './api'
export const listReports = async () => (await api.get('/comparison-reports')).data
export const readReport = async id => (await api.get(`/comparison-reports/${id}`)).data
export const deleteReport = async id => api.delete(`/comparison-reports/${id}`)
export const saveReport = async (collectionId, body) => (await api.post(`/comparison-reports/collection/${collectionId}`, body)).data
export async function downloadReport(id, format) {
  let response
  try { response = await api.get(`/comparison-reports/${id}/export`, { params: { format }, responseType: 'blob' }) }
  catch (failure) {
    if (failure.response?.data instanceof Blob) {
      try { failure.response.data = JSON.parse(await failure.response.data.text()) } catch { /* Preserve the original failure. */ }
    }
    throw failure
  }
  const url = URL.createObjectURL(response.data)
  const anchor = document.createElement('a')
  anchor.href = url; anchor.download = `documind-report-${id}.${format}`
  document.body.appendChild(anchor); anchor.click(); anchor.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
