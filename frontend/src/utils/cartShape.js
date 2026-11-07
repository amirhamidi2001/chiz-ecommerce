// Found by the RTL QA pass (Task 14.3.3.1) rendering the real backend:
// GET /api/cart/ returns each item as { variant: { price, original_price, stock, color,
// product: { name, slug, image } }, quantity, unit_price, subtotal }, but the Cart and
// Checkout pages read `item.product.*` (the shape from before the ProductVariant
// migration), so both threw "Cannot read properties of undefined" and rendered a blank
// page for anyone with items in their cart. The unit tests mock the OLD shape, so they
// never noticed.
//
// This adapts the API shape ONCE, in CartContext, instead of editing every reader. It
// is idempotent and leaves items that already have `product` (the old shape) untouched.

/** Adds `item.product` (name/slug/image from the variant's product, plus the variant's
 *  price, original_price, stock, color, sku) to an item that only has `item.variant`. */
export function normalizeCartItem(item) {
  if (!item || item.product || !item.variant) return item;
  const { variant } = item;
  const product = variant.product || {};
  return {
    ...item,
    product: {
      ...product,
      price: variant.price,
      original_price: variant.original_price,
      stock: variant.stock,
      sku: variant.sku,
      color: variant.color,
      variant_id: variant.id,
    },
  };
}

/** Normalises every item of a cart payload; returns anything else unchanged. */
export function normalizeCart(cart) {
  if (!cart || !Array.isArray(cart.items)) return cart;
  return { ...cart, items: cart.items.map(normalizeCartItem) };
}
