import { vi } from 'vitest';
import {
  addRecentlyViewed,
  getRecentlyViewed,
  clearRecentlyViewed,
  STORAGE_KEY,
  MAX_ITEMS,
} from '../recentlyViewed';

const makeProduct = (n, extra = {}) => ({
  id: n,
  slug: `product-${n}`,
  name: `Product ${n}`,
  thumbnail_url: `http://example.com/img-${n}.webp`,
  price: '10.00',
  ...extra,
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('addRecentlyViewed', () => {
  it('adds a new product to the front of the list', () => {
    addRecentlyViewed(makeProduct(1));
    addRecentlyViewed(makeProduct(2));

    const list = getRecentlyViewed();
    expect(list.map((p) => p.id)).toEqual([2, 1]);
    expect(list[0]).toEqual({
      id: 2,
      slug: 'product-2',
      name: 'Product 2',
      thumbnail: 'http://example.com/img-2.webp',
      price: '10.00',
      viewedAt: expect.any(Number),
    });
  });

  it('moves an already-present product to the front instead of duplicating it', () => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000);
    addRecentlyViewed(makeProduct(1));
    vi.setSystemTime(2_000);
    addRecentlyViewed(makeProduct(2));
    vi.setSystemTime(3_000);
    addRecentlyViewed(makeProduct(1));

    const list = getRecentlyViewed();
    expect(list.map((p) => p.id)).toEqual([1, 2]);
    expect(list).toHaveLength(2);
    expect(list[0].viewedAt).toBe(3_000); // refreshed, not the original 1_000
  });

  it(`caps the list at ${MAX_ITEMS}, dropping the oldest on the next distinct add`, () => {
    for (let n = 1; n <= MAX_ITEMS; n += 1) addRecentlyViewed(makeProduct(n));
    expect(getRecentlyViewed()).toHaveLength(MAX_ITEMS);

    addRecentlyViewed(makeProduct(MAX_ITEMS + 1));

    const ids = getRecentlyViewed().map((p) => p.id);
    expect(ids).toHaveLength(MAX_ITEMS);
    expect(ids[0]).toBe(MAX_ITEMS + 1);
    expect(ids).not.toContain(1); // oldest dropped
    expect(ids).toContain(2);
  });

  it('re-viewing a product at the cap does not evict anything', () => {
    for (let n = 1; n <= MAX_ITEMS; n += 1) addRecentlyViewed(makeProduct(n));

    addRecentlyViewed(makeProduct(1));

    const ids = getRecentlyViewed().map((p) => p.id);
    expect(ids).toHaveLength(MAX_ITEMS);
    expect(ids[0]).toBe(1);
  });

  it('falls back to `thumbnail` when `thumbnail_url` is absent', () => {
    addRecentlyViewed({ id: 5, slug: 's', name: 'n', thumbnail: '/t.webp', price: '1.00' });
    expect(getRecentlyViewed()[0].thumbnail).toBe('/t.webp');
  });

  it('ignores a missing product or one without an id', () => {
    addRecentlyViewed(undefined);
    addRecentlyViewed(null);
    addRecentlyViewed({ slug: 'no-id' });
    expect(getRecentlyViewed()).toEqual([]);
  });

  it('does not propagate errors when localStorage.setItem throws (private mode / quota)', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('QuotaExceededError');
    });

    expect(() => addRecentlyViewed(makeProduct(1))).not.toThrow();
    expect(getRecentlyViewed()).toEqual([]);
  });
});

describe('getRecentlyViewed', () => {
  it('returns [] when localStorage is empty', () => {
    expect(getRecentlyViewed()).toEqual([]);
  });

  it('returns [] (not an error) for malformed JSON', () => {
    localStorage.setItem(STORAGE_KEY, '{not valid json');
    expect(getRecentlyViewed()).toEqual([]);
  });

  it.each(['{}', 'null', '"text"', '42'])('returns [] for valid JSON of the wrong shape (%s)', (raw) => {
    localStorage.setItem(STORAGE_KEY, raw);
    expect(getRecentlyViewed()).toEqual([]);
  });

  it('recovers: a write after malformed data replaces it with a clean list', () => {
    localStorage.setItem(STORAGE_KEY, '{not valid json');
    addRecentlyViewed(makeProduct(1));
    expect(getRecentlyViewed().map((p) => p.id)).toEqual([1]);
  });

  it('returns [] when localStorage.getItem throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage disabled');
    });
    expect(getRecentlyViewed()).toEqual([]);
  });
});

describe('clearRecentlyViewed', () => {
  it('empties the list', () => {
    addRecentlyViewed(makeProduct(1));
    clearRecentlyViewed();
    expect(getRecentlyViewed()).toEqual([]);
  });

  it('does not throw when removeItem throws', () => {
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('storage disabled');
    });
    expect(() => clearRecentlyViewed()).not.toThrow();
  });
});
