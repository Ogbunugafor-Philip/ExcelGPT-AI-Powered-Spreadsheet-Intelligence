import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8003',
  timeout: 120000,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error?.response?.data?.detail || error?.message || 'Request failed.'
    return Promise.reject(new Error(message))
  },
)

export const uploadFile = async (file) => {
  const formData = new FormData()
  formData.append('file', file)

  const { data } = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

  return data
}

export const analyseInstruction = async (sessionId, instruction) => {
  const { data } = await api.post('/analyse', {
    session_id: sessionId,
    instruction,
  })

  return data
}

export default api
