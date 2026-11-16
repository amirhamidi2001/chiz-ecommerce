// Task 15.1.4: canonical URL policy.
import { afterEach, describe, it, expect, vi } from 'vitest';
import {
  buildBlogCanonical,
  buildCategoryCanonical,
  buildPageCanonical,
  normalizePath,
  siteOrigin,
} from '../canonical';

const O = 'https://shop.example';
const cat = (params) => buildCategoryCanonical(params, { origin: O });

describe('siteOrigin', () => {
  afterEach(() => vi.unstubAllEnvs());

  it('uses the configured VITE_SITE_URL, reduced to its origin', () => {
    vi.stubEnv('VITE_SITE_URL', 'https://chiz.example/');
    expect(siteOrigin()).toBe('https://chiz.example');
    vi.stubEnv('VITE_SITE_URL', ' https://www.chiz.example/some/path?x=1 ');
    expect(siteOrigin()).toBe('https://www.chiz.example');
  });

  it.each([['unset', ''], ['not a URL', 'chiz dot example'], ['not http(s)', 'ftp://chiz.example']])(
    'falls back to the current origin when VITE_SITE_URL is %s',
    (_label, value) => {
      vi.stubEnv('VITE_SITE_URL', value);
      expect(siteOrigin()).toBe(window.location.origin);
    },
  );
});

describe('normalizePath', () => {
  it('drops a trailing slash but keeps the root', () => {
    expect(normalizePath('/faq/')).toBe('/faq');
    expect(normalizePath('/faq///')).toBe('/faq');
    expect(normalizePath('/')).toBe('/');
  });
  it('collapses repeated slashes (so "//evil.example" can never become a host)', () => {
    expect(normalizePath('//evil.example/x')).toBe('/evil.example/x');
    expect(normalizePath('/a//b')).toBe('/a/b');
  });
  it('percent-encodes Persian segments the same whether or not they arrive encoded', () => {
    const encoded = `/blog/${encodeURIComponent('سرم-ویتامین')}`;
    expect(normalizePath('/blog/سرم-ویتامین')).toBe(encoded);
    expect(normalizePath(encoded)).toBe(encoded);
  });
  it('returns "" for anything that is not an absolute path', () => {
    expect(normalizePath(undefined)).toBe('');
    expect(normalizePath('faq')).toBe('');
    expect(normalizePath('')).toBe('');
  });
});

describe('buildPageCanonical (default: own clean path)', () => {
  it('is origin + path with no query string, hash or trailing slash', () => {
    expect(buildPageCanonical('/about', { origin: O })).toBe(`${O}/about`);
    expect(buildPageCanonical('/about/', { origin: O })).toBe(`${O}/about`);
    expect(buildPageCanonical('/', { origin: O })).toBe(`${O}/`);
  });
  it('has none for token-bearing paths, and none without an origin or a path', () => {
    expect(buildPageCanonical('/reset-password/uid/secret-token', { origin: O })).toBe('');
    expect(buildPageCanonical('/reset-password', { origin: O })).toBe('');
    expect(buildPageCanonical('/about', { origin: '' })).toBe('');
    expect(buildPageCanonical(undefined, { origin: O })).toBe('');
  });
  it('does not mistake a longer path for a no-canonical prefix', () => {
    expect(buildPageCanonical('/reset-password-help', { origin: O })).toBe(`${O}/reset-password-help`);
  });
});

describe('buildCategoryCanonical (the category is a QUERY param, so path-only would merge them all)', () => {
  it('keeps the category slug: different categories get different canonicals', () => {
    expect(cat({ category: 'skincare' })).toBe(`${O}/category?category=skincare`);
    expect(cat({ category: 'makeup' })).toBe(`${O}/category?category=makeup`);
    expect(cat({ category: 'skincare' })).not.toBe(cat({ category: 'makeup' }));
    expect(cat({ category: 'skincare' })).not.toBe(`${O}/category`);
  });
  it('is the bare listing URL when no category is chosen', () => {
    expect(cat({})).toBe(`${O}/category`);
    expect(cat({ category: '', page: 1 })).toBe(`${O}/category`);
    expect(cat()).toBe(`${O}/category`);
  });
  it('page 1 is the page itself, so it adds nothing', () => {
    expect(cat({ category: 'skincare', page: 1 })).toBe(`${O}/category?category=skincare`);
    expect(cat({ category: 'skincare', page: '1' })).toBe(`${O}/category?category=skincare`);
  });
  it('page 2+ canonicalizes to ITSELF, never back to page 1', () => {
    expect(cat({ category: 'skincare', page: 2 })).toBe(`${O}/category?category=skincare&page=2`);
    expect(cat({ category: 'skincare', page: '7' })).toBe(`${O}/category?category=skincare&page=7`);
    expect(cat({ page: 3 })).toBe(`${O}/category?page=3`);
  });
  it.each([['abc'], [0], [-2], [1.5], [NaN], [null], [undefined]])('ignores a junk page (%s)', (page) => {
    expect(cat({ category: 'skincare', page })).toBe(`${O}/category?category=skincare`);
  });
  it('writes parameters in one fixed order and percent-encodes a Persian slug', () => {
    const slug = 'مراقبت-پوست';
    expect(cat({ page: 2, category: slug })).toBe(
      `${O}/category?category=${encodeURIComponent(slug)}&page=2`,
    );
  });
  it('has none without an origin', () => {
    expect(buildCategoryCanonical({ category: 'skincare' }, { origin: '' })).toBe('');
  });
});

describe('buildBlogCanonical', () => {
  it('applies the same policy to the blog index', () => {
    expect(buildBlogCanonical({}, { origin: O })).toBe(`${O}/blog`);
    expect(buildBlogCanonical({ page: 1 }, { origin: O })).toBe(`${O}/blog`);
    expect(buildBlogCanonical({ page: 2 }, { origin: O })).toBe(`${O}/blog?page=2`);
    expect(buildBlogCanonical({ category: 'tech', page: 3 }, { origin: O })).toBe(
      `${O}/blog?category=tech&page=3`,
    );
  });
});
