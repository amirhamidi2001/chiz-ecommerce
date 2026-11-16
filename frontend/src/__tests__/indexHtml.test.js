// Task 14.3.1.1: the root document must be Persian / RTL. Reads the real
// index.html, the file Vite serves, and checks what a browser would put on
// document.documentElement (the dev-tools check from the task, automated).
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const html = readFileSync('index.html', 'utf8'); // vitest runs from the frontend/ root;
const doc = new DOMParser().parseFromString(html, 'text/html');

describe('index.html root element', () => {
  it('is Persian, right-to-left', () => {
    expect(doc.documentElement.lang).toBe('fa');
    expect(doc.documentElement.dir).toBe('rtl');
  });

  it('still has the app mount point and entry script', () => {
    expect(doc.getElementById('root')).not.toBeNull();
    expect(doc.querySelector('script[type="module"][src="/src/main.jsx"]')).not.toBeNull();
  });
});

// Task 15.1.1.1: index.html's <title> only shows for the instant before React hydrates
// (react-helmet-async then adds the real one). It must be the Persian default, not the old
// English "Chiz E-Commerce" placeholder, or that would flash on every page load.
describe('index.html pre-hydration metadata', () => {
  it('has the Persian default title from constants/seo.js', async () => {
    const { DEFAULT_TITLE } = await import('../constants/seo');
    expect(doc.title).toBe(DEFAULT_TITLE);
    expect(doc.title).not.toMatch(/E-Commerce/i);
  });

  it('has no static meta description (it would duplicate the per-page one at runtime)', () => {
    expect(doc.querySelector('meta[name="description"]')).toBeNull();
  });
});
