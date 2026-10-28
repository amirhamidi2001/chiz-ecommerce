import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

import RecommendedForYou from '../components/RecommendedForYou';
import * as api from '../services/api';
import { getRecentlyViewed } from '../utils/recentlyViewed';
import { formatToman } from '../utils/money';

vi.mock('../services/api', () => ({
  getHomeRecommendations: vi.fn(),
  isAuthenticated: vi.fn(() => false),
  // BestSellers (which exports the shared ProductCard) imports this at module load
  getProducts: vi.fn(),
}));

vi.mock('../utils/recentlyViewed', () => ({
  getRecentlyViewed: vi.fn(() => []),
}));

const MOCK_RECS = [
  {
    id: 31,
    slug: 'rec-one',
    name: 'Rec One',
    price: 245_000,
    rating: '4.9',
    reviews_count: 12,
    thumbnail_url: '/assets/img/product/product-2.webp',
    category: { name: 'Skincare' },
    is_sale: false,
    is_new: false,
  },
  {
    id: 32,
    slug: 'rec-two',
    name: 'Rec Two',
    price: 180_000,
    rating: '4.1',
    reviews_count: 3,
    thumbnail_url: '/assets/img/product/product-3.webp',
    category: { name: 'Skincare' },
    is_sale: false,
    is_new: false,
  },
];

const renderSection = () =>
  render(
    <MemoryRouter>
      <RecommendedForYou />
    </MemoryRouter>,
  );

const HEADING = /recommended for you/i;

beforeEach(() => {
  vi.clearAllMocks();
  getRecentlyViewed.mockReturnValue([
    { id: 5, slug: 'five', name: 'Five' }, // most recent first
    { id: 9, slug: 'nine', name: 'Nine' },
  ]);
  api.isAuthenticated.mockReturnValue(false);
  api.getHomeRecommendations.mockResolvedValue({ data: MOCK_RECS });
});

describe('RecommendedForYou', () => {
  it('renders the heading and a card per recommendation', async () => {
    renderSection();

    expect(await screen.findByRole('heading', { name: HEADING })).toBeInTheDocument();
    expect(screen.getByText('Rec One')).toBeInTheDocument();
    expect(screen.getByText('Rec Two')).toBeInTheDocument();
    expect(screen.getByText(formatToman(245_000))).toBeInTheDocument();
  });

  it('uses the shared product card (links to the product page)', async () => {
    renderSection();
    const link = await screen.findByRole('link', { name: 'Rec One' });
    expect(link).toHaveAttribute('href', '/product/rec-one');
  });

  it('builds its request from getRecentlyViewed(), ids only, most-recent first', async () => {
    renderSection();
    await screen.findByRole('heading', { name: HEADING });

    expect(getRecentlyViewed).toHaveBeenCalled();
    expect(api.getHomeRecommendations).toHaveBeenCalledTimes(1);
    expect(api.getHomeRecommendations).toHaveBeenCalledWith([5, 9]);
  });

  it('skips entries without an id', async () => {
    getRecentlyViewed.mockReturnValue([{ slug: 'broken' }, null, { id: 7 }]);
    renderSection();
    await screen.findByRole('heading', { name: HEADING });

    expect(api.getHomeRecommendations).toHaveBeenCalledWith([7]);
  });

  it('renders nothing when the backend returns no results', async () => {
    api.getHomeRecommendations.mockResolvedValue({ data: [] });
    const { container } = renderSection();

    await waitFor(() => expect(api.getHomeRecommendations).toHaveBeenCalled());
    expect(screen.queryByRole('heading', { name: HEADING })).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing (and does not crash) when the request fails', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    api.getHomeRecommendations.mockRejectedValue(new Error('boom'));
    const { container } = renderSection();

    await waitFor(() => expect(api.getHomeRecommendations).toHaveBeenCalled());
    await waitFor(() => expect(errorSpy).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
    errorSpy.mockRestore();
  });

  it('anonymous visitor with no history: no request, nothing rendered', () => {
    getRecentlyViewed.mockReturnValue([]);
    api.isAuthenticated.mockReturnValue(false);
    const { container } = renderSection();

    expect(api.getHomeRecommendations).not.toHaveBeenCalled();
    expect(container).toBeEmptyDOMElement();
  });

  it('logged-in user with no local history still requests (purchase history is server-side)', async () => {
    getRecentlyViewed.mockReturnValue([]);
    api.isAuthenticated.mockReturnValue(true);
    renderSection();

    expect(await screen.findByRole('heading', { name: HEADING })).toBeInTheDocument();
    expect(api.getHomeRecommendations).toHaveBeenCalledWith([]);
  });

  it('accepts a paginated { results } response shape', async () => {
    api.getHomeRecommendations.mockResolvedValue({ data: { results: MOCK_RECS } });
    renderSection();

    const heading = await screen.findByRole('heading', { name: HEADING });
    expect(within(heading.closest('section')).getByText('Rec Two')).toBeInTheDocument();
  });
});
