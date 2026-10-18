import { describe, it, expect, vi } from 'vitest';
import { useState } from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CosmeticFilters from '../components/CosmeticFilters';
import {
  EMPTY_COSMETIC_FILTERS,
  cosmeticFiltersToParams,
} from '../utils/cosmeticFilters';

// ─── Harness ──────────────────────────────────────────────────────────────────
// Owns the filter state like a page does, and prints the API query params that
// state produces — so a test clicks real controls and asserts on the REAL
// params, not on an intermediate callback.
const Harness = ({ initial = EMPTY_COSMETIC_FILTERS, spy, ...props }) => {
  const [values, setValues] = useState(initial);
  return (
    <>
      <CosmeticFilters
        values={values}
        onChange={(patch) => {
          spy?.(patch);
          setValues((prev) => ({ ...prev, ...patch }));
        }}
        {...props}
      />
      <output data-testid="params">{JSON.stringify(cosmeticFiltersToParams(values))}</output>
    </>
  );
};

const setup = (props = {}) => {
  const user = userEvent.setup();
  const utils = render(<Harness {...props} />);
  const params = () => JSON.parse(screen.getByTestId('params').textContent);
  return { user, params, ...utils };
};

const box = (name) => screen.getByRole('checkbox', { name });
const radio = (name) => screen.getByRole('radio', { name });

// ═════════════════════════════════════════════════════════════════════════════
describe('CosmeticFilters — rendering', () => {
  it('shows every section', () => {
    setup();
    ['Skin Type', 'Hair Type', 'SPF', 'Gender', 'Certifications'].forEach((title) =>
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument(),
    );
  });

  it('offers the six skin types', () => {
    setup();
    ['Oily', 'Dry', 'Combination', 'Sensitive', 'Normal', 'All Skin Types'].forEach((label) =>
      expect(box(label)).toBeInTheDocument(),
    );
  });

  it('offers the five hair types', () => {
    setup();
    ['Straight', 'Wavy', 'Curly', 'Coily', 'All Hair Types'].forEach((label) =>
      expect(box(label)).toBeInTheDocument(),
    );
  });

  it('offers three genders as a radio group', () => {
    setup();
    ['Unisex', 'Female', 'Male'].forEach((label) => expect(radio(label)).toBeInTheDocument());
  });

  it('offers the three certifications as independent checkboxes', () => {
    setup();
    ['Cruelty-Free', 'Vegan', 'Organic'].forEach((label) =>
      expect(box(label)).toBeInTheDocument(),
    );
  });

  it('has min and max SPF inputs', () => {
    setup();
    expect(screen.getByLabelText('Minimum SPF')).toBeInTheDocument();
    expect(screen.getByLabelText('Maximum SPF')).toBeInTheDocument();
  });

  it('starts completely unfiltered', () => {
    const { params } = setup();
    expect(params()).toEqual({});
    screen.getAllByRole('checkbox').forEach((c) => expect(c).not.toBeChecked());
    screen.getAllByRole('radio').forEach((r) => expect(r).not.toBeChecked());
  });

  it('reflects incoming values', () => {
    setup({
      initial: {
        ...EMPTY_COSMETIC_FILTERS,
        skin_type: ['dry'],
        gender: 'male',
        is_organic: true,
        min_spf: '30',
      },
    });
    expect(box('Dry')).toBeChecked();
    expect(radio('Male')).toBeChecked();
    expect(box('Organic')).toBeChecked();
    expect(screen.getByLabelText('Minimum SPF')).toHaveValue(30);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('CosmeticFilters — skin type (multi-select)', () => {
  it('one selection -> ?skin_type=oily', async () => {
    const { user, params } = setup();
    await user.click(box('Oily'));
    expect(params()).toEqual({ skin_type: 'oily' });
  });

  it('several selections are comma-joined (OR within the facet)', async () => {
    const { user, params } = setup();
    await user.click(box('Oily'));
    await user.click(box('Dry'));
    expect(params()).toEqual({ skin_type: 'oily,dry' });
    expect(box('Oily')).toBeChecked();
    expect(box('Dry')).toBeChecked();
  });

  it('click order does not change the query', async () => {
    const { user, params } = setup();
    await user.click(box('Normal'));
    await user.click(box('Dry'));
    await user.click(box('Oily'));
    expect(params()).toEqual({ skin_type: 'oily,dry,normal' });
  });

  it('unchecking one leaves the others', async () => {
    const { user, params } = setup();
    await user.click(box('Oily'));
    await user.click(box('Dry'));
    await user.click(box('Oily'));
    expect(params()).toEqual({ skin_type: 'dry' });
    expect(box('Oily')).not.toBeChecked();
  });

  it('unchecking the last one removes the parameter entirely', async () => {
    const { user, params } = setup();
    await user.click(box('Oily'));
    await user.click(box('Oily'));
    expect(params()).toEqual({});
    expect(params()).not.toHaveProperty('skin_type');
  });

  it('emits only the changed key as the patch', async () => {
    const spy = vi.fn();
    const { user } = setup({ spy });
    await user.click(box('Oily'));
    expect(spy).toHaveBeenLastCalledWith({ skin_type: ['oily'] });
    await user.click(box('Sensitive'));
    expect(spy).toHaveBeenLastCalledWith({ skin_type: ['oily', 'sensitive'] });
  });
});

describe('CosmeticFilters — hair type (multi-select)', () => {
  it('several selections are comma-joined', async () => {
    const { user, params } = setup();
    await user.click(box('Curly'));
    await user.click(box('Wavy'));
    expect(params()).toEqual({ hair_type: 'wavy,curly' });
  });

  it('deselecting removes the parameter', async () => {
    const { user, params } = setup();
    await user.click(box('Coily'));
    await user.click(box('Coily'));
    expect(params()).not.toHaveProperty('hair_type');
  });

  it('is independent of skin type — "All" is a separate option in each', async () => {
    const { user, params } = setup();
    await user.click(box('All Skin Types'));
    expect(params()).toEqual({ skin_type: 'all' });
    await user.click(box('All Hair Types'));
    expect(params()).toEqual({ skin_type: 'all', hair_type: 'all' });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('CosmeticFilters — gender (single-select)', () => {
  it('selecting sets ?gender=', async () => {
    const { user, params } = setup();
    await user.click(radio('Female'));
    expect(params()).toEqual({ gender: 'female' });
  });

  it('selecting another replaces the first', async () => {
    const { user, params } = setup();
    await user.click(radio('Female'));
    await user.click(radio('Male'));
    expect(params()).toEqual({ gender: 'male' });
    expect(radio('Male')).toBeChecked();
    expect(radio('Female')).not.toBeChecked();
  });

  it('clicking the selected one again clears it', async () => {
    const { user, params } = setup();
    await user.click(radio('Unisex'));
    expect(params()).toEqual({ gender: 'unisex' });
    await user.click(radio('Unisex'));
    expect(params()).toEqual({});
    expect(radio('Unisex')).not.toBeChecked();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('CosmeticFilters — certifications (independent booleans)', () => {
  it.each([
    ['Cruelty-Free', 'is_cruelty_free'],
    ['Vegan', 'is_vegan'],
    ['Organic', 'is_organic'],
  ])('checking %s sends %s=true', async (label, key) => {
    const { user, params } = setup();
    await user.click(box(label));
    expect(params()).toEqual({ [key]: 'true' });
  });

  it('unchecked boxes are omitted from the query — not sent as false', async () => {
    const { user, params } = setup();
    await user.click(box('Vegan'));
    expect(params()).toEqual({ is_vegan: 'true' });
    expect(params()).not.toHaveProperty('is_cruelty_free');
    expect(params()).not.toHaveProperty('is_organic');
  });

  it('unchecking a box removes its parameter instead of sending false', async () => {
    const { user, params } = setup();
    await user.click(box('Vegan'));
    await user.click(box('Vegan'));
    expect(params()).toEqual({});
    expect(params()).not.toHaveProperty('is_vegan');
  });

  it('never produces a "false" value anywhere along a sequence of toggles', async () => {
    const { user, params } = setup();
    const seen = [];
    for (const label of ['Vegan', 'Organic', 'Vegan', 'Cruelty-Free', 'Organic', 'Cruelty-Free']) {
      await user.click(box(label));
      seen.push(params());
    }
    seen.forEach((p) => {
      Object.values(p).forEach((v) => {
        expect(v).not.toBe(false);
        expect(v).not.toBe('false');
      });
    });
  });

  it('they combine freely and independently', async () => {
    const { user, params } = setup();
    await user.click(box('Cruelty-Free'));
    await user.click(box('Organic'));
    expect(params()).toEqual({ is_cruelty_free: 'true', is_organic: 'true' });
    await user.click(box('Cruelty-Free'));
    expect(params()).toEqual({ is_organic: 'true' });
  });

  it('emits only the changed flag as the patch', async () => {
    const spy = vi.fn();
    const { user } = setup({ spy });
    await user.click(box('Vegan'));
    expect(spy).toHaveBeenLastCalledWith({ is_vegan: true });
    await user.click(box('Vegan'));
    expect(spy).toHaveBeenLastCalledWith({ is_vegan: false });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('CosmeticFilters — SPF range', () => {
  const minInput = () => screen.getByLabelText('Minimum SPF');
  const maxInput = () => screen.getByLabelText('Maximum SPF');
  const apply = () => screen.getByRole('button', { name: 'Apply SPF range' });

  it('applies min_spf with the Apply button', async () => {
    const { user, params } = setup();
    await user.type(minInput(), '30');
    await user.click(apply());
    expect(params()).toEqual({ min_spf: 30 });
  });

  it('applies max_spf', async () => {
    const { user, params } = setup();
    await user.type(maxInput(), '50');
    await user.click(apply());
    expect(params()).toEqual({ max_spf: 50 });
  });

  it('applies both ends together', async () => {
    const { user, params } = setup();
    await user.type(minInput(), '15');
    await user.type(maxInput(), '50');
    await user.click(apply());
    expect(params()).toEqual({ min_spf: 15, max_spf: 50 });
  });

  it('does not apply while typing — "30" never sends min_spf=3 first', async () => {
    const spy = vi.fn();
    const { user, params } = setup({ spy });
    await user.type(minInput(), '30');
    expect(spy).not.toHaveBeenCalled();
    expect(params()).toEqual({});
  });

  it('Enter applies too', async () => {
    const { user, params } = setup();
    await user.type(minInput(), '30{Enter}');
    expect(params()).toEqual({ min_spf: 30 });
  });

  it('emptying both inputs and applying removes the SPF filter', async () => {
    const { user, params } = setup({
      initial: { ...EMPTY_COSMETIC_FILTERS, min_spf: '15', max_spf: '50' },
    });
    await user.clear(minInput());
    await user.clear(maxInput());
    await user.click(apply());
    expect(params()).toEqual({});
  });

  it('a minimum of 0 is no minimum (omitted)', async () => {
    const { user, params } = setup();
    await user.type(minInput(), '0');
    await user.click(apply());
    expect(params()).toEqual({});
  });

  it('rejects min > max with a message and applies nothing', async () => {
    const spy = vi.fn();
    const { user, params } = setup({ spy });
    await user.type(minInput(), '50');
    await user.type(maxInput(), '15');
    await user.click(apply());
    expect(screen.getByRole('alert')).toHaveTextContent(/minimum spf/i);
    expect(spy).not.toHaveBeenCalled();
    expect(params()).toEqual({});
  });

  it.each(['101', '-5', '1.5'])('rejects %s with a message and applies nothing', async (bad) => {
    const spy = vi.fn();
    const { user } = setup({ spy });
    await user.type(minInput(), bad);
    await user.click(apply());
    expect(screen.getByRole('alert')).toHaveTextContent(/whole numbers/i);
    expect(spy).not.toHaveBeenCalled();
  });

  it('clears the error after a valid apply', async () => {
    const { user } = setup();
    await user.type(minInput(), '50');
    await user.type(maxInput(), '15');
    await user.click(apply());
    expect(screen.getByRole('alert')).toBeInTheDocument();
    await user.clear(maxInput());
    await user.type(maxInput(), '60');
    await user.click(apply());
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('inputs reset when the applied values are cleared from outside ("Clear all")', () => {
    const { rerender } = render(
      <CosmeticFilters
        values={{ ...EMPTY_COSMETIC_FILTERS, min_spf: '30', max_spf: '50' }}
        onChange={() => {}}
      />,
    );
    expect(screen.getByLabelText('Minimum SPF')).toHaveValue(30);

    rerender(<CosmeticFilters values={EMPTY_COSMETIC_FILTERS} onChange={() => {}} />);

    expect(screen.getByLabelText('Minimum SPF')).toHaveValue(null);
    expect(screen.getByLabelText('Maximum SPF')).toHaveValue(null);
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('CosmeticFilters — facets combine', () => {
  it('skin type + vegan + min SPF produce all three params together', async () => {
    const { user, params } = setup();
    await user.click(box('Oily'));
    await user.click(box('Dry'));
    await user.click(box('Vegan'));
    await user.type(screen.getByLabelText('Minimum SPF'), '30');
    await user.click(screen.getByRole('button', { name: 'Apply SPF range' }));
    expect(params()).toEqual({ skin_type: 'oily,dry', is_vegan: 'true', min_spf: 30 });
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('CosmeticFilters — injectable look', () => {
  it('renders sections and options through the supplied components', async () => {
    const Section = ({ title, children }) => (
      <section data-testid={`section-${title}`} aria-label={title}>{children}</section>
    );
    const Option = ({ label, checked, onToggle }) => (
      <button type="button" aria-pressed={checked} onClick={onToggle}>{label}</button>
    );
    const { user, params } = setup({ Section, Option });

    const skin = screen.getByTestId('section-Skin Type');
    await user.click(within(skin).getByRole('button', { name: 'Oily' }));

    expect(params()).toEqual({ skin_type: 'oily' });
    expect(within(skin).getByRole('button', { name: 'Oily' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    // the default markup is not used
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('CosmeticFilters — facet counts', () => {
  const COUNTS = {
    skin_type: { oily: 12, dry: 0, combination: 3, sensitive: 0, normal: 7, all: 1 },
    hair_type: { straight: 2, wavy: 0, curly: 5, coily: 1, all: 0 },
    gender: { unisex: 10, female: 4, male: 0 },
    is_cruelty_free: 8,
    is_vegan: 0,
    is_organic: 2,
  };

  it('shows the count beside every skin-type option', () => {
    setup({ counts: COUNTS });
    ['Oily (12)', 'Dry (0)', 'Combination (3)', 'Sensitive (0)', 'Normal (7)', 'All Skin Types (1)']
      .forEach((name) => expect(box(name)).toBeInTheDocument());
  });

  it('shows the count beside every hair-type option', () => {
    setup({ counts: COUNTS });
    ['Straight (2)', 'Wavy (0)', 'Curly (5)', 'Coily (1)', 'All Hair Types (0)']
      .forEach((name) => expect(box(name)).toBeInTheDocument());
  });

  it('shows the count beside each gender', () => {
    setup({ counts: COUNTS });
    ['Unisex (10)', 'Female (4)', 'Male (0)'].forEach((name) =>
      expect(radio(name)).toBeInTheDocument(),
    );
  });

  it('shows the count beside each certification', () => {
    setup({ counts: COUNTS });
    ['Cruelty-Free (8)', 'Vegan (0)', 'Organic (2)'].forEach((name) =>
      expect(box(name)).toBeInTheDocument(),
    );
  });

  it('shows no counts at all while there are none (not loaded / failed)', () => {
    setup({ counts: null });
    expect(box('Oily')).toBeInTheDocument();
    expect(screen.queryByText(/\(\d+\)/)).not.toBeInTheDocument();
    screen.getAllByRole('checkbox').forEach((c) => expect(c).toBeEnabled());
    screen.getAllByRole('radio').forEach((r) => expect(r).toBeEnabled());
  });

  it('shows a count only for options the counts actually cover', () => {
    setup({ counts: { skin_type: { oily: 4 } } });
    expect(box('Oily (4)')).toBeInTheDocument();
    expect(box('Dry')).toBeInTheDocument(); // no count known -> plain, and enabled
    expect(box('Dry')).toBeEnabled();
    expect(box('Vegan')).toBeEnabled();
  });

  describe('options with a count of 0', () => {
    it('stay visible but are disabled', () => {
      setup({ counts: COUNTS });
      expect(box('Dry (0)')).toBeDisabled();
      expect(box('Wavy (0)')).toBeDisabled();
      expect(radio('Male (0)')).toBeDisabled();
      expect(box('Vegan (0)')).toBeDisabled();
    });

    it('are greyed out', () => {
      setup({ counts: COUNTS });
      expect(box('Dry (0)').closest('label')).toHaveClass('text-gray-400', 'cursor-not-allowed');
      expect(box('Oily (12)').closest('label')).not.toHaveClass('cursor-not-allowed');
    });

    it('options with matches stay enabled', () => {
      setup({ counts: COUNTS });
      expect(box('Oily (12)')).toBeEnabled();
      expect(radio('Female (4)')).toBeEnabled();
      expect(box('Organic (2)')).toBeEnabled();
    });

    it('cannot be selected', async () => {
      const spy = vi.fn();
      const { user, params } = setup({ counts: COUNTS, spy });
      await user.click(box('Dry (0)'));
      await user.click(radio('Male (0)'));
      await user.click(box('Vegan (0)'));
      expect(spy).not.toHaveBeenCalled();
      expect(params()).toEqual({});
    });

    it('stay enabled when already selected, so they can always be unselected', async () => {
      const { user, params } = setup({
        counts: COUNTS,
        initial: { ...EMPTY_COSMETIC_FILTERS, skin_type: ['dry'], is_vegan: true, gender: 'male' },
      });
      expect(box('Dry (0)')).toBeChecked();
      expect(box('Dry (0)')).toBeEnabled();
      expect(box('Vegan (0)')).toBeEnabled();
      expect(radio('Male (0)')).toBeEnabled();

      await user.click(box('Dry (0)'));
      await user.click(box('Vegan (0)'));
      await user.click(radio('Male (0)'));
      expect(params()).toEqual({});
    });
  });

  it('updates when new counts arrive', () => {
    const { rerender } = setup({ counts: COUNTS });
    expect(box('Oily (12)')).toBeInTheDocument();
    expect(box('Dry (0)')).toBeDisabled();

    rerender(
      <Harness counts={{ ...COUNTS, skin_type: { ...COUNTS.skin_type, oily: 5, dry: 9 } }} />,
    );

    expect(box('Oily (5)')).toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: 'Oily (12)' })).not.toBeInTheDocument();
    expect(box('Dry (9)')).toBeEnabled(); // a previously-disabled option comes back
  });

  it('passes count and disabled to an injected option component', () => {
    const Option = ({ label, count, disabled }) => (
      <span data-testid={`opt-${label}`} data-count={count} data-disabled={String(disabled)} />
    );
    setup({ counts: COUNTS, Option });
    expect(screen.getByTestId('opt-Oily')).toHaveAttribute('data-count', '12');
    expect(screen.getByTestId('opt-Oily')).toHaveAttribute('data-disabled', 'false');
    expect(screen.getByTestId('opt-Dry')).toHaveAttribute('data-count', '0');
    expect(screen.getByTestId('opt-Dry')).toHaveAttribute('data-disabled', 'true');
  });
});
