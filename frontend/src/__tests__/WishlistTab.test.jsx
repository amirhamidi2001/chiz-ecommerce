import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import WishlistTab from '../components/WishlistTab';

// ─── Module mocks ─────────────────────────────────────────────────────────────
vi.mock('../context/WishlistContext', () => ({ useWishlist: vi.fn() }));
vi.mock('../context/CartContext', () => ({ useCart: vi.fn() }));
vi.mock('../services/api', () => ({
  dashboardAPI: {
    moveWishlistItemToCart: vi.fn(),
    moveAllWishlistToCart: vi.fn(),
  },
}));

import { useWishlist } from '../context/WishlistContext';
import { useCart } from '../context/CartContext';
import { dashboardAPI } from '../services/api';
import { formatToman } from '../utils/money';

// ─── Fixtures ─────────────────────────────────────────────────────────────────
const product = (id, name) => ({
  id, name, slug: `p-${id}`, price: 200_000, original_price: null,
  rating: 4, reviews_count: 3, thumbnail_url: null,
  // Product.stock is the legacy field and is deliberately 0 here: moving must
  // not be gated on it.
  stock: 0,
});
const ITEM_A = { id: 11, product: product(1, 'Lip Balm') };
const ITEM_B = { id: 22, product: product(2, 'Lipstick') };

const SHADES = [
  { id: 201, sku: 'LS-ROSE', price: 100_000, effective_price: 100_000,
    color: { id: 1, name: 'Rose', hex_code: '#ff0066' } },
  { id: 202, sku: 'LS-NUDE', price: 120_000, effective_price: 120_000,
    color: { id: 2, name: 'Nude', hex_code: '#d2b48c' } },
];

const needsChoice = (variants = SHADES) => ({
  response: { status: 300, data: { needs_selection: true, variants } },
});
const failure = (status, data) => ({ response: { status, data } });

let refreshWishlist;
let refreshCart;

const renderTab = (items = [ITEM_A, ITEM_B]) => {
  refreshWishlist = vi.fn().mockResolvedValue(true);
  refreshCart = vi.fn().mockResolvedValue(true);
  useWishlist.mockReturnValue({
    wishlist: items, loading: false,
    removeFromWishlist: vi.fn(), fetchWishlist: vi.fn(), refreshWishlist,
  });
  // No addToCart on purpose: the old product-id-as-variant-id path is gone.
  useCart.mockReturnValue({ refreshCart });
  return render(<MemoryRouter><WishlistTab /></MemoryRouter>);
};

const cardFor = (name) => screen.getByRole('heading', { name }).closest('div.bg-white');
const moveButtonIn = (card) => within(card).getByRole('button', { name: /Move to Cart/ });

beforeEach(() => vi.clearAllMocks());

// ═════════════════════════════════════════════════════════════════════════════
describe('buttons', () => {
  it('shows Move to Cart per item and a Move All to Cart button', () => {
    renderTab();
    expect(screen.getAllByRole('button', { name: /Move to Cart/ })).toHaveLength(2);
    expect(screen.getByRole('button', { name: /Move All to Cart/ })).toBeInTheDocument();
  });

  it('no longer offers the old product-id "Add to Cart" buttons', () => {
    renderTab();
    expect(screen.queryByRole('button', { name: /^Add to Cart/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Add All to Cart/ })).not.toBeInTheDocument();
  });

  it('does not disable a move because the legacy Product.stock is 0', () => {
    renderTab();
    expect(moveButtonIn(cardFor('Lip Balm'))).toBeEnabled();
    expect(screen.queryByText('Out of Stock')).not.toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('moving a single item', () => {
  it('moves an unambiguous item, toasts, and refreshes BOTH wishlist and cart', async () => {
    dashboardAPI.moveWishlistItemToCart.mockResolvedValueOnce({ data: { detail: 'Moved to cart.' } });
    renderTab();

    await userEvent.click(moveButtonIn(cardFor('Lip Balm')));

    expect(dashboardAPI.moveWishlistItemToCart).toHaveBeenCalledWith(11, undefined);
    expect(await screen.findByText('Lip Balm moved to cart!')).toBeInTheDocument();
    await waitFor(() => {
      expect(refreshWishlist).toHaveBeenCalledTimes(1);
      expect(refreshCart).toHaveBeenCalledTimes(1);
    });
  });

  it('on 300 shows an inline picker (and moves nothing yet)', async () => {
    dashboardAPI.moveWishlistItemToCart.mockRejectedValueOnce(needsChoice());
    renderTab();

    await userEvent.click(moveButtonIn(cardFor('Lipstick')));

    const picker = await within(cardFor('Lipstick')).findByRole('radiogroup');
    expect(within(picker).getAllByRole('radio')).toHaveLength(2);
    expect(refreshWishlist).not.toHaveBeenCalled();
    expect(refreshCart).not.toHaveBeenCalled();
  });

  it('keeps the confirm button disabled until an option is picked', async () => {
    dashboardAPI.moveWishlistItemToCart.mockRejectedValueOnce(needsChoice());
    renderTab();
    await userEvent.click(moveButtonIn(cardFor('Lipstick')));

    const confirm = await screen.findByRole('button', { name: /Move selected option/ });
    expect(confirm).toBeDisabled();
    await userEvent.click(screen.getByRole('radio', { name: /Nude/ }));
    expect(confirm).toBeEnabled();
  });

  it('resubmits with the chosen variant_id, then closes the picker and refreshes both lists', async () => {
    dashboardAPI.moveWishlistItemToCart
      .mockRejectedValueOnce(needsChoice())
      .mockResolvedValueOnce({ data: { detail: 'Moved to cart.' } });
    renderTab();
    await userEvent.click(moveButtonIn(cardFor('Lipstick')));

    await userEvent.click(await screen.findByRole('radio', { name: /Nude/ }));
    await userEvent.click(screen.getByRole('button', { name: /Move selected option/ }));

    await waitFor(() =>
      expect(dashboardAPI.moveWishlistItemToCart).toHaveBeenLastCalledWith(22, 202),
    );
    expect(await screen.findByText('Lipstick moved to cart!')).toBeInTheDocument();
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
    await waitFor(() => {
      expect(refreshWishlist).toHaveBeenCalledTimes(1);
      expect(refreshCart).toHaveBeenCalledTimes(1);
    });
  });

  it('shows the server message when the product is unavailable, and refreshes nothing', async () => {
    dashboardAPI.moveWishlistItemToCart.mockRejectedValueOnce(
      failure(400, { detail: 'This product is currently unavailable.' }),
    );
    renderTab();

    await userEvent.click(moveButtonIn(cardFor('Lip Balm')));

    expect(await screen.findByText('This product is currently unavailable.')).toBeInTheDocument();
    expect(refreshWishlist).not.toHaveBeenCalled();
    expect(refreshCart).not.toHaveBeenCalled();
  });

  it('on a stale pick: drops the picker, says so, and refreshes (never guesses a replacement)', async () => {
    dashboardAPI.moveWishlistItemToCart
      .mockRejectedValueOnce(needsChoice())
      .mockRejectedValueOnce(failure(400, { variant_id: 'Invalid variant for this product.' }));
    renderTab();
    await userEvent.click(moveButtonIn(cardFor('Lipstick')));
    await userEvent.click(await screen.findByRole('radio', { name: /Rose/ }));
    await userEvent.click(screen.getByRole('button', { name: /Move selected option/ }));

    expect(await screen.findByText(/no longer available — please choose again/)).toBeInTheDocument();
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
    await waitFor(() => expect(refreshWishlist).toHaveBeenCalled());
    expect(dashboardAPI.moveWishlistItemToCart).toHaveBeenCalledTimes(2); // no auto-retry
  });

  it('on 404 (already moved elsewhere) tells the user and refreshes', async () => {
    dashboardAPI.moveWishlistItemToCart.mockRejectedValueOnce(failure(404, { detail: 'Not found.' }));
    renderTab();

    await userEvent.click(moveButtonIn(cardFor('Lip Balm')));

    expect(await screen.findByText('That item is no longer on your wishlist.')).toBeInTheDocument();
    await waitFor(() => expect(refreshWishlist).toHaveBeenCalled());
  });

  it('disables the button while the request is in flight', async () => {
    let release;
    dashboardAPI.moveWishlistItemToCart.mockReturnValueOnce(
      new Promise((resolve) => { release = () => resolve({ data: {} }); }),
    );
    renderTab();

    await userEvent.click(moveButtonIn(cardFor('Lip Balm')));

    expect(within(cardFor('Lip Balm')).getByRole('button', { name: /Moving/ })).toBeDisabled();
    release();
    await waitFor(() => expect(refreshWishlist).toHaveBeenCalled());
  });
});

// ═════════════════════════════════════════════════════════════════════════════
describe('Move All to Cart', () => {
  const MIXED = {
    moved: ['Lip Balm', 'Mascara'],
    needs_selection: [{ wishlist_item_id: 22, product: 'Lipstick', variants: SHADES }],
    unavailable: [{ wishlist_item_id: 33, product: 'Old Gloss' }],
  };

  const moveAll = async () => {
    dashboardAPI.moveAllWishlistToCart.mockResolvedValueOnce({ data: MIXED });
    renderTab();
    await userEvent.click(screen.getByRole('button', { name: /Move All to Cart/ }));
    return screen.findByRole('region', { name: /Move to cart summary/ });
  };

  it('summarises what moved, what needs a choice, and what is unavailable', async () => {
    const summary = await moveAll();

    expect(within(summary).getByText('2 items moved to your cart')).toBeInTheDocument();
    expect(within(summary).getByText('Mascara')).toBeInTheDocument();
    expect(within(summary).getByText(/Choose an option to finish moving this item/)).toBeInTheDocument();
    expect(within(summary).getByText('Lipstick')).toBeInTheDocument();
    expect(within(summary).getByText(/Currently unavailable/)).toBeInTheDocument();
    expect(within(summary).getByText('Old Gloss')).toBeInTheDocument();
  });

  it('refreshes both wishlist and cart after the bulk move', async () => {
    await moveAll();
    await waitFor(() => {
      expect(refreshWishlist).toHaveBeenCalledTimes(1);
      expect(refreshCart).toHaveBeenCalledTimes(1);
    });
  });

  it('gives each ambiguous item its own inline picker inside the summary', async () => {
    const summary = await moveAll();
    expect(within(summary).getByRole('radiogroup')).toBeInTheDocument();
    expect(within(summary).getAllByRole('radio')).toHaveLength(2);
  });

  it('finishes an ambiguous item from the summary with the chosen variant, then removes its row', async () => {
    const summary = await moveAll();
    dashboardAPI.moveWishlistItemToCart.mockResolvedValueOnce({ data: { detail: 'Moved to cart.' } });

    await userEvent.click(within(summary).getByRole('radio', { name: /Rose/ }));
    await userEvent.click(within(summary).getByRole('button', { name: /Move selected option/ }));

    await waitFor(() =>
      expect(dashboardAPI.moveWishlistItemToCart).toHaveBeenCalledWith(22, 201),
    );
    await waitFor(() => expect(within(summary).queryByRole('radiogroup')).not.toBeInTheDocument());
    // The already-moved and unavailable reports stay visible.
    expect(within(summary).getByText('Mascara')).toBeInTheDocument();
    expect(within(summary).getByText('Old Gloss')).toBeInTheDocument();
    expect(refreshWishlist).toHaveBeenCalledTimes(2); // bulk + the follow-up
    expect(refreshCart).toHaveBeenCalledTimes(2);
  });

  it('can be dismissed', async () => {
    const summary = await moveAll();
    await userEvent.click(within(summary).getByRole('button', { name: 'Dismiss' }));
    expect(screen.queryByRole('region', { name: /Move to cart summary/ })).not.toBeInTheDocument();
  });

  it('says so plainly when nothing could be moved automatically', async () => {
    dashboardAPI.moveAllWishlistToCart.mockResolvedValueOnce({
      data: { moved: [], needs_selection: MIXED.needs_selection, unavailable: [] },
    });
    renderTab();
    await userEvent.click(screen.getByRole('button', { name: /Move All to Cart/ }));

    expect(await screen.findByText('Nothing could be moved automatically')).toBeInTheDocument();
    expect(screen.queryByText(/Currently unavailable/)).not.toBeInTheDocument();
  });

  it('uses singular wording for one moved item', async () => {
    dashboardAPI.moveAllWishlistToCart.mockResolvedValueOnce({
      data: { moved: ['Lip Balm'], needs_selection: [], unavailable: [] },
    });
    renderTab();
    await userEvent.click(screen.getByRole('button', { name: /Move All to Cart/ }));
    expect(await screen.findByText('1 item moved to your cart')).toBeInTheDocument();
  });

  it('toasts an error and shows no summary if the request fails', async () => {
    dashboardAPI.moveAllWishlistToCart.mockRejectedValueOnce(failure(500, {}));
    renderTab();

    await userEvent.click(screen.getByRole('button', { name: /Move All to Cart/ }));

    expect(await screen.findByText('Could not move items to cart')).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: /Move to cart summary/ })).not.toBeInTheDocument();
    expect(refreshCart).not.toHaveBeenCalled();
  });

  it('does not show a second picker on the card for an item the summary already hosts', async () => {
    dashboardAPI.moveWishlistItemToCart.mockRejectedValueOnce(needsChoice());
    renderTab();
    // Single flow first (card picker), then a bulk run that lists the same item.
    await userEvent.click(moveButtonIn(cardFor('Lipstick')));
    await within(cardFor('Lipstick')).findByRole('radiogroup');
    dashboardAPI.moveAllWishlistToCart.mockResolvedValueOnce({ data: MIXED });
    await userEvent.click(screen.getByRole('button', { name: /Move All to Cart/ }));

    const summary = await screen.findByRole('region', { name: /Move to cart summary/ });
    expect(within(summary).getAllByRole('radiogroup')).toHaveLength(1);
    expect(within(cardFor('Lipstick')).queryByRole('radiogroup')).not.toBeInTheDocument();
  });
});

// ═════════════════════════════════════════════════════════════════════════════
// Numeral styles (Task 14.1.2.4): review counts Persian, prices Western.
describe('numeral styles', () => {
  it('shows each product\'s review count in Persian digits and its price in Western', () => {
    renderTab();
    const card = cardFor('Lip Balm');

    expect(within(card).getByText('(۳)')).toBeInTheDocument();
    expect(within(card).queryByText('(3)')).not.toBeInTheDocument();
    expect(within(card).getByText(formatToman(200_000))).toBeInTheDocument();
  });
});
