import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import Home from '../pages/Home';

// ─── Mock all child components ────────────────────────────────────────────────
// Each child is replaced with a lightweight stub so this test verifies only
// that Home correctly composes and mounts its sections — without triggering
// any API calls, context dependencies, or async side-effects from the children.

vi.mock('../components/Hero', () => ({
  default: () => <div data-testid="mock-hero">Hero Section</div>,
}));

vi.mock('../components/PromoCards', () => ({
  default: () => <div data-testid="mock-promocards">Promo Cards Section</div>,
}));

vi.mock('../components/BestSellers', () => ({
  default: () => <div data-testid="mock-bestsellers">Best Sellers Section</div>,
}));

vi.mock('../components/Cards', () => ({
  default: () => <div data-testid="mock-cards">Cards Section</div>,
}));

vi.mock('../components/Countdown', () => ({
  default: () => <div data-testid="mock-countdown">Countdown Section</div>,
}));

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('Home Page', () => {
  describe('Rendering', () => {
    it('should mount without crashing', () => {
      expect(() => render(<Home />)).not.toThrow();
    });

    it('should render all main layout sections successfully', () => {
      render(<Home />);

      expect(screen.getByTestId('mock-hero')).toBeInTheDocument();
      expect(screen.getByTestId('mock-promocards')).toBeInTheDocument();
      expect(screen.getByTestId('mock-bestsellers')).toBeInTheDocument();
      expect(screen.getByTestId('mock-cards')).toBeInTheDocument();
      expect(screen.getByTestId('mock-countdown')).toBeInTheDocument();
    });

    it('should render each section exactly once', () => {
      render(<Home />);

      expect(screen.getAllByTestId('mock-hero')).toHaveLength(1);
      expect(screen.getAllByTestId('mock-promocards')).toHaveLength(1);
      expect(screen.getAllByTestId('mock-bestsellers')).toHaveLength(1);
      expect(screen.getAllByTestId('mock-cards')).toHaveLength(1);
      expect(screen.getAllByTestId('mock-countdown')).toHaveLength(1);
    });

    it('should render sections in the correct document order', () => {
      const { container } = render(<Home />);

      // Collect all mocked section nodes in DOM order
      const sections = within(container).getAllByTestId(
        /^mock-(hero|promocards|bestsellers|cards|countdown)$/,
      );

      const orderedIds = sections.map((el) => el.dataset.testid);

      expect(orderedIds).toEqual([
        'mock-hero',
        'mock-promocards',
        'mock-bestsellers',
        'mock-cards',
        'mock-countdown',
      ]);
    });
  });
});
