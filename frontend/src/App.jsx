import { useState } from 'react'
import './index.css'
import UploadView from './components/UploadView'
import ChatView from './components/ChatView'
import { analyseInstruction, downloadAll, downloadFile } from './services/api'

// ExcelGPT — conversational data decision guide.
// Upload an Excel file, then ask questions one at a time; each answer becomes an
// insight card in the chat. Chat history persists while the same file is loaded.
export default function App() {
  const [file, setFile] = useState(null) // { name, rowCount, sheetCount, sessionId, intelligenceBrief }
  const [chatHistory, setChatHistory] = useState([]) // [{ id, question, answer, downloadToken, error, timestamp }]
  const [isThinking, setIsThinking] = useState(false)
  const [inputValue, setInputValue] = useState('')

  const handleFileUpload = (rawFile, response) => {
    const sheets = response?.preview?.sheets || []
    const rowCount = sheets.reduce((sum, s) => sum + (s?.row_count || 0), 0)
    setFile({
      name: rawFile?.name || response?.intelligence_brief?.filename || 'workbook.xlsx',
      rowCount,
      sheetCount: sheets.length,
      sessionId: response.session_id,
      intelligenceBrief: response.intelligence_brief,
    })
    setChatHistory([])
    setInputValue('')
  }

  const handleQuestion = async (question) => {
    if (!file?.sessionId || isThinking) return
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    setChatHistory((prev) => [
      ...prev,
      { id, question, answer: null, downloadToken: null, error: null, timestamp: Date.now() },
    ])
    setInputValue('')
    setIsThinking(true)

    try {
      const data = await analyseInstruction(file.sessionId, question)
      setChatHistory((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, answer: data, downloadToken: data.download_token || null } : item,
        ),
      )
    } catch (err) {
      const message =
        err?.errorKey === 'CEREBRAS_TIMEOUT'
          ? 'That took longer than expected. Please try asking again.'
          : err?.errorKey === 'SESSION_EXPIRED'
            ? 'Your session expired — please re-upload your file.'
            : 'Something went wrong analysing that. Try rephrasing your question.'
      setChatHistory((prev) => prev.map((item) => (item.id === id ? { ...item, error: message } : item)))
    } finally {
      setIsThinking(false)
    }
  }

  const handleChangeFile = () => {
    setFile(null)
    setChatHistory([])
    setInputValue('')
    setIsThinking(false)
  }

  const handleDownloadOne = (token) => downloadFile(token)

  const handleDownloadAll = (tokens) => downloadAll(tokens)

  if (!file) {
    return <UploadView onUpload={handleFileUpload} />
  }

  return (
    <ChatView
      file={file}
      chatHistory={chatHistory}
      isThinking={isThinking}
      inputValue={inputValue}
      onInputChange={setInputValue}
      onSubmit={handleQuestion}
      onChangeFile={handleChangeFile}
      onDownloadOne={handleDownloadOne}
      onDownloadAll={handleDownloadAll}
    />
  )
}
