import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../services/api', () => ({
  dashboardAPI: {
    getOrders: vi.fn(),
    getOrder: vi.fn(),
    downloadInvoice: vi.fn(),
  },
}));
vi.mock('../components/ShipmentTrackingWidget', () => ({ default: () => null }));
vi.mock('../utils/download', () => ({ saveBlob: vi.fn() }));
// OrdersTab's Reorder button needs the cart context and a router.
vi.mock('../context/CartContext', () => ({ useCart: () => ({ refreshCart: vi.fn() }) }));

import OrdersTab from '../components/OrdersTab';
import { dashboardAPI } from '../services/api';
import { saveBlob } from '../utils/download';

const baseOrder = {
  id: 7,
  order_number: 'ORD-ABC123',
  status: 'processing',
  created_at: '2026-01-15T12:00:00Z',
  subtotal: 500_000,
  shipping_cost: 99_900,
  tax: 45_000,
  discount: 0,
  total: 644_900,
  first_name: 'Jane',
  last_name: 'Smith',
  shipping_address: '1 Test St',
  shipping_city: 'Tehran',
  shipping_state: 'tehran',
  shipping_zip: '12345',
  shipping_country: 'IR',
  payment_method: 'credit_card',
  items: [],
  shipment: null,
};

const openModal = async (status = 'processing') => {
  const order = { ...baseOrder, status };
  dashboardAPI.getOrders.mockResolvedValue({
    data: { count: 1, results: [{ ...order, item_count: 1 }] },
  });
  dashboardAPI.getOrder.mockResolvedValue({ data: order });
  const user = userEvent.setup();
  render(<MemoryRouter><OrdersTab /></MemoryRouter>);
  await user.click(await screen.findByText(/view details/i));
  return user;
};

describe('OrderDetailModal — Download Invoice', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it('fetches the PDF through the authenticated axios helper and saves it', async () => {
    dashboardAPI.downloadInvoice.mockResolvedValue({ data: new Uint8Array([37, 80, 68, 70]) });
    const user = await openModal();

    await user.click(await screen.findByTestId('download-invoice'));

    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(dashboardAPI.downloadInvoice).toHaveBeenCalledWith(7);
    const [blob, filename] = saveBlob.mock.calls[0];
    expect(blob.type).toBe('application/pdf');
    expect(filename).toBe('invoice_ORD-ABC123.pdf');
  });

  it('is not a bare anchor (which would send no Authorization header)', async () => {
    dashboardAPI.downloadInvoice.mockResolvedValue({ data: new Uint8Array([1]) });
    await openModal();
    const control = await screen.findByTestId('download-invoice');
    expect(control.tagName).toBe('BUTTON');
    expect(control.getAttribute('href')).toBeNull();
  });

  it('shows an error and re-enables the button when the download fails', async () => {
    dashboardAPI.downloadInvoice.mockRejectedValue(new Error('403'));
    const user = await openModal();

    await user.click(await screen.findByTestId('download-invoice'));

    expect(await screen.findByRole('alert')).toHaveTextContent('دانلود فاکتور با خطا مواجه شد');
    expect(saveBlob).not.toHaveBeenCalled();
    expect(screen.getByTestId('download-invoice')).not.toBeDisabled();
  });

  it.each(['processing', 'shipped', 'delivered'])('offers the button for a %s order', async (status) => {
    await openModal(status);
    expect(await screen.findByTestId('download-invoice')).toBeEnabled();
  });

  it.each(['pending', 'cancelled'])('hides the button for a %s order', async (status) => {
    await openModal(status);
    await screen.findByText(/order ORD-ABC123/i);
    expect(screen.queryByTestId('download-invoice')).toBeNull();
  });

  it('disables the button and shows progress while the PDF is generated', async () => {
    let resolve;
    dashboardAPI.downloadInvoice.mockReturnValue(new Promise((r) => { resolve = r; }));
    const user = await openModal();

    await user.click(await screen.findByTestId('download-invoice'));
    const button = screen.getByTestId('download-invoice');
    expect(button).toBeDisabled();
    expect(button).toHaveTextContent(/preparing/i);

    resolve({ data: new Uint8Array([1]) });
    await waitFor(() => expect(screen.getByTestId('download-invoice')).toBeEnabled());
    expect(screen.getByTestId('download-invoice')).toHaveTextContent('Download Invoice');
  });

  it('can retry after a failure and clears the error on success', async () => {
    dashboardAPI.downloadInvoice
      .mockRejectedValueOnce(new Error('500'))
      .mockResolvedValueOnce({ data: new Uint8Array([1]) });
    const user = await openModal();

    await user.click(await screen.findByTestId('download-invoice'));
    expect(await screen.findByRole('alert')).toBeInTheDocument();

    await user.click(screen.getByTestId('download-invoice'));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
