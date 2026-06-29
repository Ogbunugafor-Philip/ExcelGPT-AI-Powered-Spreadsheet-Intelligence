import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8003',
  // 100s: the backend's 3-tier planner worst case (~81s) finishes well before
  // this, so the rule-based fallback always reaches the user instead of the
  // browser cancelling the request mid-flight.
  timeout: 100000,
})

// Map an axios error to one of our friendly ERROR_MESSAGES keys (see
// utils/errorMessages.js). URL-aware so the same status reads correctly per route.
const classifyError = (error) => {
  const url = error?.config?.url || ''
  const status = error?.response?.status
  const isUpload = url.includes('/upload')
  const isDownload = url.includes('/download')
  const isAI = url.includes('/analyse') || url.includes('/refine')

  if (!error.response) {
    if (error.code === 'ECONNABORTED') return isAI ? 'CEREBRAS_TIMEOUT' : 'NETWORK_ERROR'
    return 'NETWORK_ERROR'
  }
  switch (status) {
    case 413: return 'FILE_TOO_LARGE'
    case 400: return isUpload ? 'INVALID_FILE_TYPE' : 'COMPUTATION_ERROR'
    case 422: return isUpload ? 'EMPTY_FILE' : 'COMPUTATION_ERROR'
    case 404: return isDownload ? 'DOWNLOAD_FAILED' : 'SESSION_EXPIRED'
    case 410: return 'SESSION_EXPIRED'
    case 500: return isDownload ? 'DOWNLOAD_FAILED' : 'COMPUTATION_ERROR'
    case 502:
    case 503:
    case 504: return 'CEREBRAS_TIMEOUT'
    default: return 'UNKNOWN'
  }
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error?.response?.data?.detail || error?.message || 'Request failed.'
    const normalised = new Error(message)
    normalised.errorKey = classifyError(error)
    normalised.status = error?.response?.status
    return Promise.reject(normalised)
  },
)

export const uploadFile = async (file, onProgress) => {
  const formData = new FormData()
  formData.append('file', file)

  const { data } = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => {
      if (!onProgress) return
      const percent = event.total ? Math.round((event.loaded * 100) / event.total) : 0
      onProgress(percent)
    },
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

// Poll processing status for a session (used for large-file background reads).
export const getStatus = async (sessionId) => {
  const { data } = await api.get(`/status/${sessionId}`)
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
