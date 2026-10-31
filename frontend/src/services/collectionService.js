import api from './api'
export const listCollections = async () => (await api.get('/collections')).data
export const createCollection = async name => (await api.post('/collections', { name })).data
export const editCollection = async (id, fields) => (await api.patch(`/collections/${id}`, fields)).data
export const deleteCollection = async id => api.delete(`/collections/${id}`)
export const askCollection = async (id, question, file_ids) => (await api.post(`/collections/${id}/chat`, { question, file_ids })).data
export const compareCollection = async (id, file_ids, focus, signal) => (await api.post(`/collections/${id}/compare`, { file_ids, focus }, { signal })).data
