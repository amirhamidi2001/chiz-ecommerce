import { describe, expect, it } from 'vitest';
import { normalizeCart, normalizeCartItem } from '../cartShape';

// The real GET /api/cart/ item (captured from the Django backend).
const API_ITEM = {
  id: 6,
  variant: {
    id: 67, sku: 'SKU-020-0', color: { id: 13, name: 'Rose', hex_code: '#f43f5e' },
    price: 3083900, original_price: 3854870, stock: 3,
    product: { id: 20, name: 'Trail Running Backpack', slug: 'trail-running-backpack', image: 'http://x/media/a.webp' },
  },
  quantity: 2, unit_price: 3083900, subtotal: 6167800,
};

describe('normalizeCartItem', () => {
  it('builds item.product from the variant for the real API shape', () => {
    const item = normalizeCartItem(API_ITEM);
    expect(item.product).toMatchObject({
      name: 'Trail Running Backpack', slug: 'trail-running-backpack', image: 'http://x/media/a.webp',
      price: 3083900, original_price: 3854870, stock: 3, sku: 'SKU-020-0', variant_id: 67,
    });
    expect(item.product.color.name).toBe('Rose');
  });

  it('keeps everything else on the item (variant, quantity, totals)', () => {
    const item = normalizeCartItem(API_ITEM);
    expect(item).toMatchObject({ id: 6, quantity: 2, unit_price: 3083900, subtotal: 6167800 });
    expect(item.variant).toBe(API_ITEM.variant);
  });

  it('does not mutate its input', () => {
    const copy = JSON.stringify(API_ITEM);
    normalizeCartItem(API_ITEM);
    expect(JSON.stringify(API_ITEM)).toBe(copy);
  });

  it('is idempotent and leaves old-shape items (already have product) untouched', () => {
    const old = { id: 1, product: { name: 'Old', stock: 5 }, quantity: 1 };
    expect(normalizeCartItem(old)).toBe(old);
    const once = normalizeCartItem(API_ITEM);
    expect(normalizeCartItem(once)).toBe(once);
  });

  it('copes with a variant that has no nested product', () => {
    expect(normalizeCartItem({ id: 2, variant: { id: 1, price: 10, stock: 0 }, quantity: 1 }).product)
      .toMatchObject({ price: 10, stock: 0 });
  });

  it('passes through junk', () => {
    expect(normalizeCartItem(null)).toBeNull();
    expect(normalizeCartItem({ id: 3 })).toEqual({ id: 3 });
  });
});

describe('normalizeCart', () => {
  it('normalises every item and keeps the cart fields', () => {
    const cart = normalizeCart({ id: 1, subtotal: 5, coupon_code: 'X', items: [API_ITEM, API_ITEM] });
    expect(cart.items.every((i) => i.product && i.product.name === 'Trail Running Backpack')).toBe(true);
    expect(cart).toMatchObject({ id: 1, subtotal: 5, coupon_code: 'X' });
  });

  it('returns null / a cart without items unchanged', () => {
    expect(normalizeCart(null)).toBeNull();
    const noItems = { id: 1 };
    expect(normalizeCart(noItems)).toBe(noItems);
  });
});
