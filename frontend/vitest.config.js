// vitest.config.js
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,                         // no need to import describe/it/expect
    setupFiles: ['./src/__tests__/setup.js'],
    clearMocks: true,                      // reset mocks between tests automatically
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov'],
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/__tests__/**', 'src/main.jsx'],
    },
  },
});

/*
Install required dev dependencies:
  npm install -D vitest @vitest/coverage-v8 jsdom \
    @testing-library/react @testing-library/user-event \
    @testing-library/jest-dom @vitejs/plugin-react
*/
