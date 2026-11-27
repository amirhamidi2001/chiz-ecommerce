// Order detail modal: Toman formatting (the old USD fmt() is gone), the status
// timeline, and Epic 7 shipment tracking. The REAL ShipmentTrackingWidget is used
// on purpose (the sibling OrdersTab tests stub it out).
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

vi.mock('../services/api', () => ({
  dashboardAPI: { getOrders: vi.fn(), getOrder: vi.fn() },
}));
vi.mock('../utils/download', () => ({ saveBlob: vi.fn() }));
// OrdersTab's Reorder button needs the cart context and a router.
vi.mock('../context/CartContext', () => ({ useCart: () => ({ refreshCart: vi.fn() }) }));

import OrdersTab from '../components/OrdersTab';
import { dashboardAPI } from '../services/api';
import { ORDER_CANCELLED_MESSAGE_FA } from '../constants/orderStatus';

const baseOrder = {
  id: 7,
  order_number: 'ORD-ABC123',
  status: 'processing',
  created_at: '2026-01-15T12:00:00Z',
  subtotal: 500_000,
  shipping_cost: 99_900 + 0,
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
  items: [
    { id: 1, product_name: 'Rose Serum', product_image: '', quantity: 2, subtotal: 299_900 },
  ],
  shipment: null,
};

const shipment = {
  carrier_name: 'Iran Post',
  tracking_number: 'RR1234567IR',
  status: 'in_transit',
  status_display: 'In Transit',
  last_tracked_at: '2026-01-16T09:00:00Z',
};

const openModal = async (overrides = {}) => {
  const order = { ...baseOrder, ...overrides };
  dashboardAPI.getOrders.mockResolvedValue({
    data: { count: 1, results: [{ ...order, items_count: 1 }] },
  });
  dashboardAPI.getOrder.mockResolvedValue({ data: order });
  const user = userEvent.setup();
  render(<MemoryRouter><OrdersTab /></MemoryRouter>);
  await user.click(await screen.findByText(/view details/i));
  await screen.findByText(`Order ${order.order_number}`);
  return user;
};

describe('OrdersTab — Toman formatting (fmt -> formatToman)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('formats the list total as Toman, not USD', async () => {
    dashboardAPI.getOrders.mockResolvedValue({
      data: { count: 1, results: [{ ...baseOrder, items_count: 1 }] },
    });
    render(<MemoryRouter><OrdersTab /></MemoryRouter>);
    // 644,900 Rial = 64,490 Toman. The old USD fmt() printed "$644,900.00".
    expect(await screen.findByText('64,490 تومان')).toBeInTheDocument();
    expect(screen.queryByText(/\$/)).toBeNull();
  });

  it('formats item lines and every price-breakdown row as Toman', async () => {
    await openModal({ discount: 50_000 });
    const modal = document.querySelector('.max-w-2xl');
    expect(within(modal).getByText('29,990 تومان')).toBeInTheDocument(); // item line
    expect(within(modal).getByText('50,000 تومان')).toBeInTheDocument(); // subtotal
    expect(within(modal).getByText('9,990 تومان')).toBeInTheDocument(); // shipping
    expect(within(modal).getByText('4,500 تومان')).toBeInTheDocument(); // tax
    expect(within(modal).getByText('-5,000 تومان')).toBeInTheDocument(); // discount
    expect(within(modal).getByText('64,490 تومان')).toBeInTheDocument(); // total
    expect(modal.textContent).not.toMatch(/[$]/);
  });
});

describe('OrderDetailModal — status timeline', () => {
  beforeEach(() => vi.clearAllMocks());

  it('replaces the flat badge with the step timeline', async () => {
    await openModal({ status: 'shipped' });
    const modal = document.querySelector('.max-w-2xl');
    expect(within(modal).getByTestId('order-timeline')).toBeInTheDocument();
    expect(within(modal).getByTestId('order-step-shipped').dataset.current).toBe('true');
    expect(within(modal).getByTestId('order-step-delivered').dataset.active).toBe('false');
  });

  it.each(['pending', 'processing', 'shipped', 'delivered'])(
    'highlights the %s step',
    async (status) => {
      await openModal({ status });
      expect(screen.getByTestId(`order-step-${status}`).dataset.current).toBe('true');
    },
  );

  it('shows the distinct cancelled state for a cancelled order', async () => {
    await openModal({ status: 'cancelled' });
    expect(screen.getByTestId('order-cancelled')).toHaveTextContent(ORDER_CANCELLED_MESSAGE_FA);
    expect(screen.queryByTestId('order-timeline')).toBeNull();
  });
});

describe('OrderDetailModal — shipment tracking (Epic 7)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders carrier, tracking number and shipment status when order.shipment is present', async () => {
    await openModal({ status: 'shipped', shipment });
    const tracking = screen.getByTestId('shipment-tracking');
    expect(within(tracking).getByText('Iran Post')).toBeInTheDocument();
    expect(within(tracking).getByText(/RR1234567IR/)).toBeInTheDocument();
    expect(within(tracking).getByText('In Transit', { selector: 'span.bg-teal-50' })).toBeInTheDocument();
    expect(screen.queryByTestId('shipment-not-shipped')).toBeNull();
  });

  it('shows a clean "not yet shipped" state (no empty tracking box) when there is no shipment', async () => {
    await openModal({ status: 'processing', shipment: null });
    expect(screen.getByTestId('shipment-not-shipped')).toBeInTheDocument();
    expect(screen.queryByTestId('shipment-tracking')).toBeNull();
    expect(screen.queryByText(/Tracking #/)).toBeNull();
  });

  it('omits the Shipment section for a cancelled order that never shipped', async () => {
    await openModal({ status: 'cancelled', shipment: null });
    expect(screen.queryByText('Shipment')).toBeNull();
    expect(screen.queryByTestId('shipment-not-shipped')).toBeNull();
  });

  it('still shows tracking for a cancelled order that did have a shipment', async () => {
    await openModal({ status: 'cancelled', shipment: { ...shipment, status: 'failed', status_display: 'Failed' } });
    expect(screen.getByTestId('shipment-failed')).toBeInTheDocument();
  });
});
