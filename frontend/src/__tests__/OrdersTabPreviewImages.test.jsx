// Task 14.3.3.1 (QA): the orders list drew an empty bordered box (and React warned about
// <img src="">) for every order item whose `product_image` snapshot is blank.
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('../services/api', () => ({
  dashboardAPI: { getOrders: vi.fn(), getOrder: vi.fn() },
}));
vi.mock('../components/ShipmentTrackingWidget', () => ({ default: () => null }));
vi.mock('../utils/download', () => ({ saveBlob: vi.fn() }));
// OrdersTab's Reorder button needs the cart context and a router.
vi.mock('../context/CartContext', () => ({ useCart: () => ({ refreshCart: vi.fn() }) }));

import OrdersTab from '../components/OrdersTab';
import { dashboardAPI } from '../services/api';

const listOrder = (preview_images) => ({
  id: 1, order_number: 'ORD-1', status: 'shipped', created_at: '2026-01-15T12:00:00Z',
  total: 100_000, item_count: preview_images.length, preview_images,
});

const renderWith = async (previews) => {
  dashboardAPI.getOrders.mockResolvedValue({ data: { count: 1, results: [listOrder(previews)] } });
  const { container } = render(<MemoryRouter><OrdersTab /></MemoryRouter>);
  await screen.findByText('ORD-1');
  return container;
};

describe('OrdersTab order-list thumbnails', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders no <img> (and no empty src) when every snapshot is blank', async () => {
    const c = await renderWith(['', '']);
    expect(c.querySelectorAll('img')).toHaveLength(0);
  });

  it('renders only the non-blank thumbnails', async () => {
    const c = await renderWith(['', 'http://x/a.png', '']);
    const imgs = [...c.querySelectorAll('img')];
    expect(imgs.map((i) => i.getAttribute('src'))).toEqual(['http://x/a.png']);
  });
});
