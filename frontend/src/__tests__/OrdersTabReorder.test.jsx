// "Reorder": re-add a past order's items to the cart, report what could not be
// added (and why), offer a link to the cart, and refresh the cart context.
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

vi.mock('../services/api', () => ({
  dashboardAPI: {
    getOrders: vi.fn(),
    getOrder: vi.fn(),
    downloadInvoice: vi.fn(),
    reorderOrder: vi.fn(),
  },
}));
vi.mock('../components/ShipmentTrackingWidget', () => ({ default: () => null }));
vi.mock('../utils/download', () => ({ saveBlob: vi.fn() }));
vi.mock('../context/CartContext', () => ({ useCart: vi.fn() }));

import OrdersTab from '../components/OrdersTab';
import { dashboardAPI } from '../services/api';
import { useCart } from '../context/CartContext';

const order = (over = {}) => ({
  id: 7,
  order_number: 'ORD-ABC123',
  status: 'delivered',
  created_at: '2026-01-15T12:00:00Z',
  items_count: 2,
  subtotal: 500_000,
  shipping_cost: 0,
  tax: 0,
  discount: 0,
  total: 500_000,
  items: [],
  shipment: null,
  ...over,
});

let refreshCart;

const renderTab = async (orders = [order()]) => {
  dashboardAPI.getOrders.mockResolvedValue({ data: { count: orders.length, results: orders } });
  dashboardAPI.getOrder.mockImplementation((id) =>
    Promise.resolve({ data: orders.find((o) => o.id === id) }),
  );
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={['/account']}>
      <Routes>
        <Route path="/account" element={<OrdersTab />} />
        <Route path="/cart" element={<div>CART PAGE</div>} />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByText(orders[0].order_number);
  return user;
};

const allAdded = { added_count: 2, added: ['Rose Serum', 'Day Cream'], unavailable: [] };
const partial = {
  added_count: 1,
  added: ['Rose Serum'],
  unavailable: [
    { product_name: 'Day Cream', reason: 'This product variant is out of stock.', reason_code: 'out_of_stock' },
    { product_name: 'Old Mask', reason: 'This product variant is unavailable.', reason_code: 'unavailable' },
  ],
};

describe('OrdersTab — Reorder button visibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    refreshCart = vi.fn().mockResolvedValue(true);
    useCart.mockReturnValue({ refreshCart });
  });

  it.each(['delivered', 'cancelled'])('is offered for a %s order', async (status) => {
    await renderTab([order({ status })]);
    expect(screen.getByTestId('reorder-button')).toBeEnabled();
  });

  it.each(['pending', 'processing', 'shipped'])('is hidden for an in-flight %s order', async (status) => {
    await renderTab([order({ status })]);
    expect(screen.queryByTestId('reorder-button')).toBeNull();
  });

  it('only appears on the finished orders in a mixed list', async () => {
    await renderTab([
      order({ id: 1, order_number: 'ORD-1', status: 'delivered' }),
      order({ id: 2, order_number: 'ORD-2', status: 'processing' }),
    ]);
    expect(screen.getAllByTestId('reorder-button')).toHaveLength(1);
  });

  it('is also available in the order detail modal', async () => {
    const user = await renderTab();
    await user.click(screen.getByText(/view details/i));
    const modal = (await screen.findByText('Order ORD-ABC123')).closest('.max-w-2xl');
    expect(within(modal).getByTestId('reorder-button')).toBeInTheDocument();
  });
});

describe('OrdersTab — Reorder action', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    refreshCart = vi.fn().mockResolvedValue(true);
    useCart.mockReturnValue({ refreshCart });
  });

  it('calls the reorder endpoint with the order id', async () => {
    dashboardAPI.reorderOrder.mockResolvedValue({ data: allAdded });
    const user = await renderTab();
    await user.click(screen.getByTestId('reorder-button'));
    await screen.findByTestId('reorder-result');
    expect(dashboardAPI.reorderOrder).toHaveBeenCalledTimes(1);
    expect(dashboardAPI.reorderOrder).toHaveBeenCalledWith(7);
  });

  it('summarises a full success with no "not added" section', async () => {
    dashboardAPI.reorderOrder.mockResolvedValue({ data: allAdded });
    const user = await renderTab();
    await user.click(screen.getByTestId('reorder-button'));
    expect(await screen.findByTestId('reorder-summary')).toHaveTextContent('2 items added to your cart');
    expect(screen.queryByTestId('reorder-unavailable')).toBeNull();
  });

  it('reports each unavailable item with its reason on a partial success', async () => {
    dashboardAPI.reorderOrder.mockResolvedValue({ data: partial });
    const user = await renderTab();
    await user.click(screen.getByTestId('reorder-button'));

    expect(await screen.findByTestId('reorder-summary')).toHaveTextContent('1 item added to your cart');
    const list = screen.getByTestId('reorder-unavailable');
    expect(within(list).getByText('Day Cream')).toBeInTheDocument();
    expect(list).toHaveTextContent('Day Cream — This product variant is out of stock.');
    expect(list).toHaveTextContent('Old Mask — This product variant is unavailable.');
  });

  it('says so, with reasons and no cart link, when nothing could be added', async () => {
    dashboardAPI.reorderOrder.mockResolvedValue({
      data: { added_count: 0, added: [], unavailable: partial.unavailable },
    });
    const user = await renderTab();
    await user.click(screen.getByTestId('reorder-button'));

    expect(await screen.findByTestId('reorder-summary')).toHaveTextContent(/none of these items/i);
    expect(screen.getByTestId('reorder-unavailable')).toBeInTheDocument();
    expect(screen.queryByTestId('reorder-go-to-cart')).toBeNull();
    expect(refreshCart).not.toHaveBeenCalled(); // the cart did not change
  });

  it('refreshes the cart context after a successful reorder', async () => {
    dashboardAPI.reorderOrder.mockResolvedValue({ data: partial });
    const user = await renderTab();
    await user.click(screen.getByTestId('reorder-button'));
    await screen.findByTestId('reorder-result');
    expect(refreshCart).toHaveBeenCalledTimes(1);
  });

  it('"Go to cart" navigates to /cart', async () => {
    dashboardAPI.reorderOrder.mockResolvedValue({ data: allAdded });
    const user = await renderTab();
    await user.click(screen.getByTestId('reorder-button'));
    await user.click(await screen.findByTestId('reorder-go-to-cart'));
    expect(await screen.findByText('CART PAGE')).toBeInTheDocument();
  });

  it('disables the button and shows progress while the request is in flight', async () => {
    let resolve;
    dashboardAPI.reorderOrder.mockReturnValue(new Promise((r) => { resolve = r; }));
    const user = await renderTab();
    await user.click(screen.getByTestId('reorder-button'));

    expect(screen.getByTestId('reorder-button')).toBeDisabled();
    expect(screen.getByTestId('reorder-button')).toHaveTextContent(/adding to cart/i);

    resolve({ data: allAdded });
    await waitFor(() => expect(screen.getByTestId('reorder-button')).toBeEnabled());
    expect(screen.getByTestId('reorder-button')).toHaveTextContent('Reorder');
  });

  it('shows an error (not a success) when the request fails, and can retry', async () => {
    dashboardAPI.reorderOrder.mockRejectedValueOnce(new Error('500'));
    dashboardAPI.reorderOrder.mockResolvedValueOnce({ data: allAdded });
    const user = await renderTab();

    await user.click(screen.getByTestId('reorder-button'));
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not reorder/i);
    expect(screen.queryByTestId('reorder-result')).toBeNull();
    expect(refreshCart).not.toHaveBeenCalled();

    await user.click(screen.getByTestId('reorder-button'));
    expect(await screen.findByTestId('reorder-summary')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).toBeNull();
    expect(refreshCart).toHaveBeenCalledTimes(1);
  });

  it('a second reorder replaces the previous result instead of stacking', async () => {
    dashboardAPI.reorderOrder.mockResolvedValueOnce({ data: partial });
    dashboardAPI.reorderOrder.mockResolvedValueOnce({ data: allAdded });
    const user = await renderTab();
    await user.click(screen.getByTestId('reorder-button'));
    await screen.findByTestId('reorder-unavailable');
    await user.click(screen.getByTestId('reorder-button'));
    await waitFor(() => expect(screen.getByTestId('reorder-summary')).toHaveTextContent('2 items'));
    expect(screen.getAllByTestId('reorder-result')).toHaveLength(1);
    expect(screen.queryByTestId('reorder-unavailable')).toBeNull();
  });
});
