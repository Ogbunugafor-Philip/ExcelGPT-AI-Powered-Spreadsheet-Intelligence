// Friendly, actionable copy for every error scenario ExcelGPT can hit.
// api.js attaches one of these keys to thrown errors (err.errorKey); components
// look the key up here to render a helpful message instead of a raw stack.

export const ERROR_MESSAGES = {
  FILE_TOO_LARGE: {
    title: 'File is too large',
    message: 'Your file exceeds 50MB. Try splitting it into smaller sheets or removing unused data.',
    action: 'Choose a different file',
  },
  INVALID_FILE_TYPE: {
    title: 'Wrong file type',
    message: 'ExcelGPT only works with Excel files (.xlsx or .xls). CSV files need to be converted first.',
    action: 'Upload an Excel file',
  },
  EMPTY_FILE: {
    title: 'File appears empty',
    message: 'Your file has no data rows. Make sure your spreadsheet has content before uploading.',
    action: 'Check your file and try again',
  },
  CEREBRAS_TIMEOUT: {
    title: 'Processing with smart fallback',
    message: 'Your instruction was complex. ExcelGPT used its built-in intelligence to analyse your data. The results cover all key areas requested.',
    action: 'View results',
  },
  CEREBRAS_CLARIFICATION: {
    title: 'Need a bit more detail',
    message: null, // use the clarification_question from the response
    action: 'Answer the question above',
  },
  COMPUTATION_ERROR: {
    title: 'Could not compute that',
    message: 'Something went wrong during analysis. This can happen with unusual data formats. Try rephrasing your instruction.',
    action: 'Rephrase and try again',
  },
  SESSION_EXPIRED: {
    title: 'Session expired',
    message: 'Your upload session has expired after inactivity. Please upload your file again.',
    action: 'Start over',
  },
  DOWNLOAD_FAILED: {
    title: 'Download failed',
    message: 'Could not prepare your Excel file. Please try downloading again.',
    action: 'Try downloading again',
  },
  NETWORK_ERROR: {
    title: 'Connection problem',
    message: 'Could not reach the ExcelGPT server. Check your internet connection and try again.',
    action: 'Retry',
  },
  UNKNOWN: {
    title: 'Something went wrong',
    message: 'An unexpected error occurred. Please try again or start fresh.',
    action: 'Try again',
  },
}

// Resolve a key (falling back to UNKNOWN) and apply any custom message override.
export const resolveError = (errorKey, customMessage) => {
  const base = ERROR_MESSAGES[errorKey] || ERROR_MESSAGES.UNKNOWN
  return { ...base, message: customMessage || base.message || ERROR_MESSAGES.UNKNOWN.message }
}

export default ERROR_MESSAGES
