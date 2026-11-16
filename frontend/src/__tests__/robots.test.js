// Task 15.1.2.2: robots.txt is generated at build time and is crawlable ONLY on an explicit
// production opt-in; everything else is blocked. Also audits it against the live route table.
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { PRIVATE_PATHS, buildRobotsTxt, resolveRobotsConfig, robotsPlugin } from '../../robots.js';

const PROD_ENV = { VITE_ALLOW_INDEXING: 'true', VITE_SITE_URL: 'https://chiz.example' };
const robots = (env) => buildRobotsTxt(resolveRobotsConfig(env));
const directives = (txt) =>
  txt
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('#'));

/** Minimal RFC 9309 matcher for the `User-agent: *` group: longest rule wins, Allow wins a tie. */
const isBlocked = (txt, urlPath) => {
  let best = { length: -1, allow: true };
  for (const line of directives(txt)) {
    const m = /^(allow|disallow):\s*(.*)$/i.exec(line);
    if (!m || m[2] === '') continue;
    if (!urlPath.startsWith(m[2])) continue;
    const allow = m[1].toLowerCase() === 'allow';
    if (m[2].length > best.length || (m[2].length === best.length && allow)) {
      best = { length: m[2].length, allow };
    }
  }
  return !best.allow;
};

describe('non-production builds are blocked entirely', () => {
  const BLOCK_ALL = ['User-agent: *', 'Disallow: /'];

  it('blocks everything by default, with no environment configured at all', () => {
    expect(directives(robots({}))).toEqual(BLOCK_ALL);
    expect(directives(robots(undefined))).toEqual(BLOCK_ALL);
  });

  it('stays blocked, and advertises NO sitemap, even when a site URL and sitemap are configured', () => {
    // A staging build is a production build with different settings: only the opt-in differs.
    const staging = robots({
      VITE_SITE_URL: 'https://staging.chiz.example',
      VITE_SITEMAP_URL: 'https://staging.chiz.example/sitemap.xml',
    });
    expect(directives(staging)).toEqual(BLOCK_ALL);
    expect(staging).not.toMatch(/sitemap/i);
    expect(staging).not.toMatch(/^Allow:/im);
  });

  it.each([[''], ['false'], ['True'], ['TRUE'], ['1'], ['yes'], ['on'], [' truee ']])(
    'treats VITE_ALLOW_INDEXING=%j as NOT opted in (only the exact string "true" opts in)',
    (flag) => {
      expect(directives(robots({ ...PROD_ENV, VITE_ALLOW_INDEXING: flag }))).toEqual(BLOCK_ALL);
    },
  );

  it('warns about a non-empty value that is not exactly "true", but not about an absent one', () => {
    expect(resolveRobotsConfig({ VITE_ALLOW_INDEXING: 'True' }).warning).toMatch(/exactly "true"/);
    expect(resolveRobotsConfig({}).warning).toBeUndefined();
    expect(resolveRobotsConfig({ VITE_ALLOW_INDEXING: '' }).warning).toBeUndefined();
  });

  it('blocks every path', () => {
    for (const p of ['/', '/product/serum', '/category', '/blog/post', '/robots.txt']) {
      expect(isBlocked(robots({}), p), p).toBe(true);
    }
  });
});

describe('a production build (explicit opt-in)', () => {
  const txt = robots(PROD_ENV);

  it('allows crawling and names the REAL sitemap, never the placeholder domain', () => {
    expect(directives(txt)).toContain('Allow: /');
    expect(txt).toContain('Sitemap: https://chiz.example/sitemap.xml');
    expect(txt).not.toMatch(/yourdomain/i);
    expect(directives(txt)).not.toContain('Disallow: /');
  });

  it('disallows every private path', () => {
    for (const p of PRIVATE_PATHS) expect(directives(txt)).toContain(`Disallow: ${p}`);
    expect(new Set(PRIVATE_PATHS).size).toBe(PRIVATE_PATHS.length); // no duplicates
  });

  it('has no Crawl-delay (ignored by Google; protects nothing here)', () => {
    expect(txt).not.toMatch(/crawl-delay/i);
  });

  it('lists Allow: / last, so a first-match parser meets the specific Disallows first', () => {
    const lines = directives(txt).filter((l) => /^(allow|disallow):/i.test(l));
    expect(lines.at(-1)).toBe('Allow: /');
  });

  it('uses the sitemap URL override when given (e.g. the sitemap is served from the API host)', () => {
    const t = robots({ ...PROD_ENV, VITE_SITEMAP_URL: 'https://api.chiz.example/sitemap.xml' });
    expect(t).toContain('Sitemap: https://api.chiz.example/sitemap.xml');
    expect(t).not.toContain('Sitemap: https://chiz.example/');
  });

  it('reduces a site URL with a path or trailing slash to its origin', () => {
    expect(robots({ ...PROD_ENV, VITE_SITE_URL: 'https://chiz.example/shop/' })).toContain(
      'Sitemap: https://chiz.example/sitemap.xml',
    );
  });

  it('is a single Sitemap line and ends with a newline', () => {
    expect(txt.match(/^Sitemap:/gm)).toHaveLength(1);
    expect(txt.endsWith('\n')).toBe(true);
  });
});

describe('opting in with unusable configuration FAILS THE BUILD instead of shipping a bad file', () => {
  it.each([
    ['no VITE_SITE_URL', { VITE_ALLOW_INDEXING: 'true' }],
    ['an empty VITE_SITE_URL', { VITE_ALLOW_INDEXING: 'true', VITE_SITE_URL: '  ' }],
    ['a non-URL', { VITE_ALLOW_INDEXING: 'true', VITE_SITE_URL: 'chiz.example' }],
    ['plain http', { VITE_ALLOW_INDEXING: 'true', VITE_SITE_URL: 'http://chiz.example' }],
    ['localhost', { VITE_ALLOW_INDEXING: 'true', VITE_SITE_URL: 'https://localhost:3000' }],
    ['127.0.0.1', { VITE_ALLOW_INDEXING: 'true', VITE_SITE_URL: 'https://127.0.0.1' }],
    ['a .local host', { VITE_ALLOW_INDEXING: 'true', VITE_SITE_URL: 'https://box.local' }],
  ])('throws for %s', (_label, env) => {
    expect(() => resolveRobotsConfig(env)).toThrow(/VITE_SITE_URL/);
  });

  it('throws for an unusable VITE_SITEMAP_URL', () => {
    expect(() =>
      resolveRobotsConfig({ ...PROD_ENV, VITE_SITEMAP_URL: '/sitemap.xml' }),
    ).toThrow(/VITE_SITEMAP_URL/);
    expect(() =>
      resolveRobotsConfig({ ...PROD_ENV, VITE_SITEMAP_URL: 'http://localhost:8000/sitemap.xml' }),
    ).toThrow(/VITE_SITEMAP_URL/);
  });

  it('names the way out in the message', () => {
    expect(() => resolveRobotsConfig({ VITE_ALLOW_INDEXING: 'true' })).toThrow(
      /Remove VITE_ALLOW_INDEXING/,
    );
  });
});

describe('Vite plugin', () => {
  let envDir;
  const logger = { info: vi.fn(), warn: vi.fn() };
  beforeEach(() => {
    envDir = fs.mkdtempSync(path.join(os.tmpdir(), 'robots-plugin-'));
    // Neutralise whatever the machine running the tests has set. REMOVED, not blanked: Vite's
    // loadEnv lets a process env var override the .env files even when it is empty.
    for (const name of ['VITE_ALLOW_INDEXING', 'VITE_SITE_URL', 'VITE_SITEMAP_URL']) {
      vi.stubEnv(name, undefined);
    }
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    fs.rmSync(envDir, { recursive: true, force: true });
  });

  const resolve = (plugin, mode = 'production') => plugin.configResolved({ mode, envDir, logger });
  const emitted = (plugin) => {
    const emitFile = vi.fn();
    plugin.generateBundle.call({ emitFile });
    return emitFile.mock.calls[0]?.[0];
  };
  const served = (plugin, url) => {
    let handler;
    plugin.configureServer({ middlewares: { use: (fn) => (handler = fn) } });
    const res = { setHeader: vi.fn(), end: vi.fn() };
    const next = vi.fn();
    handler({ url }, res, next);
    return { res, next };
  };

  it('emits robots.txt into the build, blocking everything by default', () => {
    const plugin = robotsPlugin();
    resolve(plugin);
    expect(emitted(plugin)).toMatchObject({ type: 'asset', fileName: 'robots.txt' });
    expect(directives(emitted(plugin).source)).toEqual(['User-agent: *', 'Disallow: /']);
  });

  it('emits the crawlable file when the build env opts in (process env, as in a Docker build)', () => {
    vi.stubEnv('VITE_ALLOW_INDEXING', 'true');
    vi.stubEnv('VITE_SITE_URL', 'https://chiz.example');
    const plugin = robotsPlugin();
    resolve(plugin);
    expect(emitted(plugin).source).toContain('Sitemap: https://chiz.example/sitemap.xml');
  });

  it('reads the opt-in from the mode’s .env file too (e.g. .env.production)', () => {
    fs.writeFileSync(
      path.join(envDir, '.env.production'),
      'VITE_ALLOW_INDEXING=true\nVITE_SITE_URL=https://chiz.example\n',
    );
    const plugin = robotsPlugin();
    resolve(plugin, 'production');
    expect(emitted(plugin).source).toContain('Allow: /');

    const staging = robotsPlugin(); // a different mode does not read that file: blocked
    resolve(staging, 'staging');
    expect(directives(emitted(staging).source)).toEqual(['User-agent: *', 'Disallow: /']);
  });

  it('lets a (even blank) build-time env var override the .env file: blocked, the safe direction', () => {
    // e.g. a Docker `ARG VITE_ALLOW_INDEXING=` / `ENV ...` with an empty default shadows the file.
    fs.writeFileSync(
      path.join(envDir, '.env.production'),
      'VITE_ALLOW_INDEXING=true\nVITE_SITE_URL=https://chiz.example\n',
    );
    vi.stubEnv('VITE_ALLOW_INDEXING', '');
    const plugin = robotsPlugin();
    resolve(plugin);
    expect(directives(emitted(plugin).source)).toEqual(['User-agent: *', 'Disallow: /']);
  });

  it('makes the build itself fail on an opt-in with an unusable site URL', () => {
    vi.stubEnv('VITE_ALLOW_INDEXING', 'true');
    expect(() => resolve(robotsPlugin())).toThrow(/VITE_SITE_URL/);
  });

  it('logs the decision, and warns about a mistyped flag', () => {
    vi.stubEnv('VITE_ALLOW_INDEXING', 'True');
    resolve(robotsPlugin());
    expect(logger.warn).toHaveBeenCalledWith(expect.stringContaining('not exactly "true"'));
    expect(logger.info).toHaveBeenCalledWith(expect.stringContaining('blocked'));
  });

  it('serves the same content from the dev server, ahead of the SPA fallback', () => {
    const plugin = robotsPlugin();
    resolve(plugin, 'development');

    const { res, next } = served(plugin, '/robots.txt?cachebust=1');
    expect(next).not.toHaveBeenCalled();
    expect(res.setHeader).toHaveBeenCalledWith('Content-Type', 'text/plain; charset=utf-8');
    expect(directives(res.end.mock.calls[0][0])).toEqual(['User-agent: *', 'Disallow: /']);
  });

  it('leaves every other dev-server request alone', () => {
    const plugin = robotsPlugin();
    resolve(plugin);
    for (const url of ['/', '/faq', '/robots.txt.bak', '/src/main.jsx']) {
      const { res, next } = served(plugin, url);
      expect(next).toHaveBeenCalled();
      expect(res.end).not.toHaveBeenCalled();
    }
  });

  it('is safe before configResolved has run: still blocks everything', () => {
    expect(directives(emitted(robotsPlugin()).source)).toEqual(['User-agent: *', 'Disallow: /']);
  });
});

// ─── Audit against the LIVE route table (src/App.jsx) ─────────────────────────────
// Not a hand-kept list: the private routes are re-derived from the guards in App.jsx, so a new
// ProtectedRoute/GuestRoute/AdminRoute page that robots.txt misses fails here.
describe('robots.txt matches the real routes in App.jsx', () => {
  const appSource = fs.readFileSync(
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../App.jsx'),
    'utf8',
  );
  const opens = [...appSource.matchAll(/<Route\b/g)].map((m) => m.index);
  const routes = [...appSource.matchAll(/<Route\s+path="(\/[^"]*)"/g)].map((m) => {
    const next = opens.find((i) => i > m.index) ?? appSource.length;
    return {
      path: m[1].replace(/:[A-Za-z_]+/g, 'x'),
      pattern: m[1],
      guarded: /\b(GuestRoute|ProtectedRoute|AdminRoute)\b/.test(appSource.slice(m.index, next)),
    };
  });
  const txt = robots(PROD_ENV);

  // Per-user state with no auth wrapper, so it cannot be derived from a guard.
  const PRIVATE_BUT_UNGUARDED = ['/cart'];

  it('finds the route table (guards against the parser silently matching nothing)', () => {
    const guarded = routes.filter((r) => r.guarded).map((r) => r.pattern);
    expect(routes.length).toBeGreaterThan(20);
    expect(guarded).toEqual(
      expect.arrayContaining(['/login', '/account', '/checkout', '/order-confirmation/:id', '/admin']),
    );
  });

  it('blocks every guarded route (admin, account, checkout and the auth flows)', () => {
    const missed = routes.filter((r) => r.guarded && !isBlocked(txt, r.path)).map((r) => r.pattern);
    expect(missed, `add these to PRIVATE_PATHS in robots.js: ${missed}`).toEqual([]);
  });

  it('blocks the known private routes that have no guard', () => {
    for (const p of PRIVATE_BUT_UNGUARDED) expect(isBlocked(txt, p), p).toBe(true);
  });

  it('blocks nothing public: every other route stays crawlable', () => {
    const publicRoutes = routes.filter((r) => !r.guarded && !PRIVATE_BUT_UNGUARDED.includes(r.path));
    expect(publicRoutes.map((r) => r.pattern)).toEqual(
      expect.arrayContaining(['/', '/category', '/product/:slug', '/blog', '/blog/:slug', '/faq']),
    );
    const wronglyBlocked = publicRoutes.filter((r) => isBlocked(txt, r.path)).map((r) => r.pattern);
    expect(wronglyBlocked).toEqual([]);
  });

  it('keeps /search crawlable: it is noindex, and a noindex can only be seen on a fetchable page', () => {
    expect(routes.map((r) => r.pattern)).toContain('/search');
    expect(isBlocked(txt, '/search')).toBe(false);
  });

  it('does not block the JS/CSS the SPA needs to render, or the sitemap', () => {
    expect(isBlocked(txt, '/assets/index-abc123.js')).toBe(false);
    expect(isBlocked(txt, '/sitemap.xml')).toBe(false);
  });

  it('has no stale entries: every PRIVATE_PATHS rule covers at least one real route', () => {
    for (const rule of PRIVATE_PATHS) {
      const covered = routes.some((r) => r.path === rule || r.path.startsWith(`${rule}/`));
      expect(covered, `${rule} matches no route in App.jsx (renamed or removed?)`).toBe(true);
    }
  });

  it('does not list routes that never existed (the brief guessed /register)', () => {
    expect(PRIVATE_PATHS).not.toContain('/register');
  });
});
