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
