// src/components/CosmeticFilters.jsx
import { useState } from 'react';
import {
  SKIN_TYPE_OPTIONS,
  HAIR_TYPE_OPTIONS,
  GENDER_OPTIONS,
  CERTIFICATION_OPTIONS,
  SPF_MAX,
  parseSpf,
  toggleListValue,
  EMPTY_COSMETIC_FILTERS,
} from '../utils/cosmeticFilters';

// The cosmetics filter sections: skin type, hair type, SPF, gender and the
// certification flags. Presentational and controlled — the page owns the
// filter state (see utils/cosmeticFilters.js for how it maps to the API).
//
// Facet counts: pass `counts` (the /products/facet-counts/ response) to show
// "Oily (12)" beside each option. An option whose count is 0 is shown greyed
// out and disabled — still visible, so the customer sees it exists and why it
// can't be picked — EXCEPT when it is currently checked, which always stays
// enabled so it can be unchecked. With no `counts` (not loaded yet, or the
// request failed) options render exactly as before.
//
// The two listing pages (Category, SearchResults) have different sidebar
// styles, so the look is injected rather than invented here:
//   Section({ title, children })                      — a titled filter group
//   Option({ type, name, label, checked, onToggle, count, disabled }) — one checkbox/radio row
// The defaults match Category's sidebar.

// ─── Default look (Category sidebar) ──────────────────────────────────────────
export const DefaultSection = ({ title, children }) => (
  <div className="widget-item mb-6">
    <h3 className="text-lg font-semibold border-l-4 border-teal-600 pl-3 mb-4">{title}</h3>
    <div className="space-y-2">{children}</div>
  </div>
);

export const DefaultOption = ({
  type = 'checkbox', name, label, checked, onToggle, count, disabled = false,
}) => (
  <label
    className={`flex items-center gap-2 ${disabled ? 'cursor-not-allowed text-gray-400' : 'cursor-pointer'}`}
  >
    <input
      type={type}
      name={name}
      checked={checked}
      disabled={disabled}
      // A radio's onChange only fires when it becomes checked; clicking the
      // already-selected one fires onClick instead — used to deselect it.
      onChange={type === 'radio' ? () => { if (!checked) onToggle(); } : onToggle}
      onClick={type === 'radio' ? () => { if (checked) onToggle(); } : undefined}
      className="rounded text-teal-600 focus:ring-teal-500"
    />
    <span className="text-sm">
      {label}
      {/* the space is its own text node: inside the <span> it is dropped from
          the accessible name, which would then read "Oily(12)" */}
      {count !== undefined && <>{' '}<span className="text-gray-400">({count})</span></>}
    </span>
  </label>
);

// ─── SPF range ────────────────────────────────────────────────────────────────
// Two number inputs applied together (Enter or the Apply button) rather than
// on every keystroke, so typing "30" doesn't fire a request for SPF 3 first.
// Remounted (via `key`) whenever the applied values change from outside —
// e.g. "Clear all" — so the drafts never show stale text.
const SpfRange = ({ min, max, onApply }) => {
  const [draftMin, setDraftMin] = useState(min);
  const [draftMax, setDraftMax] = useState(max);
  const [error, setError] = useState('');

  const submit = (e) => {
    e.preventDefault();
    const lo = parseSpf(draftMin);
    const hi = parseSpf(draftMax);
    if (lo === null || hi === null) {
      setError(`Enter whole numbers from 0 to ${SPF_MAX}.`);
      return;
    }
    if (lo !== '' && hi !== '' && Number(lo) > Number(hi)) {
      setError('Minimum SPF can’t be higher than maximum.');
      return;
    }
    setError('');
    onApply(lo, hi);
  };

  const inputClass =
    'w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-teal-500';

  return (
    <form onSubmit={submit} noValidate>
      <div className="flex items-center gap-2">
        <input
          type="number"
          min="0"
          max={SPF_MAX}
          step="1"
          value={draftMin}
          onChange={(e) => setDraftMin(e.target.value)}
          placeholder="Min"
          aria-label="Minimum SPF"
          className={inputClass}
        />
        <span className="text-gray-400 flex-shrink-0">–</span>
        <input
          type="number"
          min="0"
          max={SPF_MAX}
          step="1"
          value={draftMax}
          onChange={(e) => setDraftMax(e.target.value)}
          placeholder="Max"
          aria-label="Maximum SPF"
          className={inputClass}
        />
      </div>
      {error && (
        <p role="alert" className="mt-2 text-xs text-red-500">{error}</p>
      )}
      <button
        type="submit"
        // Distinct from other "Apply" buttons on the page (e.g. price range).
        aria-label="Apply SPF range"
        className="mt-2 w-full bg-teal-600 text-white text-sm rounded-lg py-1.5 hover:bg-teal-700 transition"
      >
        Apply
      </button>
    </form>
  );
};

// ─── CosmeticFilters ──────────────────────────────────────────────────────────
/**
 * @param values   current filter state (see EMPTY_COSMETIC_FILTERS)
 * @param onChange called with a PATCH — only the keys that changed,
 *                 e.g. { is_vegan: true } or { skin_type: ['dry', 'oily'] }
 * @param counts   optional facet counts, see the note at the top of the file
 */
const CosmeticFilters = ({
  values = EMPTY_COSMETIC_FILTERS,
  onChange,
  counts = null,
  Section: SectionProp,
  Option: OptionProp,
}) => {
  // Aliased to capitalised consts so JSX can use them (and so the lint rule,
  // which only exempts capitalised variables, doesn't flag them as unused).
  const Section = SectionProp ?? DefaultSection;
  const OptionRow = OptionProp ?? DefaultOption;
  const f = { ...EMPTY_COSMETIC_FILTERS, ...values };

  // undefined when counts aren't available (so nothing is shown / disabled).
  const listCount = (facet, value) => counts?.[facet]?.[value];
  const flagCount = (key) => (typeof counts?.[key] === 'number' ? counts[key] : undefined);
  // Out of matches AND not currently selected -> can't usefully be picked.
  const isDead = (count, checked) => count === 0 && !checked;

  const renderMulti = (facet, options) =>
    options.map((o) => {
      const checked = f[facet].includes(o.value);
      const count = listCount(facet, o.value);
      return (
        <OptionRow
          key={o.value}
          type="checkbox"
          name={facet}
          label={o.label}
          checked={checked}
          count={count}
          disabled={isDead(count, checked)}
          onToggle={() => onChange({ [facet]: toggleListValue(f[facet], o.value, options) })}
        />
      );
    });

  return (
    <>
      <Section title="Skin Type">{renderMulti('skin_type', SKIN_TYPE_OPTIONS)}</Section>

      <Section title="Hair Type">{renderMulti('hair_type', HAIR_TYPE_OPTIONS)}</Section>

      <Section title="SPF">
        <SpfRange
          key={`${f.min_spf}|${f.max_spf}`}
          min={f.min_spf}
          max={f.max_spf}
          onApply={(min_spf, max_spf) => onChange({ min_spf, max_spf })}
        />
      </Section>

      <Section title="Gender">
        {GENDER_OPTIONS.map((o) => {
          const checked = f.gender === o.value;
          const count = listCount('gender', o.value);
          return (
            <OptionRow
              key={o.value}
              type="radio"
              name="gender"
              label={o.label}
              checked={checked}
              count={count}
              disabled={isDead(count, checked)}
              // Single-select: picking another replaces it; picking the
              // selected one again clears it.
              onToggle={() => onChange({ gender: f.gender === o.value ? '' : o.value })}
            />
          );
        })}
      </Section>

      <Section title="Certifications">
        {CERTIFICATION_OPTIONS.map(({ key, label }) => {
          const count = flagCount(key);
          return (
            <OptionRow
              key={key}
              type="checkbox"
              name={key}
              label={label}
              checked={f[key]}
              count={count}
              disabled={isDead(count, f[key])}
              onToggle={() => onChange({ [key]: !f[key] })}
            />
          );
        })}
      </Section>
    </>
  );
};

export default CosmeticFilters;
