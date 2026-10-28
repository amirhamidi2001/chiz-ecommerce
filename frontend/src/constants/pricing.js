// src/constants/pricing.js
// Client-side pricing constants. All amounts are RIAL integers (multiples of
// 10); display goes through utils/money.js. ADR 0001.
//
// The SPA must not grow its own pricing logic: the server computes and stores
// every order total. The constants below exist only for the cart/checkout
// PREVIEW and static copy, and must stay in step with the backend.

import { tomanToRial } from '../utils/money';

/** Mirrors backend PricingService.TAX_PERCENT (10%) — in BASIS POINTS (10% = 1000). */
export const TAX_BASIS_POINTS = 1000;

// Cart-page shipping ESTIMATE (the order is priced from the real ShippingRate
// at checkout). Re-baselined from the old dollar-shaped values at the same
// x10,000 factor as the data migration (4.99 -> 49,900 Rial).
export const CART_SHIPPING_OPTIONS = [
  { id: 'standard', label: 'Standard Delivery', price: 49_900, eta: '5-7 days' },
  { id: 'express', label: 'Express Delivery', price: 129_900, eta: '2-3 days' },
  { id: 'free', label: 'Free Shipping', price: 0, eta: '7-14 days', minOrder: 3_000_000 },
];
export const CART_FREE_SHIPPING_FALLBACK = 129_900;

// Static marketing copy (ShippingInfo page / header banner), same x10,000 scale.
export const STANDARD_SHIPPING_RIAL = 59_900;
export const EXPRESS_SHIPPING_RIAL = 129_900;
export const FREE_SHIPPING_THRESHOLD_RIAL = 500_000;

// Storefront price-filter slider: domain and step, in TOMAN (what shoppers see).
export const PRICE_FILTER_MAX_TOMAN = 10_000_000;
export const PRICE_FILTER_STEP_TOMAN = 10_000;
export const PRICE_FILTER_MAX_RIAL = tomanToRial(PRICE_FILTER_MAX_TOMAN);
