// Task 14.3.1.2: the site is Persian / RTL (index.html: dir="rtl"), so direction-relative
// spacing and positioning must use Tailwind's LOGICAL utilities (ms-/me-/ps-/pe-/start-/
// end-/text-start/text-end/border-s/border-e/rounded-s/e...), which flip with `dir`, not
// the physical ones (ml-/mr-/pl-/pr-/left-/right-/text-left/text-right/border-l/border-r/
// rounded-l/r...), which do not. This cannot prove a layout LOOKS right; it stops the
// physical classes creeping back in and keeps the intentional exceptions explicit.
import { readFileSync, readdirSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const UTILS = [
  'text-left', 'text-right', 'border-l', 'border-r', 'rounded-tl', 'rounded-tr', 'rounded-bl',
  'rounded-br', 'rounded-l', 'rounded-r', 'ml', 'mr', 'pl', 'pr', 'left', 'right',
];
const NEEDS_VALUE = new Set(['ml', 'mr', 'pl', 'pr', 'left', 'right']);
// A class token: not preceded by a word char, "/", "." or "-" (so icon names such as
// bi-chevron-left and bi-text-left are NOT matched), optional variants (md:, hover:...).
const TOKEN = new RegExp(
  String.raw`(?<![\w/.-])((?:[\w\[\]&>*=:.#-]+:)*)(!?)(-?)(` + UTILS.join('|') +
    String.raw`)(?:-([\w./\[\]%#-]+))?(?![\w-])`,
  'g',
);

/** Physical-direction class tokens on one line, minus the documented exceptions. */
export function physicalTokens(line) {
  const found = [];
  for (const m of line.matchAll(TOKEN)) {
    const [token, , , , util, value] = m;
    if (NEEDS_VALUE.has(util) && value === undefined) continue; // the bare word "left"/"right"
    // EXCEPTION: left-/right- paired with a physical translate-x (centering with
    // left-1/2 -translate-x-1/2, decorative corner blobs) must stay physical, because
    // the translate is physical and a logical offset would then move the wrong way.
    if ((util === 'left' || util === 'right') && /translate-x/.test(line)) continue;
    found.push(token);
  }
  return found;
}

/** `space-x-N` puts its gap on a physical side, so it needs `rtl:space-x-reverse`. */
export function unreversedSpaceX(line) {
  return /(?<![\w-])space-x-[\w.]+/.test(line) && !/rtl:space-x-reverse/.test(line);
}

// Prose in comments ("isolated left-to-right") is not a class, so comment lines are skipped.
const isComment = (line) => /^\s*(\/\/|\*|\/\*|\{\/\*)/.test(line);

const sourceFiles = readdirSync('src', { recursive: true })
  .map(String)
  .filter((f) => /\.(jsx?|tsx?)$/.test(f) && !/(^|[\\/])(__tests__|tests)[\\/]/.test(f));

describe('RTL: no physical-direction Tailwind classes in src', () => {
  it('scans a meaningful number of files', () => {
    expect(sourceFiles.length).toBeGreaterThan(60);
  });

  it('uses logical utilities only (apart from documented translate-x pairs)', () => {
    const offenders = [];
    for (const file of sourceFiles) {
      readFileSync(`src/${file}`, 'utf8').split('\n').forEach((line, i) => {
        if (isComment(line)) return;
        const hits = physicalTokens(line);
        if (hits.length) offenders.push(`${file}:${i + 1}: ${hits.join(' ')}`);
      });
    }
    expect(offenders).toEqual([]);
  });

  it('every space-x-* also has rtl:space-x-reverse', () => {
    const offenders = [];
    for (const file of sourceFiles) {
      readFileSync(`src/${file}`, 'utf8').split('\n').forEach((line, i) => {
        if (unreversedSpaceX(line)) offenders.push(`${file}:${i + 1}`);
      });
    }
    expect(offenders).toEqual([]);
  });
});

describe('the detector itself', () => {
  it.each([
    ['ml-2', ['ml-2']],
    ['-mr-3 md:pl-4 hover:left-0', ['-mr-3', 'md:pl-4', 'hover:left-0']],
    ['text-left md:text-right', ['text-left', 'md:text-right']],
    ['border-l-4 border-l-teal-600 rounded-r-lg rounded-br-sm', ['border-l-4', 'border-l-teal-600', 'rounded-r-lg', 'rounded-br-sm']],
    ['before:-right-3 after:left-[2px]', ['before:-right-3', 'after:left-[2px]']],
  ])('flags %s', (line, expected) => {
    expect(physicalTokens(`className="${line}"`)).toEqual(expected);
  });

  it.each([
    'ms-2 me-auto ps-4 pe-4 start-0 end-3 -start-4 text-start text-end',
    'border-s-4 border-e rounded-s-lg rounded-ee-sm',
    'bi bi-chevron-left bi-text-left bi-arrow-right', // icon names are not utilities
    'rtl:space-x-reverse',
    'absolute left-1/2 -translate-x-1/2', // centering: physical on purpose
  ])('does not flag %s', (line) => {
    expect(physicalTokens(`className="${line}"`)).toEqual([]);
  });

  it('treats comment lines as prose, not classes', () => {
    expect(isComment('// isolated left-to-right (found by the QA pass)')).toBe(true);
    expect(isComment('   * text-left is only mentioned here')).toBe(true);
    expect(isComment('{/* ml-2 */}')).toBe(true);
    expect(isComment('<div className="ml-2">')).toBe(false);
  });

  it('flags space-x without the RTL reverse', () => {
    expect(unreversedSpaceX('className="flex space-x-4"')).toBe(true);
    expect(unreversedSpaceX('className="flex space-x-4 rtl:space-x-reverse"')).toBe(false);
    expect(unreversedSpaceX('className="flex gap-4"')).toBe(false);
  });
});
