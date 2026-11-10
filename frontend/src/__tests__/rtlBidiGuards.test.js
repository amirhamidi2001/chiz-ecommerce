// Task 14.3.3.1 (RTL QA pass). Guards for three defects that a real RTL render exposed and
// that the class-name guards (rtlLogicalClasses / rtlDirectionalIcons) cannot see:
//  1. a phone number in an RTL paragraph is drawn scrambled ("+1 (234) 567-890" -> "567-890 (234) 1+");
//  2. an image-fade gradient is physical (bg-gradient-to-l) and fades the wrong edge in RTL;
//  3. email/url inputs push trailing punctuation to the wrong end ("a@b.com." -> ".a@b.com").
// Like its siblings this cannot prove a layout LOOKS right; it keeps these regressions out.
import { readFileSync, readdirSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const sourceFiles = readdirSync('src', { recursive: true })
  .map(String)
  .filter((f) => /\.(jsx?|tsx?)$/.test(f) && !/(^|[\\/])(__tests__|tests)[\\/]/.test(f));
const isComment = (line) => /^\s*(\/\/|\*|\/\*|\{\/\*)/.test(line);
const lines = (file) => readFileSync(`src/${file}`, 'utf8').split('\n');

describe('phone numbers are bidi-isolated', () => {
  // a literal like +1 (555) 123-4567 / 021-1234-5678 shown to the reader
  const PHONE = />\s*\+?\d[\d\s()-]{7,}\d\s*</;

  it('a phone literal sits in an element with dir="ltr" (an isolate)', () => {
    const bad = [];
    for (const file of sourceFiles) {
      lines(file).forEach((line, i) => {
        if (!isComment(line) && PHONE.test(line) && !/dir="ltr"|<bdi/.test(line)) bad.push(`${file}:${i + 1}`);
      });
    }
    expect(bad).toEqual([]);
  });

  it('the detector flags an unisolated number and accepts an isolated one', () => {
    expect(PHONE.test('<span>+1 (555) 123-4567</span>')).toBe(true);
    expect(PHONE.test('<span dir="ltr">+1 (555) 123-4567</span>')).toBe(true); // matched, then allowed by dir
    expect(PHONE.test('<span>3 items</span>')).toBe(false);
  });
});

describe('image-fade gradients flip in RTL', () => {
  it('every `from-transparent` gradient has an rtl: counterpart', () => {
    const bad = [];
    for (const file of sourceFiles) {
      lines(file).forEach((line, i) => {
        if (isComment(line)) return;
        if (/bg-gradient-to-(l|r)\b/.test(line) && /from-transparent/.test(line) && !/rtl:bg-gradient-to-/.test(line)) bad.push(`${file}:${i + 1}`);
      });
    }
    expect(bad).toEqual([]);
  });

  it('the hero background gradient (text on one side, image on the other) flips too', () => {
    expect(readFileSync('src/components/Hero.jsx', 'utf8')).toMatch(/bg-gradient-to-r rtl:bg-gradient-to-l/);
  });
});

describe('email and url inputs are laid out by their own content', () => {
  const css = readFileSync('src/index.css', 'utf8');
  it('index.css sets unicode-bidi: plaintext on type=email and type=url', () => {
    expect(css).toMatch(/input\[type="email"\][^{]*input\[type="url"\]\s*\{[^}]*unicode-bidi:\s*plaintext/s);
  });
  it('does not use dir="ltr" on those inputs (it flips logical padding under the field icon)', () => {
    const bad = [];
    for (const file of sourceFiles) {
      lines(file).forEach((line, i) => {
        if (/type=["'](email|url)["']/.test(line) && /dir=["']ltr["']/.test(line)) bad.push(`${file}:${i + 1}`);
      });
    }
    expect(bad).toEqual([]);
  });
});
