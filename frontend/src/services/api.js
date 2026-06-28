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

// Refine an existing report with follow-up feedback and the conversation so far.
export const refineReport = async ({ session_id, feedback, history, current_version }) => {
  const { data } = await api.post('/refine', {
    session_id,
    feedback,
    history,
    current_version,
  })

  return data
}

// Stream the built .xlsx for a download token and trigger a browser download.
export const downloadFile = async (token) => {
  const { data } = await api.get(`/download/${token}`, { responseType: 'blob' })

  const url = URL.createObjectURL(data)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'ExcelGPT_Report.xlsx'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export default api
