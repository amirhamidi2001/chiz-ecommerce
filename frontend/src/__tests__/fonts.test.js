// Task 14.3.2.1: Vazirmatn is the site's self-hosted default typeface. This pins the parts
// that quietly rot: the download budget, font-display, the fallback stack, "no third-party
// font host", and the weight range the shipped file really covers. (Whether it RENDERS
// correctly was checked in a real browser: computed font-family, the font Chromium actually
// used per node, request sizes and the swap behaviour.)
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import tailwindConfig from '../../tailwind.config.js';

const css = readFileSync('src/index.css', 'utf8');
const html = readFileSync('index.html', 'utf8');
const size = (f) => statSync(`public/fonts/${f}`).size;
const faces = [...css.matchAll(/@font-face\s*\{([^}]*)\}/g)].map((m) => m[1]);
const vazirFaces = faces.filter((f) => /font-family:\s*'Vazirmatn'/.test(f));

describe('font files', () => {
  const woff2 = readdirSync('public/fonts').filter((f) => f.endsWith('.woff2'));

  it('ships the three script subsets as real WOFF2 files, plus the OFL licence text', () => {
    expect(woff2.sort()).toEqual([
      'vazirmatn-arabic-wght.woff2', 'vazirmatn-latin-ext-wght.woff2', 'vazirmatn-latin-wght.woff2',
    ]);
    for (const f of woff2) expect(readFileSync(`public/fonts/${f}`).subarray(0, 4).toString()).toBe('wOF2');
    expect(readFileSync('public/fonts/OFL.txt', 'utf8')).toMatch(/SIL Open Font License/);
  });

  it('keeps the per-page download small: Persian + Latin under 70 KB, everything under 100 KB', () => {
    // Persian+Latin is what every page fetches (~59 KB). The upstream full variable font
    // is 111 KB and a file per weight is ~50 KB EACH; this is the regression to avoid.
    expect(size('vazirmatn-arabic-wght.woff2') + size('vazirmatn-latin-wght.woff2')).toBeLessThan(70 * 1024);
    expect(woff2.reduce((sum, f) => sum + size(f), 0)).toBeLessThan(100 * 1024);
  });
});

describe('@font-face', () => {
  it('declares one Vazirmatn face per subset, each with a unicode-range', () => {
    expect(vazirFaces).toHaveLength(3);
    for (const f of vazirFaces) expect(f).toMatch(/unicode-range:\s*U\+/);
    expect(vazirFaces.map((f) => /vazirmatn-([\w-]+)-wght\.woff2/.exec(f)[1]).sort())
      .toEqual(['arabic', 'latin', 'latin-ext']);
  });

  it('uses font-display: swap (no invisible text while loading)', () => {
    for (const f of vazirFaces) expect(f).toMatch(/font-display:\s*swap/);
  });

  it('declares the weight range the file actually contains (400-700)', () => {
    for (const f of vazirFaces) expect(f).toMatch(/font-weight:\s*400 700/);
  });

  it('only references self-hosted files', () => {
    for (const f of vazirFaces) expect(f).toMatch(/url\('\/fonts\/vazirmatn-/);
    expect(css + html).not.toMatch(/fonts\.(googleapis|gstatic)\.com|use\.typekit|fontsource|jsdelivr[^"']*vazir/i);
  });
});

describe('default typeface', () => {
  it('makes Vazirmatn the default sans stack, with a fallback chain', () => {
    const sans = tailwindConfig.theme.extend.fontFamily.sans;
    expect(sans).toEqual(['Vazirmatn', 'Tahoma', 'system-ui', 'sans-serif']);
  });

  it('preloads the two files every page needs (with crossorigin), and not Latin-extended', () => {
    const preloads = [...html.matchAll(/<link rel="preload"[^>]*>/g)].map((m) => m[0]);
    expect(preloads).toHaveLength(2);
    for (const p of preloads) {
      expect(p).toMatch(/as="font"/);
      expect(p).toMatch(/type="font\/woff2"/);
      expect(p).toMatch(/\bcrossorigin\b/);
    }
    expect(preloads.join('')).toMatch(/vazirmatn-arabic-wght/);
    expect(preloads.join('')).toMatch(/vazirmatn-latin-wght/);
    expect(preloads.join('')).not.toMatch(/latin-ext/);
  });
});

describe('weights used by the UI are weights the font file covers', () => {
  const sourceFiles = readdirSync('src', { recursive: true })
    .map(String)
    .filter((f) => /\.(jsx?|tsx?)$/.test(f) && !/(^|[\\/])(__tests__|tests)[\\/]/.test(f));

  it('uses no font-thin / extralight / light / extrabold / black (outside 400-700 they would silently clamp)', () => {
    const offenders = [];
    for (const file of sourceFiles) {
      readFileSync(`src/${file}`, 'utf8').split('\n').forEach((line, i) => {
        if (/(?<![\w-])font-(thin|extralight|light|extrabold|black)(?![\w-])/.test(line)) offenders.push(`${file}:${i + 1}`);
      });
    }
    // If this fails on purpose, widen the range together: WGHT in scripts/build-fonts.sh,
    // `font-weight` in src/index.css, and this test.
    expect(offenders).toEqual([]);
  });
});
