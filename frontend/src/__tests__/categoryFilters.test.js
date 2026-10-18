import { describe, it, expect } from 'vitest';
import {
  DEFAULT_SORT,
  DEFAULT_PAGE_SIZE,
  FILTER_URL_KEYS,
  parseCategoryFilters,
  toApiFilterParams,
  toggleListParam,
} from '../utils/categoryFilters';
import { applyParamUpdates } from '../utils/urlParams';
import { cosmeticPatchToUrlUpdates, EMPTY_COSMETIC_FILTERS } from '../utils/cosmeticFilters';

const parse = (qs = '') => parseCategoryFilters(new URLSearchParams(qs));

// ═════════════════════════════════════════════════════════════════════════════
describe('parseCategoryFilters — reading the URL', () => {
  it('an empty URL is the unfiltered default state', () => {
    expect(parse('')).toEqual({
      category: '',
      search: '',
      brands: [],
      colors: [],
      priceRange: { min: 0, max: 1000 },
      cosmetic: EMPTY_COSMETIC_FILTERS,
      sortBy: DEFAULT_SORT,
      page: 1,
      pageSize: DEFAULT_PAGE_SIZE,
      flashSaleId: '',
    });
  });

  it('reads every filter', () => {
    const f = parse(
      'category=skincare&search=rose&brand=acme,zen&color=Red,Deep%20Blue' +
        '&min_price=100&max_price=500&skin_type=oily,dry&hair_type=curly&gender=female' +
        '&min_spf=30&max_spf=50&is_cruelty_free=true&is_vegan=true' +
        '&ordering=price&page=3&page_size=24&flash_sale=7',
    );
    expect(f).toMatchObject({
      category: 'skincare',
      search: 'rose',
      brands: ['acme', 'zen'],
      colors: ['Red', 'Deep Blue'],
      priceRange: { min: 100, max: 500 },
      sortBy: 'price',
      page: 3,
      pageSize: 24,
      flashSaleId: '7',
    });
    expect(f.cosmetic).toMatchObject({
      skin_type: ['oily', 'dry'],
      hair_type: ['curly'],
      gender: 'female',
      min_spf: '30',
      max_spf: '50',
      is_cruelty_free: true,
      is_vegan: true,
      is_organic: false,
    });
  });

  it('multi-value filters are ONE comma-separated value, decoded to a list', () => {
    expect(parse('brand=a,b,c').brands).toEqual(['a', 'b', 'c']);
    expect(parse('brand=a%2Cb').brands).toEqual(['a', 'b']); // the encoded form URLSearchParams writes
    expect(parse('skin_type=oily%2Cdry').cosmetic.skin_type).toEqual(['oily', 'dry']);
  });

  it('trims, drops blanks and removes duplicates in lists', () => {
    expect(parse('brand=a,,b,a, c ').brands).toEqual(['a', 'b', 'c']);
  });

  describe('junk values fall back to defaults instead of breaking the page', () => {
    it.each(['abc', '0', '-3', '1.5', ''])('page=%j -> 1', (bad) => {
      expect(parse(`page=${bad}`).page).toBe(1);
    });
    it('page=7 -> 7', () => expect(parse('page=7').page).toBe(7));

    it('unknown ordering -> newest first', () => {
      expect(parse('ordering=bogus').sortBy).toBe(DEFAULT_SORT);
      expect(parse('ordering=-price').sortBy).toBe('-price');
    });

    it('page_size must be one of the offered sizes', () => {
      expect(parse('page_size=7').pageSize).toBe(DEFAULT_PAGE_SIZE);
      expect(parse('page_size=abc').pageSize).toBe(DEFAULT_PAGE_SIZE);
      expect(parse('page_size=48').pageSize).toBe(48);
    });

    it('prices are clamped to the slider range and ignore non-numbers', () => {
      expect(parse('min_price=-50&max_price=5000').priceRange).toEqual({ min: 0, max: 1000 });
      expect(parse('min_price=zzz&max_price=yyy').priceRange).toEqual({ min: 0, max: 1000 });
    });

    it('a reversed price range is put the right way round', () => {
      expect(parse('min_price=500&max_price=100').priceRange).toEqual({ min: 100, max: 500 });
    });

    it('unknown skin / gender values are ignored', () => {
      const { cosmetic } = parse('skin_type=oily,purple&gender=alien');
      expect(cosmetic.skin_type).toEqual(['oily']);
      expect(cosmetic.gender).toBe('');
    });

    it('is_vegan=false in a hand-edited URL is not a filter', () => {
      expect(parse('is_vegan=false').cosmetic.is_vegan).toBe(false);
    });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('toApiFilterParams — what the list/facet requests are built from', () => {
  it('sends nothing for the default state', () => {
    expect(toApiFilterParams(parse(''))).toEqual({});
  });

  it('maps every filter to its API param, comma-joining lists', () => {
    const params = toApiFilterParams(
      parse(
        'category=skincare&search=%20rose%20&brand=acme,zen&color=Red,Blue&min_price=100&max_price=500' +
          '&skin_type=dry,oily&gender=female&min_spf=30&is_vegan=true&flash_sale=7',
      ),
    );
    expect(params).toEqual({
      category: 'skincare',
      search: 'rose', // trimmed
      brand: 'acme,zen',
      color: 'Red,Blue',
      min_price: 100,
      max_price: 500,
      flash_sale: '7',
      skin_type: 'oily,dry', // canonical order
      gender: 'female',
      min_spf: 30,
      is_vegan: 'true',
    });
  });

  it('leaves out paging, sort and page size (they do not change what matches)', () => {
    const params = toApiFilterParams(parse('page=4&page_size=48&ordering=price&brand=acme'));
    expect(params).toEqual({ brand: 'acme' });
  });

  it('omits the price bounds when they are at the slider extremes', () => {
    expect(toApiFilterParams(parse('min_price=0&max_price=1000'))).toEqual({});
    expect(toApiFilterParams(parse('min_price=10'))).toEqual({ min_price: 10 });
    expect(toApiFilterParams(parse('max_price=990'))).toEqual({ max_price: 990 });
  });
});

describe('toggleListParam', () => {
  it('adds, removes, and returns null (= remove the param) when empty', () => {
    expect(toggleListParam([], 'a')).toBe('a');
    expect(toggleListParam(['a'], 'b')).toBe('a,b');
    expect(toggleListParam(['a', 'b'], 'a')).toBe('b');
    expect(toggleListParam(['a'], 'a')).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('applyParamUpdates — writing the URL', () => {
  const sp = (qs) => new URLSearchParams(qs);

  it('sets, overwrites and removes params', () => {
    const next = applyParamUpdates(sp('a=1&b=2'), { a: '9', b: null, c: 'x' }, { resetPage: false });
    expect(next.toString()).toBe('a=9&c=x');
  });

  it.each([null, undefined, ''])('%j removes the param', (empty) => {
    expect(applyParamUpdates(sp('a=1'), { a: empty }).has('a')).toBe(false);
  });

  it('never mutates the params it was given', () => {
    const prev = sp('a=1&page=3');
    applyParamUpdates(prev, { a: '2' });
    expect(prev.toString()).toBe('a=1&page=3');
  });

  it('changing a filter drops the page (back to page 1)', () => {
    expect(applyParamUpdates(sp('brand=a&page=3'), { brand: 'b' }).has('page')).toBe(false);
  });

  it('keepPage (resetPage: false) leaves it — and a page update can set it', () => {
    const next = applyParamUpdates(sp('brand=a&page=3'), { page: '4' }, { resetPage: false });
    expect(next.get('page')).toBe('4');
    expect(next.get('brand')).toBe('a');
  });

  it('keeps unrelated params (e.g. flash_sale, utm tracking) untouched', () => {
    const next = applyParamUpdates(sp('flash_sale=7&utm_source=mail'), { brand: 'a' });
    expect(next.get('flash_sale')).toBe('7');
    expect(next.get('utm_source')).toBe('mail');
  });

  it('coerces numbers to strings', () => {
    expect(applyParamUpdates(sp(''), { min_price: 100 }).get('min_price')).toBe('100');
  });

  it('a multi-value list is stored as a single param, never repeated keys', () => {
    const next = applyParamUpdates(sp(''), { skin_type: 'oily,dry' });
    expect(next.getAll('skin_type')).toEqual(['oily,dry']);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('write -> read round trip', () => {
  it('every filter survives being written to the URL and read back', () => {
    // Exactly the updates the Category page issues, applied one after another.
    let url = new URLSearchParams();
    const write = (updates, opts) => { url = applyParamUpdates(url, updates, opts); };

    write({ category: 'skincare' });
    write({ brand: toggleListParam([], 'acme') });
    write({ brand: toggleListParam(['acme'], 'zen') });
    write({ color: toggleListParam([], 'Deep Blue') });
    write({ min_price: '100', max_price: '500' });
    write(cosmeticPatchToUrlUpdates({ skin_type: ['dry', 'oily'] }));
    write(cosmeticPatchToUrlUpdates({ hair_type: ['curly'], gender: 'female' }));
    write(cosmeticPatchToUrlUpdates({ min_spf: '30', max_spf: '50' }));
    write(cosmeticPatchToUrlUpdates({ is_vegan: true }));
    write({ search: 'rose' });
    write({ ordering: 'price' });
    write({ page_size: '24' });
    write({ page: '2' }, { resetPage: false });

    const f = parseCategoryFilters(new URLSearchParams(url.toString()));
    expect(f).toMatchObject({
      category: 'skincare',
      brands: ['acme', 'zen'],
      colors: ['Deep Blue'],
      priceRange: { min: 100, max: 500 },
      search: 'rose',
      sortBy: 'price',
      pageSize: 24,
      page: 2,
    });
    expect(f.cosmetic).toMatchObject({
      skin_type: ['oily', 'dry'],
      hair_type: ['curly'],
      gender: 'female',
      min_spf: '30',
      max_spf: '50',
      is_vegan: true,
      is_organic: false,
    });
    // ...and the multi-select facets are single params, not repeated ones.
    expect(url.getAll('skin_type')).toHaveLength(1);
    expect(url.getAll('brand')).toHaveLength(1);
  });

  it('un-doing every filter returns to a clean URL', () => {
    let url = new URLSearchParams();
    const write = (u) => { url = applyParamUpdates(url, u); };
    write({ brand: 'a' });
    write(cosmeticPatchToUrlUpdates({ skin_type: ['oily'], is_vegan: true }));
    write({ min_price: '100' });
    write({ brand: null });
    write(cosmeticPatchToUrlUpdates({ skin_type: [], is_vegan: false }));
    write({ min_price: null });
    expect(url.toString()).toBe('');
  });
});

describe('FILTER_URL_KEYS (what "Clear all" removes)', () => {
  it('covers every filter, the sort order and all the cosmetics params', () => {
    [
      'category', 'search', 'brand', 'color', 'min_price', 'max_price', 'ordering',
      'skin_type', 'hair_type', 'gender', 'min_spf', 'max_spf',
      'is_cruelty_free', 'is_vegan', 'is_organic',
    ].forEach((k) => expect(FILTER_URL_KEYS).toContain(k));
  });

  it('leaves the flash-sale link, page size and page alone', () => {
    ['flash_sale', 'page_size', 'page'].forEach((k) => expect(FILTER_URL_KEYS).not.toContain(k));
  });
});
