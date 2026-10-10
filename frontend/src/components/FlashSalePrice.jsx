// src/components/FlashSalePrice.jsx
//
// Shared flash-sale display for product CARDS. A card shows product-level
// info, but real prices are per variant, so the API gives a "starting at"
// figure (the cheapest variant with the sale applied) — see
// ProductListSerializer's flash_sale_* fields. Product cards are implemented
// separately in several places; they all use these two pieces so a sale
// looks and behaves the same everywhere.

import { isOnFlashSale } from '../utils/flashSale';

const money = (v) => `$${Number(v).toFixed(2)}`;
// "25.00" -> "25", "12.50" -> "12.5"
const percent = (v) => String(parseFloat(v));

/** "Flash Sale -25%" pill. Renders nothing for a product that isn't on sale. */
export const FlashSaleBadge = ({ product, className = '', showPercent = true }) => {
  if (!isOnFlashSale(product)) return null;
  const pct = showPercent && product.flash_sale_discount_percent != null
    ? ` -${percent(product.flash_sale_discount_percent)}%`
    : '';
  return (
    <span
      className={`inline-flex items-center gap-1 bg-red-600 text-white text-xs font-bold px-2 py-1 rounded ${className}`}
    >
      <i className="bi bi-lightning-charge-fill" aria-hidden="true"></i>
      Flash Sale{pct}
    </span>
  );
};

const SIZES = { sm: 'text-sm', base: 'text-base', lg: 'text-lg', xl: 'text-xl' };

/**
 * The discounted price with the pre-sale price struck through beside it
 * ("From" in front when the product's variants differ in price).
 * Renders nothing for a product that isn't on sale.
 */
export const FlashSalePrice = ({ product, size = 'base', className = '' }) => {
  if (!isOnFlashSale(product)) return null;
  return (
    <span className={`inline-flex items-baseline gap-1.5 flex-wrap ${className}`}>
      {product.flash_sale_price_varies && (
        <span className="text-xs text-gray-500">From</span>
      )}
      <span className={`font-bold text-red-600 ${SIZES[size] || SIZES.base}`}>
        {money(product.flash_sale_price)}
      </span>
      <del className="text-xs text-gray-400" aria-label="Original price">
        {money(product.flash_sale_original_price)}
      </del>
    </span>
  );
};
