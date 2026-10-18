import { describe, it, expect } from 'vitest';
import {
  EMPTY_COSMETIC_FILTERS,
  SKIN_TYPE_OPTIONS,
  HAIR_TYPE_OPTIONS,
  GENDER_OPTIONS,
  cosmeticFiltersToParams,
  cosmeticFiltersFromSearchParams,
  cosmeticPatchToUrlUpdates,
  countActiveCosmeticFilters,
  getActiveCosmeticChips,
  normalizeCosmeticFilters,
  toggleListValue,
  parseSpf,
} from '../utils/cosmeticFilters';

const withFilters = (overrides) => ({ ...EMPTY_COSMETIC_FILTERS, ...overrides });

// ═════════════════════════════════════════════════════════════════════════════
// option values must match the backend's choices exactly
// ═════════════════════════════════════════════════════════════════════════════
describe('option values (shop.models SkinType / HairType / ProductGender)', () => {
  it('skin types', () => {
    expect(SKIN_TYPE_OPTIONS.map((o) => o.value)).toEqual([
      'oily', 'dry', 'combination', 'sensitive', 'normal', 'all',
    ]);
  });
  it('hair types', () => {
    expect(HAIR_TYPE_OPTIONS.map((o) => o.value)).toEqual([
      'straight', 'wavy', 'curly', 'coily', 'all',
    ]);
  });
  it('genders', () => {
    expect(GENDER_OPTIONS.map((o) => o.value)).toEqual(['unisex', 'female', 'male']);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// state -> API query params
// ═════════════════════════════════════════════════════════════════════════════
describe('cosmeticFiltersToParams', () => {
  it('sends nothing when no filter is set', () => {
    expect(cosmeticFiltersToParams(EMPTY_COSMETIC_FILTERS)).toEqual({});
    expect(cosmeticFiltersToParams(undefined)).toEqual({});
  });

  it('skin_type: comma-separated values', () => {
    expect(cosmeticFiltersToParams(withFilters({ skin_type: ['oily'] }))).toEqual({
      skin_type: 'oily',
    });
    expect(cosmeticFiltersToParams(withFilters({ skin_type: ['oily', 'dry'] }))).toEqual({
      skin_type: 'oily,dry',
    });
  });

  it('hair_type: comma-separated values', () => {
    expect(
      cosmeticFiltersToParams(withFilters({ hair_type: ['curly', 'wavy'] })),
    ).toEqual({ hair_type: 'wavy,curly' });
  });

  it('lists are in canonical order regardless of selection order (stable URLs / cache keys)', () => {
    const a = cosmeticFiltersToParams(withFilters({ skin_type: ['dry', 'oily', 'normal'] }));
    const b = cosmeticFiltersToParams(withFilters({ skin_type: ['normal', 'oily', 'dry'] }));
    expect(a).toEqual(b);
    expect(a.skin_type).toBe('oily,dry,normal');
  });

  it('gender: a single value', () => {
    expect(cosmeticFiltersToParams(withFilters({ gender: 'female' }))).toEqual({
      gender: 'female',
    });
  });

  it('SPF range: min_spf / max_spf as numbers', () => {
    expect(cosmeticFiltersToParams(withFilters({ min_spf: '30' }))).toEqual({ min_spf: 30 });
    expect(cosmeticFiltersToParams(withFilters({ max_spf: '50' }))).toEqual({ max_spf: 50 });
    expect(
      cosmeticFiltersToParams(withFilters({ min_spf: '15', max_spf: '50' })),
    ).toEqual({ min_spf: 15, max_spf: 50 });
  });

  it('a minimum SPF of 0 is "no minimum" (spf >= 0 would exclude NULL-SPF products)', () => {
    expect(cosmeticFiltersToParams(withFilters({ min_spf: '0' }))).toEqual({});
    expect(
      cosmeticFiltersToParams(withFilters({ min_spf: '0', max_spf: '30' })),
    ).toEqual({ max_spf: 30 });
  });

  it('a maximum SPF of 0 is kept (it means "no SPF protection" or less)', () => {
    expect(cosmeticFiltersToParams(withFilters({ max_spf: '0' }))).toEqual({ max_spf: 0 });
  });

  describe('certification flags', () => {
    it.each([
      ['is_cruelty_free'],
      ['is_vegan'],
      ['is_organic'],
    ])('%s is sent as "true" when checked', (key) => {
      expect(cosmeticFiltersToParams(withFilters({ [key]: true }))).toEqual({ [key]: 'true' });
    });

    it('unchecked flags are OMITTED, never sent as false', () => {
      const params = cosmeticFiltersToParams(withFilters({ is_vegan: true }));
      expect(params).toEqual({ is_vegan: 'true' });
      expect(params).not.toHaveProperty('is_cruelty_free');
      expect(params).not.toHaveProperty('is_organic');
      expect(Object.values(params)).not.toContain('false');
      expect(Object.values(params)).not.toContain(false);
    });

    it('they are independent — any combination can be set together', () => {
      expect(
        cosmeticFiltersToParams(
          withFilters({ is_cruelty_free: true, is_vegan: true, is_organic: true }),
        ),
      ).toEqual({ is_cruelty_free: 'true', is_vegan: 'true', is_organic: 'true' });
    });

    it('only a real boolean true counts (not the string "false", not 1)', () => {
      expect(
        cosmeticFiltersToParams(withFilters({ is_vegan: 'false', is_organic: 1 })),
      ).toEqual({});
    });
  });

  it('combines every facet at once', () => {
    expect(
      cosmeticFiltersToParams({
        skin_type: ['dry', 'oily'],
        hair_type: ['curly'],
        gender: 'unisex',
        min_spf: '30',
        max_spf: '50',
        is_cruelty_free: true,
        is_vegan: true,
        is_organic: false,
      }),
    ).toEqual({
      skin_type: 'oily,dry',
      hair_type: 'curly',
      gender: 'unisex',
      min_spf: 30,
      max_spf: 50,
      is_cruelty_free: 'true',
      is_vegan: 'true',
    });
  });

  it('drops unknown / invalid values instead of sending them', () => {
    expect(
      cosmeticFiltersToParams({
        skin_type: ['oily', 'purple'],
        hair_type: ['nope'],
        gender: 'alien',
        min_spf: '-5',
        max_spf: 'abc',
      }),
    ).toEqual({ skin_type: 'oily' });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// SPF parsing
// ═════════════════════════════════════════════════════════════════════════════
describe('parseSpf', () => {
  it.each([
    ['', ''],
    ['  ', ''],
    [undefined, ''],
    [null, ''],
    ['0', '0'],
    ['30', '30'],
    [' 50 ', '50'],
    ['007', '7'],
    ['100', '100'],
  ])('%j -> %j', (raw, expected) => {
    expect(parseSpf(raw)).toBe(expected);
  });

  it.each(['-1', '1.5', 'abc', '30spf', '101', '1e2', '+5'])('%j is invalid', (raw) => {
    expect(parseSpf(raw)).toBeNull();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// toggling list values
// ═════════════════════════════════════════════════════════════════════════════
describe('toggleListValue', () => {
  it('adds an absent value and removes a present one', () => {
    expect(toggleListValue([], 'dry', SKIN_TYPE_OPTIONS)).toEqual(['dry']);
    expect(toggleListValue(['dry'], 'oily', SKIN_TYPE_OPTIONS)).toEqual(['oily', 'dry']);
    expect(toggleListValue(['oily', 'dry'], 'oily', SKIN_TYPE_OPTIONS)).toEqual(['dry']);
    expect(toggleListValue(['dry'], 'dry', SKIN_TYPE_OPTIONS)).toEqual([]);
  });
  it('does not mutate its input', () => {
    const input = ['dry'];
    toggleListValue(input, 'oily', SKIN_TYPE_OPTIONS);
    expect(input).toEqual(['dry']);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// URL search params <-> state
// ═════════════════════════════════════════════════════════════════════════════
describe('URL round-trip', () => {
  it('reads every facet from a URLSearchParams', () => {
    const sp = new URLSearchParams(
      'skin_type=oily,dry&hair_type=curly&gender=female&min_spf=30&max_spf=50' +
        '&is_cruelty_free=true&is_vegan=true&is_organic=true',
    );
    expect(cosmeticFiltersFromSearchParams(sp)).toEqual({
      skin_type: ['oily', 'dry'],
      hair_type: ['curly'],
      gender: 'female',
      min_spf: '30',
      max_spf: '50',
      is_cruelty_free: true,
      is_vegan: true,
      is_organic: true,
    });
  });

  it('absent params give the empty state', () => {
    expect(cosmeticFiltersFromSearchParams(new URLSearchParams('q=shoes'))).toEqual(
      EMPTY_COSMETIC_FILTERS,
    );
  });

  it('ignores junk in a hand-edited URL', () => {
    const sp = new URLSearchParams('skin_type=oily,bogus&is_vegan=false&gender=x&min_spf=zzz');
    expect(cosmeticFiltersFromSearchParams(sp)).toEqual({
      ...EMPTY_COSMETIC_FILTERS,
      skin_type: ['oily'],
    });
  });

  it('turns state patches into URL updates: a string to set, null to remove', () => {
    expect(cosmeticPatchToUrlUpdates({ skin_type: ['dry', 'oily'] })).toEqual({
      skin_type: 'oily,dry',
    });
    expect(cosmeticPatchToUrlUpdates({ skin_type: [] })).toEqual({ skin_type: null });
    expect(cosmeticPatchToUrlUpdates({ is_vegan: true })).toEqual({ is_vegan: 'true' });
    expect(cosmeticPatchToUrlUpdates({ is_vegan: false })).toEqual({ is_vegan: null });
    expect(cosmeticPatchToUrlUpdates({ gender: 'male' })).toEqual({ gender: 'male' });
    expect(cosmeticPatchToUrlUpdates({ gender: '' })).toEqual({ gender: null });
    expect(cosmeticPatchToUrlUpdates({ min_spf: '30', max_spf: '' })).toEqual({
      min_spf: '30',
      max_spf: null,
    });
    expect(cosmeticPatchToUrlUpdates({ min_spf: '0' })).toEqual({ min_spf: null });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// counts & chips
// ═════════════════════════════════════════════════════════════════════════════
describe('countActiveCosmeticFilters', () => {
  it('is 0 when nothing is set', () => {
    expect(countActiveCosmeticFilters(EMPTY_COSMETIC_FILTERS)).toBe(0);
  });

  it('counts each facet group once, however many values it has', () => {
    expect(countActiveCosmeticFilters(withFilters({ skin_type: ['oily', 'dry', 'normal'] }))).toBe(1);
    expect(countActiveCosmeticFilters(withFilters({ min_spf: '15', max_spf: '50' }))).toBe(1);
  });

  it('counts each certification flag on its own', () => {
    expect(
      countActiveCosmeticFilters(withFilters({ is_vegan: true, is_organic: true })),
    ).toBe(2);
  });

  it('skin type + vegan + min SPF = 3', () => {
    expect(
      countActiveCosmeticFilters(
        withFilters({ skin_type: ['oily'], is_vegan: true, min_spf: '30' }),
      ),
    ).toBe(3);
  });
});

describe('getActiveCosmeticChips', () => {
  it('has no chips when nothing is set', () => {
    expect(getActiveCosmeticChips(EMPTY_COSMETIC_FILTERS)).toEqual([]);
  });

  it('makes one chip per selected skin/hair value', () => {
    const chips = getActiveCosmeticChips(
      withFilters({ skin_type: ['oily', 'dry'], hair_type: ['curly'] }),
    );
    expect(chips.map((c) => `${c.type}: ${c.value}`)).toEqual([
      'Skin Type: Oily',
      'Skin Type: Dry',
      'Hair Type: Curly',
    ]);
  });

  it("each chip's patch removes only its own value", () => {
    const [oily, dry] = getActiveCosmeticChips(withFilters({ skin_type: ['oily', 'dry'] }));
    expect(oily.patch).toEqual({ skin_type: ['dry'] });
    expect(dry.patch).toEqual({ skin_type: ['oily'] });
  });

  it('labels the SPF range', () => {
    const label = (f) => getActiveCosmeticChips(withFilters(f))[0].value;
    expect(label({ min_spf: '30' })).toBe('30+');
    expect(label({ max_spf: '15' })).toBe('up to 15');
    expect(label({ min_spf: '15', max_spf: '50' })).toBe('15 – 50');
  });

  it('SPF chip clears both ends; gender and flag chips clear themselves', () => {
    const chips = getActiveCosmeticChips(
      withFilters({ min_spf: '15', max_spf: '50', gender: 'female', is_vegan: true }),
    );
    const byType = Object.fromEntries(chips.map((c) => [c.type, c]));
    expect(byType.SPF.patch).toEqual({ min_spf: '', max_spf: '' });
    expect(byType.Gender).toMatchObject({ value: 'Female', patch: { gender: '' } });
    expect(byType.Certification).toMatchObject({ value: 'Vegan', patch: { is_vegan: false } });
  });
});

describe('normalizeCosmeticFilters', () => {
  it('fills in every key and never returns nullish values', () => {
    expect(normalizeCosmeticFilters()).toEqual(EMPTY_COSMETIC_FILTERS);
    expect(normalizeCosmeticFilters({ skin_type: null, gender: null })).toEqual(
      EMPTY_COSMETIC_FILTERS,
    );
  });
});
