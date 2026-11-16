import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { robotsPlugin } from './robots.js'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), robotsPlugin()],
})
