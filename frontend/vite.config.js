import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Registers @vitejs/plugin-react so JSX uses the automatic runtime (no need to
// import React in every file) and Fast Refresh works. Without this config Vite
// falls back to esbuild's classic transform (React.createElement), which throws
// "React is not defined" at runtime and blanks the app.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // bind 0.0.0.0 so the dev server is reachable over the network
    port: 5173,
  },
})
