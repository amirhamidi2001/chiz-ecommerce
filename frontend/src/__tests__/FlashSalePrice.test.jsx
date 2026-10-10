import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { FlashSaleBadge, FlashSalePrice } from '../components/FlashSalePrice';
import { formatRemaining, isOnFlashSale } from '../utils/flashSale';

const onSale = (overrides = {}) => ({
  is_on_flash_sale: true,
  flash_sale_price: '60.00',
  flash_sale_original_price: '80.00',
  flash_sale_price_varies: false,
  flash_sale_discount_percent: '25.00',
  ...overrides,
});
const notOnSale = { is_on_flash_sale: false, flash_sale_price: null };

describe('isOnFlashSale', () => {
  it('is true only for a product flagged on sale that has a sale price', () => {
    expect(isOnFlashSale(onSale())).toBe(true);
    expect(isOnFlashSale(notOnSale)).toBe(false);
    expect(isOnFlashSale({ is_on_flash_sale: true, flash_sale_price: null })).toBe(false);
    expect(isOnFlashSale({})).toBe(false);
    expect(isOnFlashSale(undefined)).toBe(false);
  });
});

describe('FlashSaleBadge', () => {
  it('shows the sale and its percentage', () => {
    render(<FlashSaleBadge product={onSale()} />);
    expect(screen.getByText(/flash sale -25%/i)).toBeInTheDocument();
  });

  it('drops trailing zeros from the percentage', () => {
    render(<FlashSaleBadge product={onSale({ flash_sale_discount_percent: '12.50' })} />);
    expect(screen.getByText(/-12\.5%/)).toBeInTheDocument();
  });

  it('can omit the percentage', () => {
    render(<FlashSaleBadge product={onSale()} showPercent={false} />);
    expect(screen.getByText('Flash Sale')).toBeInTheDocument();
    expect(screen.queryByText(/-25%/)).not.toBeInTheDocument();
  });

  it('renders nothing for a product that is not on sale', () => {
    const { container } = render(<FlashSaleBadge product={notOnSale} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('FlashSalePrice', () => {
  it('shows the sale price with the original struck through', () => {
    render(<FlashSalePrice product={onSale()} />);
    expect(screen.getByText('$60.00')).toBeInTheDocument();
    const original = screen.getByText('$80.00');
    expect(original.tagName).toBe('DEL');
    expect(screen.queryByText('From')).not.toBeInTheDocument();
  });

  it('prefixes "From" when the product’s variants differ in price', () => {
    render(<FlashSalePrice product={onSale({ flash_sale_price_varies: true })} />);
    expect(screen.getByText('From')).toBeInTheDocument();
    expect(screen.getByText('$60.00')).toBeInTheDocument();
  });

  it('formats prices to two decimals', () => {
    render(
      <FlashSalePrice product={onSale({ flash_sale_price: '9.5', flash_sale_original_price: 12 })} />,
    );
    expect(screen.getByText('$9.50')).toBeInTheDocument();
    expect(screen.getByText('$12.00')).toBeInTheDocument();
  });

  it('renders nothing for a product that is not on sale', () => {
    const { container } = render(<FlashSalePrice product={notOnSale} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('formatRemaining', () => {
  it.each([
    [0, '00:00:00'],
    [-5000, '00:00:00'],
    [1000, '00:00:01'],
    [59_000, '00:00:59'],
    [3_599_000, '00:59:59'],
    [3_600_000, '01:00:00'],
    [86_399_000, '23:59:59'],
    [86_400_000, '1d 00:00:00'],
    [(2 * 86400 + 3 * 3600 + 4 * 60 + 5) * 1000, '2d 03:04:05'],
  ])('%i ms -> %s', (ms, expected) => {
    expect(formatRemaining(ms)).toBe(expected);
  });

  it('rounds partial seconds UP so 00:00:00 means the sale is actually over', () => {
    expect(formatRemaining(1)).toBe('00:00:01');
    expect(formatRemaining(1400)).toBe('00:00:02');
  });
});
