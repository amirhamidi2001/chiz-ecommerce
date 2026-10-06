import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../services/api', () => ({
  dashboardAPI: {
    getOrders: vi.fn(),
    getOrder: vi.fn(),
  },
  downloadOrderInvoice: vi.fn(),
}));
vi.mock('../components/ShipmentTrackingWidget', () => ({ default: () => null }));
vi.mock('../utils/download', () => ({ saveBlob: vi.fn() }));

import OrdersTab from '../components/OrdersTab';
import { dashboardAPI, downloadOrderInvoice } from '../services/api';
import { saveBlob } from '../utils/download';

const order = {
  id: 7,
  order_number: 'ORD-ABC123',
  status: 'processing',
  created_at: '2026-01-15T12:00:00Z',
  subtotal: '50.00',
  shipping_cost: '9.99',
  tax: '4.50',
  discount: '0.00',
  total: '64.49',
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

const openModal = async () => {
  dashboardAPI.getOrders.mockResolvedValue({
    data: { count: 1, results: [{ ...order, item_count: 1 }] },
  });
  dashboardAPI.getOrder.mockResolvedValue({ data: order });
  const user = userEvent.setup();
  render(<OrdersTab />);
  await user.click(await screen.findByText(/view details/i));
  return user;
};

describe('OrderDetailModal — Download Invoice', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it('fetches the PDF through the authenticated axios helper and saves it', async () => {
    downloadOrderInvoice.mockResolvedValue({ data: new Uint8Array([37, 80, 68, 70]) });
    const user = await openModal();

    await user.click(await screen.findByTestId('download-invoice'));

    await waitFor(() => expect(saveBlob).toHaveBeenCalledTimes(1));
    expect(downloadOrderInvoice).toHaveBeenCalledWith(7);
    const [blob, filename] = saveBlob.mock.calls[0];
    expect(blob.type).toBe('application/pdf');
    expect(filename).toBe('invoice_ORD-ABC123.pdf');
  });

  it('is not a bare anchor (which would send no Authorization header)', async () => {
    downloadOrderInvoice.mockResolvedValue({ data: new Uint8Array([1]) });
    await openModal();
    const control = await screen.findByTestId('download-invoice');
    expect(control.tagName).toBe('BUTTON');
    expect(control.getAttribute('href')).toBeNull();
  });

  it('shows an error and re-enables the button when the download fails', async () => {
    downloadOrderInvoice.mockRejectedValue(new Error('403'));
    const user = await openModal();

    await user.click(await screen.findByTestId('download-invoice'));

    expect(await screen.findByRole('alert')).toHaveTextContent(/could not download/i);
    expect(saveBlob).not.toHaveBeenCalled();
    expect(screen.getByTestId('download-invoice')).not.toBeDisabled();
  });
});
