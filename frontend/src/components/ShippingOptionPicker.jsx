// src/components/ShippingOptionPicker.jsx
//
// Task 7.2.1.6: presentational (no data-fetching of its own — the parent
// Checkout page owns the getShippingQuote() call and hands the result down)
// radio-button list of carrier+rate options returned by POST
// /api/shipping/quote/. Kept as its own component so it's independently
// testable and Checkout.jsx doesn't have to carry its render logic inline.
//
// Currency formatting: there is no shared currency-formatting utility
// anywhere in this project (checked — every file that renders money does
// its own ad hoc `${Number(x).toFixed(2)}` or a locally-scoped
// `Intl.NumberFormat` `fmt` helper; there is nothing to import). This
// mirrors Checkout.jsx's OWN existing convention (`$${total.toFixed(2)}`,
// used throughout that same file for subtotal/tax/total) for consistency
// within the page this component renders inside, rather than inventing a
// new formatting utility as an out-of-scope side effect of this task.
const formatPrice = (value) => `$${Number(value).toFixed(2)}`;

const formatEstimate = (min, max) => {
  if (min === max) return `${min} day${min === 1 ? '' : 's'}`;
  return `${min}–${max} days`;
};

/**
 * Props:
 *   loading   {boolean}  a quote request is in flight
 *   error     {string}   set when the quote request itself failed (network/
 *                         server error) — distinct from a successful
 *                         response that simply contains zero options
 *   options   {Array}    [{ carrier_id, carrier_name, rate_id, price,
 *                            estimated_days_min, estimated_days_max }]
 *   selected  {{carrier_id, rate_id}|null}  the currently-chosen option
 *   onSelect  {function}  called with the full option object when chosen
 *   onChangeAddress {function}  "try a different address" escape hatch for
 *                    the empty-options case — the parent decides what that
 *                    means (e.g. focus/scroll back to the city field)
 */
const ShippingOptionPicker = ({
  loading = false,
  error = '',
  options = [],
  selected = null,
  onSelect,
  onChangeAddress,
}) => {
  if (loading) {
    return (
      <div className="space-y-2" data-testid="shipping-options-loading">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="h-14 bg-gray-100 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm"
        role="alert"
      >
        <i className="bi bi-exclamation-triangle mt-0.5"></i>
        <span>{error}</span>
      </div>
    );
  }

  if (options.length === 0) {
    return (
      <div
        className="flex flex-col gap-3 bg-amber-50 border border-amber-200 text-amber-800 px-4 py-4 rounded-xl text-sm"
        data-testid="shipping-options-empty"
      >
        <span>
          <i className="bi bi-exclamation-triangle mr-2"></i>
          Shipping is not currently available for this address; please contact support.
        </span>
        {onChangeAddress && (
          <button
            type="button"
            onClick={onChangeAddress}
            className="self-start text-amber-900 font-medium underline hover:no-underline"
          >
            Try a different address
          </button>
        )}
      </div>
    );
  }

  const isSelected = (option) =>
    Boolean(
      selected
      && String(selected.carrier_id) === String(option.carrier_id)
      && String(selected.rate_id) === String(option.rate_id),
    );

  return (
    <div className="space-y-2" data-testid="shipping-options">
      {options.map((option) => (
        <label
          key={`${option.carrier_id}-${option.rate_id}`}
          className={`flex items-center justify-between gap-3 p-3 border rounded-xl cursor-pointer transition ${isSelected(option)
            ? 'border-teal-500 bg-teal-50/50'
            : 'border-gray-200 hover:bg-gray-50'
            }`}
        >
          <span className="flex items-center gap-3">
            <input
              type="radio"
              name="shipping_option"
              value={`${option.carrier_id}-${option.rate_id}`}
              checked={isSelected(option)}
              onChange={() => onSelect(option)}
              className="w-4 h-4 accent-teal-600 flex-shrink-0"
            />
            <span className="text-sm">
              <span className="font-medium">{option.carrier_name}</span>
              <span className="block text-xs text-gray-500">
                {formatEstimate(option.estimated_days_min, option.estimated_days_max)}
              </span>
            </span>
          </span>
          <span className="text-sm font-semibold whitespace-nowrap">
            {formatPrice(option.price)}
          </span>
        </label>
      ))}
    </div>
  );
};

export default ShippingOptionPicker;
