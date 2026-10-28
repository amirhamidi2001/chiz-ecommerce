import { formatToman } from '../utils/money';
// src/components/VariantPicker.jsx
//
// A small, controlled picker for choosing ONE of a product's variants
// (shade / size). Built for the wishlist's "move to cart" flow, where the
// server answers 300 with the purchasable variants and the customer must
// pick. The product page does its own colour selection inline against
// page state, so there was no reusable picker to share.
//
// Props
//   variants   {Array}    ProductVariantSerializer payloads
//   selectedId {number|null}
//   onSelect   {(id) => void}
//   disabled   {boolean}  optional
//   label      {string}   accessible name for the group, optional

const formatPrice = (n) => formatToman(n);

/** "Rose · 30 ml" — colour name, then size; the SKU if it has neither. */
const variantLabel = (variant) => {
  const parts = [
    variant.color?.name,
    variant.volume_ml ? `${variant.volume_ml} ml` : null,
    variant.weight_g ? `${variant.weight_g} g` : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(' · ') : variant.sku;
};

const VariantPicker = ({
  variants,
  selectedId,
  onSelect,
  disabled = false,
  label = 'Choose an option',
}) => (
  <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2">
    {variants.map((variant) => {
      const selected = variant.id === selectedId;
      const price = variant.effective_price ?? variant.price;
      const discounted = Number(price) < Number(variant.price);

      return (
        <button
          key={variant.id}
          type="button"
          role="radio"
          aria-checked={selected}
          disabled={disabled}
          onClick={() => onSelect(variant.id)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs transition disabled:opacity-60 ${
            selected
              ? 'border-teal-600 bg-teal-50 text-teal-800'
              : 'border-gray-200 bg-white text-gray-700 hover:border-gray-400'
          }`}
        >
          {variant.color?.hex_code && (
            <span
              aria-hidden="true"
              className="w-4 h-4 rounded-full border border-gray-300 inline-block"
              style={{ backgroundColor: variant.color.hex_code }}
            />
          )}
          <span className="font-medium">{variantLabel(variant)}</span>
          <span className="text-gray-500">
            {formatPrice(price)}
            {discounted && (
              <span className="ml-1 line-through text-gray-400">
                {formatPrice(variant.price)}
              </span>
            )}
          </span>
        </button>
      );
    })}
  </div>
);

export default VariantPicker;
