import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Requests to /api go to the Flask backend (port 5001, since macOS uses 5000 for AirPlay).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:5001' } },
})
