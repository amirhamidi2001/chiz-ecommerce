// Task 15.1.3: the branded fallback share image is what every imageless product (and every
// non-product page) shows on a shared link, so a missing or wrong-sized file would silently
// defeat the whole fallback. Reads the real file the nginx build ships from public/.
import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  DEFAULT_OG_IMAGE_HEIGHT,
  DEFAULT_OG_IMAGE_PATH,
  DEFAULT_OG_IMAGE_WIDTH,
} from '../constants/seo';

// frontend/public/<path>, resolved from this file's location (works from any working directory).
// (A string, not new URL(): under jsdom the global URL isn't Node's, and fileURLToPath rejects it.)
const file = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  `../../public${DEFAULT_OG_IMAGE_PATH}`,
);

/** Width/height from the first JPEG start-of-frame marker. */
const jpegSize = (buf) => {
  let i = 2;
  while (i < buf.length) {
    if (buf[i] !== 0xff) return null;
    const marker = buf[i + 1];
    const len = buf.readUInt16BE(i + 2);
    if (marker >= 0xc0 && marker <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marker)) {
      return { height: buf.readUInt16BE(i + 5), width: buf.readUInt16BE(i + 7) };
    }
    i += 2 + len;
  }
  return null;
};

describe('default Open Graph image (public/og-default.jpg)', () => {
  it('exists at the path the constants point to', () => {
    expect(DEFAULT_OG_IMAGE_PATH.startsWith('/')).toBe(true);
    expect(fs.existsSync(file)).toBe(true);
  });

  it('is a real JPEG (not WebP, which WhatsApp previews do not reliably render)', () => {
    const buf = fs.readFileSync(file);
    expect([buf[0], buf[1]]).toEqual([0xff, 0xd8]);
  });

  it('is exactly the 1200x630 the og:image:width/height tags declare', () => {
    expect(jpegSize(fs.readFileSync(file))).toEqual({
      width: DEFAULT_OG_IMAGE_WIDTH,
      height: DEFAULT_OG_IMAGE_HEIGHT,
    });
  });

  it('is small enough for link-preview crawlers (WhatsApp skips images over ~300 KB)', () => {
    expect(fs.statSync(file).size).toBeLessThan(300 * 1024);
  });
});
