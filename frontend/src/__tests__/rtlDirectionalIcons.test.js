// Task 14.3.1.3: in a right-to-left layout an icon whose DIRECTION carries meaning
// (next/previous, go, back, exit, send, reply) must be mirrored, or "next" points
// backwards. `icon-directional` (src/index.css) does that. Logical Tailwind classes
// (14.3.1.2) move things; they do not turn a "right" arrow into a "left" one.
// This keeps new directional icons from slipping in unmirrored, and pins the CSS and
// the RTL marquee that make the class work. It cannot judge how a page LOOKS.
import { readFileSync, readdirSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

// Icons that must mirror. Deliberately NOT here: clocks, refresh/rotation arrows,
// media play, vertical arrows/sort, and the symmetric arrow-left-right.
const MIRRORED = [
  'arrow-left', 'arrow-right', 'chevron-left', 'chevron-right', 'box-arrow-right',
  'arrow-return-left', 'text-left', 'send', 'reply',
  // not named left/right, but the FILLED half must face the filled stars: in RTL a rating
  // fills from the right, so the half star is mirrored (found by the 14.3.3.1 QA pass).
  'star-half',
];
const ICON = new RegExp(String.raw`\bbi-(${MIRRORED.join('|')})(?![\w-])`, 'g');
const TEXT_ARROW = /[→←]/;

const sourceFiles = readdirSync('src', { recursive: true })
  .map(String)
  .filter((f) => /\.(jsx?|tsx?)$/.test(f) && !/(^|[\\/])(__tests__|tests)[\\/]/.test(f));
const isComment = (line) => /^\s*(\/\/|\*|\/\*|\{\/\*)/.test(line);

/** Lines of non-test source for which `test(line)` is true. */
const offenders = (test) => {
  const found = [];
  for (const file of sourceFiles) {
    readFileSync(`src/${file}`, 'utf8').split('\n').forEach((line, i) => {
      if (!isComment(line) && test(line)) found.push(`${file}:${i + 1}: ${line.trim().slice(0, 100)}`);
    });
  }
  return found;
};

describe('directional icons are mirrored in RTL', () => {
  it('scans a meaningful number of files and finds directional icons', () => {
    expect(sourceFiles.length).toBeGreaterThan(60);
    expect(offenders((l) => new RegExp(ICON.source).test(l)).length).toBeGreaterThan(40);
  });

  it('every bi-arrow-* / bi-chevron-* / ... icon in the mirror list carries icon-directional', () => {
    expect(offenders((l) => new RegExp(ICON.source).test(l) && !/icon-directional/.test(l))).toEqual([]);
  });

  it('every text arrow (→ ←) is wrapped in icon-directional (these are not Unicode-mirrored)', () => {
    expect(offenders((l) => TEXT_ARROW.test(l) && !/icon-directional/.test(l))).toEqual([]);
  });

  it('does not mirror icons that must keep their handedness', () => {
    const wrong = offenders((l) =>
      /icon-directional/.test(l) && /bi-(clock|arrow-clockwise|arrow-repeat|play|arrow-up|arrow-down|sort|arrow-left-right)/.test(l));
    expect(wrong).toEqual([]);
  });
});

describe('numeric badges are bidi-isolated', () => {
  // "-23%" in an RTL paragraph is drawn "23%-": the hyphen is a weak character and lands on
  // the wrong end. dir="ltr" on the badge keeps the sign in front. Found by the 14.3.3.1 QA pass.
  it('a "-{n}%" badge sits in an element with dir="ltr"', () => {
    const bad = [];
    for (const file of sourceFiles) {
      const lines = readFileSync(`src/${file}`, 'utf8').split('\n');
      lines.forEach((line, i) => {
        if (isComment(line)) return;
        const own = /^\s*-\{[^}]+\}%\s*$/.test(line);       // text alone on its line: element is above
        const inline = />-\{[^}]+\}%</.test(line);            // <span ...>-{n}%</span> on one line
        if (!own && !inline) return;
        const owner = own ? lines[i - 1] : line;
        if (!/dir="ltr"/.test(owner)) bad.push(`${file}:${i + 1}`);
      });
    }
    expect(bad).toEqual([]);
  });
});

describe('the mirror rule and the RTL ticker exist', () => {
  const css = readFileSync('src/index.css', 'utf8');

  it('mirrors .icon-directional only under dir="rtl", with the composable `scale` property', () => {
    expect(css).toMatch(/\[dir="rtl"\]\s+\.icon-directional\s*\{[^}]*scale:\s*-1\s+1/);
  });

  it('gives .icon-directional a box (a transform is ignored on a plain inline <i>)', () => {
    expect(css).toMatch(/\.icon-directional\s*\{[^}]*display:\s*inline-block/);
  });

  it('the header ticker runs the mirrored animation in RTL', () => {
    const config = readFileSync('tailwind.config.js', 'utf8');
    expect(config).toMatch(/'marquee-rtl'\s*:\s*\{/); // keyframes
    expect(config).toMatch(/'marquee-rtl'\s*:\s*'marquee-rtl /); // animation
    const header = readFileSync('src/components/Header.jsx', 'utf8');
    expect(header).toMatch(/animate-marquee\s+rtl:animate-marquee-rtl/);
  });
});
