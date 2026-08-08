// src/__tests__/setup.js
import '@testing-library/jest-dom';

// ── localStorage stub ──────────────────────────────────────────────────────
// jsdom provides localStorage, but we reset it before every test so
// token-related state never leaks between specs.
beforeEach(() => {
  localStorage.clear();
});

// ── Suppress React act() warnings triggered by async state updates ─────────
// These are harmless in test output but noisy. Re-enable if debugging renders.
const originalError = console.error.bind(console);
beforeAll(() => {
  console.error = (...args) => {
    if (
      typeof args[0] === 'string' &&
      (args[0].includes('act(') || args[0].includes('not wrapped in act'))
    ) {
      return;
    }
    originalError(...args);
  };
});
afterAll(() => {
  console.error = originalError;
});
